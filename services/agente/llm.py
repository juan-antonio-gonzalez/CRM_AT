"""Cliente de DeepSeek. El único lugar del proyecto que sale a la red.

Decisiones que no son obvias
----------------------------
**Thinking mode apagado.** DeepSeek lo trae encendido por defecto, con esfuerzo
alto. Para Caty eso es costo y latencia regalados: su tarea es encontrar la
instrucción en el manual que ya tiene en contexto y explicarla en dos frases, no
razonar un problema. Con thinking encendido, además, `temperature` no tiene
efecto; apagado, sí.

**El `reasoning_content` se descarta.** Cuando el modelo piensa, devuelve sus
pasos en un campo aparte del texto. Si se filtrara al usuario, Caty mostraría su
cadena de pensamiento en el modal. Nunca se reenvía.

**Los errores se traducen a `ErrorLLM`.** Quien llama no tiene que saber de
`httpx` ni de códigos de estado: sólo si Caty puede responder o no.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import AsyncIterator, Iterable

import httpx

from config import settings


class ErrorLLM(Exception):
    """No se pudo obtener respuesta del modelo."""


@dataclass
class Uso:
    """Consumo de tokens, para poder mirar la factura."""

    entrada: int = 0
    salida: int = 0
    cache: int = 0


def _cuerpo(
    mensajes: list[dict],
    *,
    stream: bool,
    max_tokens: int,
    temperatura: float,
    json_mode: bool = False,
) -> dict:
    cuerpo: dict = {
        "model": settings.deepseek_model,
        "messages": mensajes,
        "stream": stream,
        "max_tokens": max_tokens,
        # Explícito, aunque sea el valor por defecto: que el día que DeepSeek
        # cambie el default, Caty no empiece a pensar sola.
        "thinking": {"type": "disabled"},
    }
    if not stream:
        cuerpo["temperature"] = temperatura
    else:
        # Sin esto, el último bloque del stream no trae el consumo y no hay forma
        # de auditar el gasto.
        cuerpo["stream_options"] = {"include_usage": True}
    if json_mode:
        # El clasificador tiene que devolver JSON parseable. Pedirlo por prompt
        # funciona casi siempre, y "casi" no alcanza cuando el resultado decide
        # si una consulta se responde o se rechaza.
        cuerpo["response_format"] = {"type": "json_object"}
    return cuerpo


def _cabeceras() -> dict:
    clave = settings.deepseek_api_key.strip()
    if not clave:
        raise ErrorLLM("Falta DEEPSEEK_API_KEY.")
    return {
        "Authorization": f"Bearer {clave}",
        "Content-Type": "application/json",
    }


def _url() -> str:
    return settings.deepseek_base_url.rstrip("/") + "/chat/completions"


def _timeout(lectura_larga: bool = False) -> httpx.Timeout:
    """Timeouts separados por fase.

    Un `timeout=30` para todo trata igual a tres cosas muy distintas. Conectar
    tiene que ser rápido: si en 10 segundos no hay conexión, no la va a haber.
    Leer, en cambio, depende de que el modelo esté generando.

    Con streaming el timeout de lectura se aplica **a cada lectura**, así que es
    un timeout de inactividad: mientras sigan llegando fragmentos, no vence. Por
    eso puede ser holgado sin que un usuario espere 90 segundos mirando la nada.
    """
    return httpx.Timeout(
        settings.agente_timeout,
        connect=settings.agente_timeout_conexion,
        read=settings.agente_timeout_lectura if lectura_larga else settings.agente_timeout,
        write=settings.agente_timeout,
        pool=settings.agente_timeout_conexion,
    )


def _revisar(respuesta: httpx.Response) -> None:
    """Traduce un estado de error a algo que se pueda mostrar en un log."""
    if respuesta.status_code == 200:
        return
    detalle = respuesta.text[:300]
    if respuesta.status_code == 401:
        raise ErrorLLM("La clave de DeepSeek fue rechazada.")
    if respuesta.status_code == 402:
        raise ErrorLLM("La cuenta de DeepSeek no tiene saldo.")
    if respuesta.status_code == 429:
        raise ErrorLLM("DeepSeek está limitando las consultas.")
    raise ErrorLLM(f"DeepSeek devolvió {respuesta.status_code}: {detalle}")


def _consumo(datos: dict) -> Uso:
    uso = datos.get("usage") or {}
    detalles = uso.get("prompt_tokens_details") or {}
    return Uso(
        entrada=int(uso.get("prompt_tokens") or 0),
        salida=int(uso.get("completion_tokens") or 0),
        cache=int(detalles.get("cached_tokens") or 0),
    )


async def completar(
    mensajes: list[dict],
    *,
    max_tokens: int = 600,
    temperatura: float = 0.2,
    json_mode: bool = False,
) -> tuple[str, Uso]:
    """Una respuesta completa, sin streaming.

    Es lo que usa el clasificador de intención: una llamada corta que tiene que
    volver rápido y no necesita mostrar nada mientras llega.
    """
    try:
        async with httpx.AsyncClient(timeout=_timeout()) as cliente:
            respuesta = await cliente.post(
                _url(),
                headers=_cabeceras(),
                json=_cuerpo(mensajes, stream=False, max_tokens=max_tokens,
                             temperatura=temperatura, json_mode=json_mode),
            )
    except httpx.TimeoutException as exc:
        raise ErrorLLM("DeepSeek no respondió a tiempo.") from exc
    except httpx.RequestError as exc:
        raise ErrorLLM(f"No se pudo llegar a DeepSeek: {exc}") from exc

    _revisar(respuesta)

    try:
        datos = respuesta.json()
        contenido = datos["choices"][0]["message"].get("content") or ""
    except (ValueError, KeyError, IndexError, TypeError) as exc:
        raise ErrorLLM("DeepSeek devolvió una respuesta ilegible.") from exc

    return contenido, _consumo(datos)


async def transmitir(
    mensajes: list[dict],
    *,
    max_tokens: int = 600,
    temperatura: float = 0.2,
) -> AsyncIterator[str]:
    """Respuesta por partes, para mostrarla mientras se escribe.

    Esperar ocho segundos a un bloque de texto se siente roto; ver las palabras
    aparecer se siente vivo. Sólo se emite `content`: el `reasoning_content` se
    descarta acá y no llega nunca al navegador.
    """
    try:
        async with httpx.AsyncClient(timeout=_timeout(lectura_larga=True)) as cliente:
            async with cliente.stream(
                "POST",
                _url(),
                headers=_cabeceras(),
                json=_cuerpo(mensajes, stream=True, max_tokens=max_tokens,
                             temperatura=temperatura),
            ) as respuesta:
                if respuesta.status_code != 200:
                    # Hay que leer el cuerpo antes de poder reportar el error, y
                    # con `stream` el cuerpo todavía no llegó.
                    await respuesta.aread()
                    _revisar(respuesta)

                async for linea in respuesta.aiter_lines():
                    fragmento = _fragmento(linea)
                    if fragmento:
                        yield fragmento
    except httpx.TimeoutException as exc:
        raise ErrorLLM("DeepSeek no respondió a tiempo.") from exc
    except httpx.RequestError as exc:
        raise ErrorLLM(f"No se pudo llegar a DeepSeek: {exc}") from exc


def _fragmento(linea: str) -> str:
    """Texto de una línea del stream SSE.

    Devuelve vacío para todo lo que no sea contenido nuevo: líneas en blanco, el
    marcador de fin, los bloques de consumo y el `reasoning_content`.
    """
    linea = linea.strip()
    if not linea or not linea.startswith("data:"):
        return ""
    carga = linea[len("data:"):].strip()
    if not carga or carga == "[DONE]":
        return ""
    try:
        datos = json.loads(carga)
        return datos["choices"][0]["delta"].get("content") or ""
    except (ValueError, KeyError, IndexError, TypeError):
        # Un bloque que no se entiende no justifica cortar la respuesta que ya
        # está llegando: se saltea.
        return ""


def unir(fragmentos: Iterable[str]) -> str:
    return "".join(fragmentos)
