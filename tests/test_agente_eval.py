"""Set de evaluación de Caty.

«Sabe el 100% de cómo funciona la aplicación» no es una afirmación, es un test.
Este archivo tiene una pregunta por pantalla, con la respuesta correcta acotada a
términos que **tienen que aparecer**: las etiquetas literales que el usuario ve.

Las pruebas de estructura corren siempre y no cuestan nada: verifican que el set
cubra todas las pantallas y que las rutas a las que apunta existan de verdad.

Las pruebas de contenido están marcadas con `eval` y **no corren por defecto**:
llaman a la API real de DeepSeek, cuestan dinero y dependen de la red.

    pytest -m eval tests/test_agente_eval.py -q

Subproducto: las preguntas que Caty no sabe responder son la lista de
documentación faltante del proyecto. Tiene valor aunque Caty funcione mal.
"""

import asyncio
import os
from dataclasses import dataclass

import pytest

from config import settings
from services.agente import chat, guard, knowledge, persona


@dataclass(frozen=True)
class Caso:
    """Una pregunta, lo que la respuesta tiene que mencionar, y dónde vive eso."""

    pregunta: str
    espera: tuple[str, ...]
    pantalla: str


# Una pregunta por pantalla, más las transversales. Los términos de `espera` son
# etiquetas reales del mapa del sistema: si el inventario de interfaz cambia, la
# prueba de cobertura de abajo avisa antes de que esto se vuelva mentira.
CASOS: tuple[Caso, ...] = (
    Caso("¿Cómo llego al dashboard y qué muestra?", ("dashboard", "requiere atención", "visitas técnicas"), "/"),
    Caso("¿Dónde busco algo en toda la aplicación?", ("buscar", "resultados para", "ver todos"), "/buscar"),
    Caso("¿Cómo genero el informe estratégico de un cliente?", ("informe estratégico", "reporte", "directorio"), "/cliente-reporte/{customer_id}"),
    Caso("¿Dónde veo el directorio de clientes?", ("clientes", "directorio"), "/clientes"),
    Caso("¿Cómo doy de alta un cliente nuevo?", ("nuevo cliente", "nuevo-cliente", "registrar cliente"), "/nuevo-cliente"),
    Caso("¿Dónde configuro las tablas auxiliares?", ("configuración", "tablas auxiliares", "configuracion"), "/configuracion"),
    Caso("¿Cómo creo una asignación de AT?", ("nueva asignación", "control de asignación", "control-at"), "/control-at"),
    Caso("¿Cómo edito una máquina del listado?", ("editar máquina", "editar-maquinaria", "guardar cambios"), "/editar-maquinaria/{machine_id}"),
    Caso("¿Cómo edito un producto ya cargado?", ("editar producto", "editar-producto", "actualizar especificación"), "/editar-producto/{product_id}"),
    Caso("¿Dónde veo el historial de una asignación AT?", ("historial de asignación", "historial-at"), "/historial-at"),
    Caso("¿Dónde veo quién cambió un registro?", ("historial de cambios", "historial-cambios"), "/historial-cambios"),
    Caso("¿Cómo importo datos desde una planilla de Excel?", ("importar", "excel", "plantilla"), "/importar"),
    Caso("¿Cómo cargo un relevamiento de infraestructura?", ("infraestructura", "relevamiento"), "/relevamiento-infraestructura/nuevo"),
    Caso("¿Dónde veo el reporte de un relevamiento de infraestructura?", ("reporte de infraestructura", "infraestructura", "descargar pdf"), "/relevamiento-infraestructura/{survey_id}/reporte"),
    Caso("¿Dónde veo los KPIs de calidad?", ("kpis de calidad", "kpi-calidad", "calidad"), "/kpi-calidad"),
    Caso("¿Dónde veo los KPIs de asignación AT?", ("kpis", "asignación at", "kpis-at"), "/kpis-at"),
    Caso("¿Cómo inicio sesión en la aplicación?", ("iniciar sesión", "usuario", "contraseña"), "/auth/login"),
    Caso("¿Cómo agrego una máquina a la biblioteca?", ("nueva máquina", "maquinaria"), "/maquinaria"),
    Caso("¿Dónde veo las minutas de reunión?", ("minutas", "minuta"), "/minutas"),
    Caso("¿Cómo creo una minuta de reunión?", ("nueva minuta", "minuta", "minutas/nueva"), "/minutas/nueva"),
    Caso("¿Cómo cargo una visita técnica nueva?", ("nueva visita", "informe de visita", "visitas2/nueva"), "/visitas2/nueva"),
    Caso("¿Cómo agrego un producto nuevo?", ("añadir producto", "nuevo producto", "nuevo-producto", "guardar especificación"), "/nuevo-producto"),
    Caso("¿Cómo cargo un relevamiento técnico V2?", ("nuevo relevamiento", "relevamiento"), "/relevamiento2/nuevo"),
    Caso("¿Dónde veo el organigrama?", ("organigrama",), "/organigrama"),
    Caso("¿Cómo creo un equipo de trabajo?", ("nuevo equipo", "crear equipo", "equipos"), "/equipos"),
    Caso("¿Cómo cambio los integrantes de un equipo?", ("editar equipo", "guardar cambios"), "/equipos/{team_id}/editar"),
    Caso("¿Cómo le asigno un equipo a un cliente?",
         ("equipo", "cliente"), "/nuevo-cliente"),
    Caso("El equipo cambió, ¿cómo actualizo a los clientes que lo tienen?",
         ("actualizar las asignaciones", "equipo"), "/equipos"),
    Caso("¿Cómo aplico el mismo equipo a todas las plantas de un cliente?",
         ("equipo", "plantas"), "/clientes"),
    Caso("¿Cómo importo a qué equipo pertenece cada cliente?",
         ("importar", "equipo"), "/importar"),
    # Conceptos, no pantallas: la respuesta sale de la documentación.
    Caso("¿Un cliente puede tener un equipo distinto en cada planta?",
         ("cada planta", "por planta"), "/equipos"),
    Caso("Edité un equipo y le cambié el AT, ¿por qué mis clientes siguen con el viejo?",
         ("actualizar las asignaciones", "foto"), "/equipos"),
    Caso("¿Cómo cambio mi contraseña?", ("contraseña", "perfil"), "/auth/perfil"),
    Caso("¿Dónde veo la biblioteca de productos?", ("productos", "biblioteca"), "/productos"),
    Caso("¿Cómo creo un usuario nuevo?", ("crear usuario", "nuevo usuario", "usuarios"), "/auth/register"),
    Caso("¿Dónde veo los relevamientos técnicos cargados?", ("relevamiento técnico", "relevamiento"), "/relevamiento2"),
    Caso("¿Dónde veo los relevamientos de infraestructura cargados?", ("infraestructura", "relevamiento"), "/relevamiento-infraestructura"),
    Caso("¿Cómo genero el reporte de una máquina relevada?", ("reporte de máquina", "reporte", "imprimir"), "/relevamiento/{machine_id}/reporte"),
    Caso("¿Dónde veo el relevamiento técnico de una máquina?", ("relevamiento", "reporte"), "/relevamiento/{machine_id}/ver"),
    Caso("¿Cómo creo una tarea en el plan de acción?", ("nueva tarea", "seguimiento", "plan de acción"), "/seguimiento-plan"),
    Caso("¿Cómo recupero un registro que desactivé?", ("papelera", "reactivar", "restaurar"), "/papelera"),
    Caso("¿Dónde administro los usuarios del sistema?", ("usuarios",), "/auth/usuarios"),
    Caso("¿Cómo le cambio los permisos a un usuario?",
         ("qué ve esta cuenta", "editar usuario", "guardar cambios"),
         "/auth/usuarios/{user_id}/editar"),
    Caso("¿Cómo hago que un usuario vea sólo algunas pantallas?",
         ("qué ve esta cuenta", "pantallas"), "/auth/usuarios/{user_id}/editar"),
    Caso("¿Puedo hacer que un usuario no vea la papelera?",
         ("qué ve esta cuenta", "pantallas"), "/auth/usuarios/{user_id}/editar"),
    Caso("¿Dónde veo las visitas técnicas cargadas?", ("visitas técnicas", "visitas"), "/visitas2"),
    Caso("¿Cómo agendo una visita en la agenda?", ("agendar visita", "agenda"), "/agenda"),
    # ── Transversales ──
    Caso("¿Cómo exporto el listado de clientes a Excel?", ("exportar", "excel"), "/clientes"),
    Caso("¿Cómo desactivo un registro en vez de eliminarlo?", ("desactivar", "desactiv"), "/clientes"),
    Caso("¿Cómo filtro el listado de visitas por cliente?", ("filtrar", "cliente"), "/visitas2"),
    Caso("¿Para qué sirve el plan de acción?", ("plan de acción", "seguimiento", "tareas"), "/seguimiento-plan"),
    Caso("¿Cómo imprimo un reporte?", ("imprimir", "impresión"), "/cliente-reporte/{customer_id}"),
    Caso("¿Qué es la papelera?", ("papelera",), "/papelera"),
    Caso("¿Cómo descargo la plantilla de importación?", ("plantilla", "importar", "descargar"), "/importar"),
    Caso("¿Cómo elimino una asignación AT?", ("eliminar", "asignación"), "/historial-at"),
    Caso("¿Qué muestra el tablero de KPIs de calidad?", ("calidad", "kpis"), "/kpi-calidad"),
    Caso("¿Cómo veo las plantas de un cliente?", ("plantas", "cliente"), "/clientes"),
)


