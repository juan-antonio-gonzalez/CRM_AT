"""El pipeline de una consulta.

Una pregunta atraviesa estas etapas:

1. **Límite de tasa** — antes de gastar un solo token. Protege la factura y frena
   un bucle automatizado.
2. **Normalización** — se acota el largo y se sacan caracteres de control.
3. **Clasificador de intención** — una llamada corta y barata decide si la
   pregunta es sobre el uso de la aplicación. Si no lo es, **nunca llega al modelo
   que tiene el manual en contexto**: el texto hostil se corta antes.
4. **Armado de mensajes** — el texto del usuario va *siempre* en un mensaje de rol
   `user`, nunca concatenado dentro del system prompt. La pantalla que informa el
   navegador se valida contra las rutas conocidas y se etiqueta como contexto.
5. **Generación** — streaming desde DeepSeek.
6. **Verificación de salida** — canario, cita de fuente y largo.

Sobre el aislamiento
--------------------
El texto del usuario nunca se interpola en las instrucciones. No hay ningún
``f"...{pregunta}..."`` dentro de un texto que el modelo lea como orden. El único
lugar donde aparece la pregunta es el campo ``content`` de un mensaje ``user``, y
el modelo está instruido para tratarlo como una pregunta y no como una orden. Eso
es lo que hace que una inyección no tenga por dónde entrar.

El clasificador tampoco la recibe como instrucción: va como mensaje ``user`` de un
prompt distinto, corto y sin el manual.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import AsyncIterator

from config import settings
from services.agente import guard, knowledge, llm, persona

# Caracteres de control, salvo tabulación y salto de línea, que sí aportan.
_CONTROL = re.compile(r"[\x00-\x08\x0b-\x1f\x7f]")

# La marca con la que Caty cierra cada respuesta, declarando de dónde sale. Sin
# esto, la respuesta no está anclada a nada y no se muestra.
#
# La palabra no se exige exacta. El modelo escribe `[fuente: ...]` casi siempre,
# pero cada tanto se le va una letra y queda `[fuerte: funcionalidades.md]`.
# Exigir la palabra literal descartaba respuestas correctas: medido sobre una
# misma pregunta, 2 de cada 5. Lo que importa es que la respuesta **declare** su
# origen, no que escriba bien la palabra que lo declara.
#
# Se acepta cualquier palabra de tres a catorce letras entre corchetes seguida de
# dos puntos. Una respuesta fuera de alcance no produce ese patrón.
_CITA = re.compile(r"\[\s*([A-Za-zÁÉÍÓÚÜÑáéíóúüñ]{3,14})\s*:\s*([^\]\n]{1,80})\]")


def cita_de(texto: str) -> re.Match | None:
    """La marca de origen de una respuesta, si la tiene."""
    return _CITA.search(texto or "")


@dataclass
class Evento:
    """Un paso del stream, tal como lo va a mandar el endpoint."""

    tipo: str
    datos: dict = field(default_factory=dict)


def normalizar(texto: str) -> str:
    """Limpia y acota lo que escribió el usuario."""
    texto = _CONTROL.sub("", texto or "")
    texto = re.sub(r"\n{3,}", "\n\n", texto)
    texto = texto.strip()
    tope = settings.agente_max_entrada
    return texto[:tope]


def _nota_de_permisos(modulos_ocultos) -> str:
    """Le dice a Caty qué pantallas no puede ver quien pregunta.

    Va en el turno del usuario y **no** en el prefijo del sistema a propósito: el
    prefijo tiene que seguir siendo idéntico byte a byte entre consultas para que
    el caché de contexto de DeepSeek sirva. Meter los permisos ahí lo partiría en
    una variante por usuario y multiplicaría el costo.

    No es una barrera de seguridad —Caty no decide accesos—: es para que no mande a
    alguien a una pantalla que le va a dar un 403.
    """
    if not modulos_ocultos:
        return ""
    nombres = ", ".join(sorted(modulos_ocultos))
    return (f"[Quien consulta no tiene acceso a estas pantallas: {nombres}. "
            f"Si pregunta por alguna, decile que su cuenta no la tiene y que se la "
            f"pida a un administrador. No la expliques.]")


def _mensajes(texto: str, historial: list[dict], ruta_actual: str,
              modulos_ocultos=()) -> list[dict]:
    """Arma la conversación. El prefijo (system) es idéntico en cada consulta."""
    mensajes: list[dict] = [{
        "role": "system",
        "content": persona.system_prompt(knowledge.conocimiento_cacheado()),
    }]

    for turno in (historial or [])[-settings.agente_max_turnos:]:
        rol = "assistant" if str(turno.get("rol", "")).lower() == "assistant" else "user"
        contenido = normalizar(str(turno.get("texto", "")))
        if contenido:
            mensajes.append({"role": rol, "content": contenido})

    partes: list[str] = []
    if knowledge.ruta_valida(ruta_actual):
        partes.append(persona.contexto_pantalla(ruta_actual))
    nota = _nota_de_permisos(modulos_ocultos)
    if nota:
        partes.append(nota)
    partes.append(texto)

    mensajes.append({"role": "user", "content": "\n\n".join(partes)})
    return mensajes


async def responder(
    mensaje: str,
    historial: list[dict] | None = None,
    ruta_actual: str = "",
    usuario_id=None,
    modulos_ocultos=(),
) -> AsyncIterator[Evento]:
    """Genera la respuesta de Caty, en partes."""
    if not settings.agente_habilitado:
        yield Evento("error", {"motivo": "deshabilitada",
                               "mensaje": persona.DESHABILITADA})
        return

    # 1. Límite de tasa. Va primero porque es gratis y porque un bucle
    #    automatizado no debería llegar ni al clasificador.
    permitido, motivo = guard.permitir(usuario_id)
    if not permitido:
        yield Evento("rechazo", {
            "motivo": f"limite_{motivo}",
            "texto": persona.LIMITE_MINUTO if motivo == "minuto" else persona.LIMITE_DIA,
        })
        return

    # 2. Normalización.
    texto = normalizar(mensaje)
    if not texto:
        yield Evento("error", {"motivo": "vacio",
                               "mensaje": persona.RECHAZO_FUERA_ALCANCE})
        return

    # 3. Clasificador de intención. Si no responde, la consulta pasa: la
    #    verificación de salida sigue en pie y es la barrera que importa.
    clasificacion = await guard.clasificar(texto)
    if clasificacion is not None and not clasificacion.alcance:
        pantalla = clasificacion.pantalla
        yield Evento("rechazo", {
            "motivo": "fuera_de_alcance",
            "texto": (persona.rechazo_datos(pantalla["nombre"], pantalla["ruta"])
                      if pantalla else persona.RECHAZO_FUERA_ALCANCE),
            "tema": clasificacion.tema,
            "pantalla": pantalla,
        })
        return

    # 4 y 5. Armado y generación.
    mensajes = _mensajes(texto, historial or [], ruta_actual, modulos_ocultos)
    canario = persona.canario()
    tope = settings.agente_max_respuesta
    acumulado: list[str] = []

    try:
        async for fragmento in llm.transmitir(mensajes, max_tokens=600, temperatura=0.2):
            acumulado.append(fragmento)
            completo = "".join(acumulado)

            # El canario se revisa antes de emitir el fragmento que lo completa:
            # así no llega nunca a la pantalla, ni siquiera por un instante.
            if canario in completo:
                yield Evento("reemplazo", {"motivo": "canario",
                                           "texto": persona.FALLBACK_SIN_FUENTE})
                return

            # Un fragmento que todavía no tiene nada visible no se emite: si no,
            # el modal muestra un globo vacío y después lo reemplaza.
            if not completo.strip():
                continue

            if len(completo) >= tope:
                restante = fragmento[:max(0, tope - (len(completo) - len(fragmento)))]
                if restante:
                    yield Evento("token", {"texto": restante})
                yield Evento("reemplazo", {"motivo": "largo",
                                           "texto": persona.FALLBACK_SIN_FUENTE})
                return

            yield Evento("token", {"texto": fragmento})
    except llm.ErrorLLM as exc:
        yield Evento("error", {"motivo": "llm", "detalle": str(exc),
                               "mensaje": persona.ERROR_SERVICIO})
        return

    final = "".join(acumulado).strip()
    if not final:
        yield Evento("reemplazo", {"motivo": "vacio",
                                   "texto": persona.FALLBACK_SIN_FUENTE})
        return

    cita = cita_de(final)
    if not cita:
        yield Evento("reemplazo", {"motivo": "sin_fuente",
                                   "texto": persona.FALLBACK_SIN_FUENTE})
        return

    # La marca va además de la fuente: si el modelo empieza a declarar el origen
    # con otra palabra, conviene que se vea en la auditoría antes de que se
    # convierta en costumbre.
    yield Evento("cita", {"fuente": cita.group(2).strip(),
                          "marca": cita.group(1).lower()})
    yield Evento("fin", {"motivo": "ok", "texto": final})
