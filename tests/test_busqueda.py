"""Pruebas de la búsqueda transversal.

Busca en cuatro entidades a la vez. Lo que importa verificar es que encuentre por
los campos correctos (las visitas y las minutas guardan casi todo en `form_data`,
que es un JSON) y que una entidad que falla no tumbe las otras tres.
"""

import models
from services import busqueda


def _cliente(db, nombre, **extra):
    c = models.Customer(name=nombre, is_active=True, status="Activo", **extra)
    db.add(c)
    db.commit()
    return c


def _visita(db, cliente, at="ING. GOMEZ", objetivo="Seguimiento"):
    v = models.TechnicalVisit2(
        fecha="2026-05-10", status="Finalizado", is_active=True,
        form_data={"cliente_nombre": cliente, "at": at, "objetivo": objetivo})
    db.add(v)
    db.commit()
    return v


def _maquina(db, cliente_id, **extra):
    m = models.Machine(customer_id=cliente_id, is_active=True, **extra)
    db.add(m)
    db.commit()
    return m


def _minuta(db, objetivo, tipo="Seguimiento"):
    m = models.MeetingMinutes(
        fecha="2026-05-10", status="Borrador", is_active=True,
        form_data={"objetivo": objetivo, "tipoReunion": tipo})
    db.add(m)
    db.commit()
    return m


def _claves(grupos):
    return {g["clave"] for g in grupos}


# ── Búsqueda por entidad ───────────────────────────────────────────────────
def test_encuentra_un_cliente_por_nombre(db_session):
    _cliente(db_session, "Cartocor SA", plant="Planta 1", city="Rosario")
    grupos, total = busqueda.buscar(db_session, "cartocor")
    assert total == 1
    assert "clientes" in _claves(grupos)
    g = next(g for g in grupos if g["clave"] == "clientes")
    assert g["resultados"][0]["titulo"] == "Cartocor SA"


def test_encuentra_un_cliente_por_ciudad_o_planta(db_session):
    """No sólo por nombre: también por planta, ciudad, sector o asesor."""
    _cliente(db_session, "Otra SA", city="Rafaela")
    _cliente(db_session, "Otra Dos SA", plant="Planta Norte")

    for consulta in ("Rafaela", "Planta Norte"):
        grupos, total = busqueda.buscar(db_session, consulta)
        assert total == 1, consulta
        assert "clientes" in _claves(grupos)


def test_encuentra_una_visita_por_su_form_data(db_session):
    """Las visitas guardan el cliente y el objetivo dentro de form_data (JSON)."""
    _visita(db_session, "Cartocor SA", objetivo="Análisis No conformidad")
    grupos, _ = busqueda.buscar(db_session, "No conformidad")
    assert "visitas" in _claves(grupos)
    g = next(g for g in grupos if g["clave"] == "visitas")
    assert "Cartocor SA" in g["resultados"][0]["detalle"]


def test_encuentra_una_maquina_por_numero_de_serie(db_session):
    c = _cliente(db_session, "Con máquinas")
    _maquina(db_session, c.id, brand="Bobst", model="X5", serial_number="SN-9911")
    grupos, _ = busqueda.buscar(db_session, "SN-9911")
    assert "maquinas" in _claves(grupos)


def test_encuentra_una_minuta_por_objetivo(db_session):
    _minuta(db_session, "Comité de calidad mensual")
    grupos, _ = busqueda.buscar(db_session, "Comité")
    assert "minutas" in _claves(grupos)


def test_la_busqueda_cruza_los_cuatro_modulos(db_session):
    """Un mismo texto puede estar en varias entidades a la vez."""
    c = _cliente(db_session, "Cartocor SA")
    _visita(db_session, "Cartocor SA")
    _maquina(db_session, c.id, brand="Cartocor", model="Especial")
    _minuta(db_session, "Visita a Cartocor")

    grupos, total = busqueda.buscar(db_session, "Cartocor")
    assert _claves(grupos) == {"clientes", "visitas", "maquinas", "minutas"}
    assert total == 4


# ── Casos límite ───────────────────────────────────────────────────────────
def test_una_sola_letra_no_busca(db_session):
    """Con una letra coincide todo y el resultado no ayuda a decidir."""
    _cliente(db_session, "Cartocor SA")
    grupos, total = busqueda.buscar(db_session, "a")
    assert grupos == [] and total == 0


def test_consulta_vacia(db_session):
    _cliente(db_session, "Cartocor SA")
    grupos, total = busqueda.buscar(db_session, "")
    assert grupos == [] and total == 0
    grupos, total = busqueda.buscar(db_session, "   ")
    assert grupos == [] and total == 0


def test_una_entidad_que_falla_no_tumba_las_demas(db_session, monkeypatch):
    """Si una consulta revienta, las otras tres igual devuelven resultados."""
    _cliente(db_session, "Cartocor SA")

    def _explota(db, q):
        raise RuntimeError("falla simulada")

    original = busqueda.GRUPOS
    busqueda.GRUPOS = [
        ("clientes", "Clientes", busqueda._buscar_clientes, "/clientes?q={q}"),
        ("visitas", "Visitas", _explota, "/visitas2?q={q}"),
    ]
    try:
        grupos, total = busqueda.buscar(db_session, "Cartocor")
        assert "clientes" in _claves(grupos)
        assert "visitas" not in _claves(grupos)
        assert total == 1
    finally:
        busqueda.GRUPOS = original


def test_los_clientes_inactivos_no_aparecen(db_session):
    db_session.add(models.Customer(name="Dado de baja SA", is_active=False))
    db_session.commit()
    grupos, total = busqueda.buscar(db_session, "Dado de baja")
    assert total == 0


def test_cada_grupo_trae_el_enlace_para_ver_todos(db_session):
    _cliente(db_session, "Cartocor SA")
    grupos, _ = busqueda.buscar(db_session, "Cartocor")
    g = grupos[0]
    assert g["enlace_todos"].startswith("/clientes?q=")
    assert "Cartocor" in g["enlace_todos"]


# ── La página ──────────────────────────────────────────────────────────────
def test_la_busqueda_pide_autenticacion(client):
    r = client.get("/buscar?q=algo", follow_redirects=False)
    assert r.status_code == 303


def test_la_pagina_de_busqueda_carga(client, db_session, seed_admin):
    client.post("/auth/login", data={"username": "admin", "password": "admin123"})
    r = client.get("/buscar")
    assert r.status_code == 200
    assert "Buscar" in r.text
    # Sin consulta, explica qué hace en lugar de mostrar una tabla vacía.
    assert "al menos dos letras" in r.text


def test_la_pagina_muestra_los_resultados(client, db_session, seed_admin):
    _cliente(db_session, "Cartocor SA", plant="Planta 1")
    client.post("/auth/login", data={"username": "admin", "password": "admin123"})
    r = client.get("/buscar?q=Cartocor")
    assert r.status_code == 200
    assert "Cartocor SA" in r.text
    assert "Resultados para" in r.text


def test_la_pagina_avisa_cuando_no_hay_nada(client, db_session, seed_admin):
    client.post("/auth/login", data={"username": "admin", "password": "admin123"})
    r = client.get("/buscar?q=zzzznoexiste")
    assert r.status_code == 200
    assert "No se encontró nada" in r.text


def test_la_caja_de_busqueda_esta_en_la_barra(client, db_session, seed_admin):
    """La caja tiene que estar en todas las páginas, no sólo en la de búsqueda."""
    client.post("/auth/login", data={"username": "admin", "password": "admin123"})
    r = client.get("/clientes")
    assert 'action="/buscar"' in r.text
    assert 'id="busqueda-global"' in r.text