# --------------------------------------------------------------------------- #
# Estructura — corre siempre, no cuesta nada
# --------------------------------------------------------------------------- #


def test_hay_al_menos_una_pregunta_por_pantalla():
    """Un set que no cubre una pantalla no puede afirmar que Caty sabe todo."""
    mapa = knowledge.construir_mapa()

    # Ruta principal de cada plantilla. Se toma de `mapa.rutas` y no de
    # `pantalla.rutas`, que guarda la clave completa ("GET /clientes").
    ruta_de = {}
    for ruta in mapa.rutas:
        if ruta.plantilla:
            ruta_de.setdefault(ruta.plantilla, ruta.path)

    rutas_de_pantallas = {
        ruta_de[p.plantilla]
        for p in mapa.pantallas_reales
        if p.plantilla in ruta_de and p.plantilla != "error.html"
        # `error.html` queda afuera porque la renderiza el manejador global de
        # excepciones, no una ruta a la que se pueda navegar.
    }

    cubiertas = {caso.pantalla for caso in CASOS}
    faltan = sorted(r for r in rutas_de_pantallas if r not in cubiertas)

    assert not faltan, f"pantallas sin ninguna pregunta: {faltan}"


def test_todas_las_rutas_del_set_existen():
    conocidas = knowledge.rutas_conocidas()
    inventadas = sorted({c.pantalla for c in CASOS if c.pantalla not in conocidas})
    assert not inventadas, f"el set apunta a rutas que no existen: {inventadas}"


