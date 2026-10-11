"""Pruebas del historial de cambios.

Lo que más importa verificar no es que se registre algo, sino **qué** se registra:
que guarde las diferencias campo por campo —y no el registro entero—, que no anote
como cambio lo que no cambió, y que un fallo del historial no tumbe la operación
del usuario.
"""

import datetime

import models
from services import auditoria


def _csrf(client, ruta="/clientes"):
    import re
    html = client.get(ruta).text
    m = re.search(r'name="csrf_token" value="([^"]*)"', html)
    return m.group(1) if m else ""


def _entrar(client):
    client.post("/auth/login", data={"username": "admin", "password": "admin123"})


# ── Diferencias ────────────────────────────────────────────────────────────
def test_solo_se_registran_los_campos_que_cambiaron():
    antes = {"name": "Cartocor SA", "plant": "Planta 1", "city": "Rosario"}
    despues = {"name": "Cartocor SA", "plant": "Planta 2", "city": "Rosario"}
    cambios = auditoria.diferencias(antes, despues)
    assert list(cambios.keys()) == ["plant"]
    assert cambios["plant"]["antes"] == "Planta 1"
    assert cambios["plant"]["despues"] == "Planta 2"


def test_los_campos_tecnicos_no_ensucian_el_historial():
    """`updated_at` cambia en cada edición y no es un cambio del usuario."""
    antes = {"name": "A", "updated_at": "2026-01-01", "id": 1}
    despues = {"name": "A", "updated_at": "2026-06-01", "id": 1}
    assert auditoria.diferencias(antes, despues) == {}


def test_los_valores_se_muestran_legibles():
    antes = {"is_active": True, "observations": None}
    despues = {"is_active": False, "observations": "algo"}
    cambios = auditoria.diferencias(antes, despues)
    assert cambios["is_active"]["antes"] == "sí"
    assert cambios["is_active"]["despues"] == "no"
    assert cambios["observations"]["antes"] == "vacío"


def test_un_texto_muy_largo_se_recorta():
    cambios = auditoria.diferencias({"obs": ""}, {"obs": "x" * 200})
    assert len(cambios["obs"]["despues"]) <= 60
    assert cambios["obs"]["despues"].endswith("…")


def test_espacios_vs_vacio_no_es_un_cambio():
    cambios = auditoria.diferencias({"city": "  "}, {"city": ""})
    assert cambios == {}


def test_sin_registro_previo_no_hay_diferencias():
    assert auditoria.diferencias({}, {"name": "x"}) == {}
    assert auditoria.diferencias(None, {"name": "x"}) == {}


def test_snapshot_toma_las_columnas_del_modelo():
    c = models.Customer(name="Prueba", plant="P1", is_active=True)
    datos = auditoria.snapshot(c)
    assert datos["name"] == "Prueba"
    assert "inactivation_reason" in datos
    assert auditoria.snapshot(None) == {}


# ── Registro ───────────────────────────────────────────────────────────────
def test_registrar_guarda_usuario_y_nombre(db_session):
    auditoria.registrar(db_session, "customer", 1, "crear",
                        user={"sub": "7", "username": "juan"},
                        entity_label="Cartocor SA")
    r = db_session.query(models.ActivityLog).first()
    assert r.user_id == 7
    assert r.username == "juan"
    assert r.entity == "customer"
    assert r.entity_id == 1
    assert r.action == "crear"


def test_el_registro_sobrevive_a_la_eliminacion_del_usuario(db_session):
    """Por eso se guarda el nombre además del id."""
    auditoria.registrar(db_session, "customer", 1, "crear",
                        user={"sub": "99", "username": "alguien"})
    db_session.query(models.User).filter(models.User.id == 99).delete()
    db_session.commit()
    r = db_session.query(models.ActivityLog).first()
    assert r.username == "alguien"


def test_un_fallo_del_historial_no_tumba_la_operacion(db_session):
    """Si el historial falla, el cambio del usuario igual se guarda."""
    # Un objeto que revienta al accederse, para forzar el fallo dentro de registrar.
    class Roto:
        def __getattr__(self, nombre):
            raise RuntimeError("falla simulada")

    resultado = auditoria.registrar(db_session, "customer", 1, "crear", user=Roto())
    assert resultado is None  # no propaga la excepción


def test_historial_de_un_registro(db_session):
    for i in range(3):
        auditoria.registrar(db_session, "customer", 1, "editar",
                            user={"sub": "1", "username": "admin"},
                            changes={"plant": {"antes": f"P{i}", "despues": f"P{i+1}"}})
    auditoria.registrar(db_session, "customer", 2, "crear", user={"sub": "1", "username": "admin"})

    registros = auditoria.historial(db_session, "customer", 1)
    assert len(registros) == 3
    # Del más reciente al más viejo.
    assert registros[0].changes["plant"]["despues"] == "P3"


