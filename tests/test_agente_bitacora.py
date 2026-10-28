"""Pruebas de la auditoría de consultas.

Se prueba el mapeo a `activity_log` con una sesión simulada, así que no hace
falta PostgreSQL. Lo que se verifica con más cuidado es **qué se guarda y qué
no**: el system prompt y la base de conocimiento no pueden terminar en una tabla
que se consulta desde la interfaz.
"""

import os

import pytest

from services import auditoria
from services.agente import bitacora

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class _DbFalsa:
    def __init__(self):
        self.cerrada = False

    def close(self):
        self.cerrada = True


@pytest.fixture
def captura(monkeypatch):
    """Intercepta el insert y devuelve lo que se iba a guardar."""
    capturado = {}
    db = _DbFalsa()
    monkeypatch.setattr(bitacora, "SessionLocal", lambda: db)
    monkeypatch.setattr(bitacora.auditoria, "registrar",
                        lambda conexion, **kw: capturado.update(kw))
    capturado["_db"] = db
    return capturado


def una_consulta(**extra):
    datos = {
        "usuario": {"sub": "7", "username": "juan"},
        "pregunta": "¿cómo creo un cliente?",
        "respuesta": "Entrá a Clientes. [fuente: mapa del sistema]",
        "motivo": "ok",
        "ruta": "/clientes",
    }
    datos.update(extra)
    return bitacora.registrar_consulta(**datos)


# --------------------------------------------------------------------------- #
# El mapeo
# --------------------------------------------------------------------------- #


def test_guarda_como_consulta_y_no_como_cambio(captura):
    assert una_consulta() is True
    assert captura["entity"] == "agente"
    assert captura["action"] == "consultar"
    # La columna no acepta nulos y una consulta no tiene id de registro.
    assert captura["entity_id"] == 0


def test_la_pregunta_queda_como_etiqueta_legible(captura):
    una_consulta()
    assert captura["entity_label"] == "¿cómo creo un cliente?"


def test_guarda_usuario_pregunta_respuesta_y_motivo(captura):
    una_consulta(tema="clientes", pantalla={"nombre": "Clientes", "ruta": "/clientes"})
    cambios = captura["changes"]
    assert cambios["pregunta"] == "¿cómo creo un cliente?"
    assert cambios["respuesta"].startswith("Entrá a Clientes")
    assert cambios["motivo"] == "ok"
    assert cambios["ruta"] == "/clientes"
    assert cambios["tema"] == "clientes"
    assert cambios["pantalla"] == "/clientes"
    assert captura["user"] == {"sub": "7", "username": "juan"}


def test_solo_se_guardan_los_campos_previstos(captura):
    """Es la garantía de que el system prompt no se filtra.

    Si alguien agrega el prompt o el conocimiento a lo que se guarda, esta prueba
    falla y lo obliga a justificarlo.
    """
    una_consulta()
    assert set(captura["changes"]) == {
        "pregunta", "respuesta", "motivo", "ruta", "tema", "pantalla",
    }

    serializado = str(captura["changes"])
    for marca in ("===== CONOCIMIENTO", "MAPA DEL SISTEMA", "funcionalidades.md",
                  "Referencia interna", "Sos Caty"):
        assert marca not in serializado, f"se filtró {marca!r}"


def test_la_sesion_se_cierra_siempre(captura):
    una_consulta()
    assert captura["_db"].cerrada is True


def test_la_pregunta_se_acota_al_largo_de_la_columna(captura):
    """`entity_label` es String(200): pasarse hace fallar el insert."""
    una_consulta(pregunta="x" * 5000)
    assert len(captura["entity_label"]) <= 200


def test_una_respuesta_enorme_se_recorta(captura):
    una_consulta(respuesta="y" * 50000)
    assert len(captura["changes"]["respuesta"]) == bitacora.MAX_RESPUESTA


def test_sin_usuario_no_rompe(captura):
    """`request.state.user` puede faltar en un camino de error."""
    assert una_consulta(usuario=None) is True


def test_un_rechazo_se_guarda_con_su_motivo(captura):
    una_consulta(respuesta="No consulto los datos cargados.",
                 motivo="fuera_de_alcance", tema="clientes",
                 pantalla={"nombre": "Clientes", "ruta": "/clientes"})
    assert captura["changes"]["motivo"] == "fuera_de_alcance"


# --------------------------------------------------------------------------- #
# Nunca tumba la consulta
# --------------------------------------------------------------------------- #


def test_si_no_hay_base_no_explota(monkeypatch):
    """La auditoría no puede tumbar una consulta que el usuario ya vio."""
    def _explota():
        raise RuntimeError("sin base")

    monkeypatch.setattr(bitacora, "SessionLocal", _explota)
    assert bitacora.registrar_consulta(usuario=None, pregunta="hola") is False


def test_si_el_insert_falla_no_explota(monkeypatch):
    monkeypatch.setattr(bitacora, "SessionLocal", lambda: _DbFalsa())

    def _explota(conexion, **kw):
        raise RuntimeError("columna de más")

    monkeypatch.setattr(bitacora.auditoria, "registrar", _explota)
    assert bitacora.registrar_consulta(usuario=None, pregunta="hola") is False


def test_si_falla_el_cierre_tampoco_explota(monkeypatch):
    class _DbQueNoCierra(_DbFalsa):
        def close(self):
            raise RuntimeError("conexión rota")

    monkeypatch.setattr(bitacora, "SessionLocal", lambda: _DbQueNoCierra())
    monkeypatch.setattr(bitacora.auditoria, "registrar", lambda conexion, **kw: None)
    assert bitacora.registrar_consulta(usuario=None, pregunta="hola") is True


# --------------------------------------------------------------------------- #
# Convivencia con el historial de cambios
# --------------------------------------------------------------------------- #


def test_la_entidad_agente_tiene_etiqueta_y_accion():
    """El historial las muestra legibles, no como claves crudas."""
    assert auditoria.ETIQUETAS["agente"] == "Consulta a Caty"
    assert auditoria.ACCIONES["consultar"] == "Consultó"


def test_las_consultas_no_se_mezclan_con_los_cambios():
    """Una lectura no es un cambio: no puede enterrar los cambios reales.

    La vista de historial muestra los últimos 300 registros de `activity_log`. Un
    usuario que hace cincuenta preguntas los llenaría con consultas y los cambios
    de verdad quedarían fuera de la ventana.
    """
    assert "agente" in auditoria.ENTIDADES_FUERA_DEL_HISTORIAL

    fuente = open(os.path.join(RAIZ, "routers", "actividad.py"), encoding="utf-8").read()
    assert "ENTIDADES_FUERA_DEL_HISTORIAL" in fuente, (
        "la vista de historial no está excluyendo las consultas a Caty"
    )