def test_el_set_es_suficientemente_amplio():
    assert len(CASOS) >= 40, f"sólo hay {len(CASOS)} casos"


def test_no_hay_preguntas_repetidas():
    preguntas = [c.pregunta.strip().lower() for c in CASOS]
    repetidas = sorted({p for p in preguntas if preguntas.count(p) > 1})
    assert not repetidas, f"preguntas repetidas: {repetidas}"


def test_cada_caso_tiene_terminos_esperados():
    for caso in CASOS:
        assert caso.espera, caso.pregunta
        assert all(t.strip() for t in caso.espera), caso.pregunta


def test_los_terminos_esperados_aparecen_en_el_mapa():
    """Cada término esperado tiene que existir en la aplicación.

    Se exige que **todos** aparezcan, no uno: una expectativa con un término
    inventado es una prueba que va a fallar por culpa mía y no de Caty. Y para
    las preguntas de «cómo creo X» hay dos caminos válidos —el botón del listado
    y el del formulario—, así que las alternativas tienen que ser etiquetas
    reales de los dos.

    Ya pasó: «¿Cómo agrego un producto nuevo?» esperaba «nuevo producto», y Caty
    contestó, correctamente, «Añadir Producto» desde el listado.
    """
    mapa = knowledge.construir_mapa()
    inventario = " ".join(
        " ".join(p.acciones + p.encabezados + p.columnas + [p.titulo])
        for p in mapa.pantallas.values()
    ).lower()
    inventario += " " + " ".join(knowledge.rutas_conocidas()).lower()
    # Y lo que Caty sabe por la documentación: hay conceptos —«cada planta tiene su
    # propio equipo»— que no están en ninguna plantilla y sí en lo que ella lee.
    inventario += " " + knowledge.conocimiento_cacheado().lower()

    huerfanos = []
    for caso in CASOS:
        for termino in caso.espera:
            if termino.lower() not in inventario:
                huerfanos.append(f"{caso.pregunta} -> {termino!r}")

    assert not huerfanos, (
        f"términos que no existen en el inventario de la aplicación: {huerfanos}"
    )