def test_resumen_legible(db_session):
    auditoria.registrar(db_session, "customer", 1, "editar",
                        entity_label="Cartocor SA",
                        changes={"plant": {"antes": "P1", "despues": "P2"}})
    r = db_session.query(models.ActivityLog).first()
    texto = auditoria.resumen(r)
    assert "Editó" in texto
    assert "Cartocor SA" in texto
    assert "plant" in texto


# ── El flujo real ──────────────────────────────────────────────────────────
def test_crear_un_cliente_queda_registrado(client, db_session, seed_admin):
    _entrar(client)
    client.post("/nuevo-cliente", data={
        "csrf_token": _csrf(client, "/nuevo-cliente"),
        "name": "Historial SA", "plant": "P1", "industry_sector": "Corrugado",
        "assigned_commercial": "A", "technical_advisor": "ING. X", "designer": "D",
        "address": "Calle 1", "city": "Rosario", "status": "Activo"})

    r = db_session.query(models.ActivityLog).filter(
        models.ActivityLog.action == "crear").first()
    assert r is not None
    assert r.entity_label == "Historial SA"
    assert r.username == "admin"


def test_editar_un_cliente_registra_la_diferencia(client, db_session, seed_admin):
    _entrar(client)
    client.post("/nuevo-cliente", data={
        "csrf_token": _csrf(client, "/nuevo-cliente"),
        "name": "Editable SA", "plant": "P1", "industry_sector": "Corrugado",
        "assigned_commercial": "A", "technical_advisor": "ING. X", "designer": "D",
        "address": "Calle 1", "city": "Rosario", "status": "Activo"})

    cid = db_session.query(models.Customer).filter_by(name="Editable SA").first().id
    client.post(f"/editar-cliente/{cid}", data={
        "csrf_token": _csrf(client),
        "name": "Editable SA", "plant": "Planta 9", "industry_sector": "Corrugado",
        "assigned_commercial": "A", "technical_advisor": "ING. X", "designer": "D",
        "address": "Calle 1", "city": "Rosario", "status": "Activo"})

    r = db_session.query(models.ActivityLog).filter(
        models.ActivityLog.action == "editar",
        models.ActivityLog.entity_id == cid).first()
    assert r is not None
    assert list(r.changes.keys()) == ["plant"]
    assert r.changes["plant"]["despues"] == "Planta 9"


def test_editar_sin_cambios_no_registra_nada(client, db_session, seed_admin):
    """Abrir el formulario y guardar sin tocar nada no es un cambio."""
    _entrar(client)
    datos = {"name": "Sin cambios SA", "plant": "P1", "industry_sector": "Corrugado",
             "assigned_commercial": "A", "technical_advisor": "ING. X", "designer": "D",
             "address": "Calle 1", "city": "Rosario", "status": "Activo"}
    client.post("/nuevo-cliente", data={"csrf_token": _csrf(client, "/nuevo-cliente"), **datos})
    cid = db_session.query(models.Customer).filter_by(name="Sin cambios SA").first().id

    antes = db_session.query(models.ActivityLog).count()
    client.post(f"/editar-cliente/{cid}", data={"csrf_token": _csrf(client), **datos})
    assert db_session.query(models.ActivityLog).count() == antes


def test_la_pagina_de_historial_carga(client, db_session, seed_admin):
    _entrar(client)
    auditoria.registrar(db_session, "customer", 1, "crear",
                        user={"sub": "1", "username": "admin"}, entity_label="X SA")
    r = client.get("/historial-cambios")
    assert r.status_code == 200
    assert "X SA" in r.text
    assert "Creó" in r.text


def test_la_pagina_filtra_por_accion(client, db_session, seed_admin):
    _entrar(client)
    auditoria.registrar(db_session, "customer", 1, "crear",
                        user={"sub": "1", "username": "admin"}, entity_label="Alta SA")
    auditoria.registrar(db_session, "customer", 2, "editar",
                        user={"sub": "1", "username": "admin"}, entity_label="Editado SA")
    r = client.get("/historial-cambios?accion=editar")
    assert "Editado SA" in r.text
    assert "Alta SA" not in r.text


def test_la_api_devuelve_el_historial_de_un_registro(client, db_session, seed_admin):
    _entrar(client)
    auditoria.registrar(db_session, "customer", 5, "editar",
                        user={"sub": "1", "username": "admin"}, entity_label="Con historial",
                        changes={"plant": {"antes": "P1", "despues": "P2"}})
    r = client.get("/api/historial/customer/5")
    assert r.status_code == 200
    datos = r.json()
    assert datos["entity_id"] == 5
    assert datos["registros"][0]["cambios"]["plant"]["despues"] == "P2"


def test_la_pagina_avisa_cuando_no_hay_nada(client, db_session, seed_admin):
    _entrar(client)
    r = client.get("/historial-cambios")
    assert r.status_code == 200
    assert "Todavía no hay cambios" in r.text