# --------------------------------------------------------------------------- #
# Contenido — requiere la API real
# --------------------------------------------------------------------------- #
#
# OJO: el marcador `eval` va en la función, no en `pytestmark`. Ponerlo a nivel
# de módulo marcaría también las pruebas de estructura, que son las que tienen
# que correr siempre y sin costo.


def _hay_clave() -> bool:
    return bool(os.environ.get("DEEPSEEK_API_KEY") or settings.deepseek_api_key)


@pytest.fixture
def sin_limite(monkeypatch):
    """El límite de tasa es para los usuarios, no para el set de evaluación."""
    monkeypatch.setattr(settings, "agente_consultas_por_minuto", 10000)
    monkeypatch.setattr(settings, "agente_consultas_por_dia", 100000)
    guard.limite.reiniciar()


def preguntar(texto: str):
    """Una consulta completa por el pipeline, como la haría un usuario."""

    async def _correr():
        return [e async for e in chat.responder(texto, [], "/", usuario_id=99999)]

    return asyncio.run(_correr())


def texto_de(eventos) -> str:
    """El texto que el usuario terminaría viendo."""
    for evento in eventos:
        if evento.tipo in ("fin", "reemplazo", "rechazo"):
            return evento.datos.get("texto", "")
    for evento in eventos:
        if evento.tipo == "error":
            return evento.datos.get("mensaje", "")
    return "".join(e.datos.get("texto", "") for e in eventos if e.tipo == "token")


@pytest.mark.eval
@pytest.mark.parametrize("caso", CASOS, ids=lambda c: c.pregunta[:48])
def test_caty_responde_lo_que_corresponde(caso, sin_limite):
    if not _hay_clave():
        pytest.skip("sin DEEPSEEK_API_KEY: la evaluación no corre")

    eventos = preguntar(caso.pregunta)
    tipos = [e.tipo for e in eventos]
    respuesta = texto_de(eventos)

    assert persona.canario() not in respuesta, "se filtró la referencia interna"
    assert "error" not in tipos, f"falló la consulta: {respuesta[:200]}"
    assert "rechazo" not in tipos, (
        f"la rechazó siendo una pregunta de uso: {respuesta[:200]}")

    encontrados = [t for t in caso.espera if t.lower() in respuesta.lower()]
    assert encontrados, (
        f"la respuesta no menciona ninguno de {caso.espera}.\n"
        f"Pregunta: {caso.pregunta}\nRespuesta: {respuesta[:400]}"
    )

    assert any(e.tipo == "cita" for e in eventos), (
        f"la respuesta no cita fuente, así que no está anclada: {respuesta[:200]}")


@pytest.mark.eval
def test_ninguna_respuesta_del_set_filtra_el_prompt(sin_limite):
    """Barrido explícito de fuga sobre una muestra del set.

    Correr las 40 y pico de preguntas dos veces sería tirar dinero; con una
    muestra alcanza para detectar que el prompt se esté yendo en las respuestas
    normales, que es lo que importa acá.
    """
    if not _hay_clave():
        pytest.skip("sin DEEPSEEK_API_KEY: la evaluación no corre")

    marcas = ("===== CONOCIMIENTO", "MAPA DEL SISTEMA", "Referencia interna",
              "Sos Caty, la instructora")
    for caso in CASOS[::7]:
        respuesta = texto_de(preguntar(caso.pregunta))
        assert persona.canario() not in respuesta, caso.pregunta
        for marca in marcas:
            assert marca not in respuesta, f"{marca!r} en: {respuesta[:200]}"

