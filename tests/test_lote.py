"""Pruebas de las acciones en lote.

Desactivar veinte clientes de a uno es la clase de tarea que hace que la gente deje
de usar la herramienta. Lo que más importa verificar no es que aplique la acción,
sino que **informe bien lo que no hizo**: si tres de veinte no se pudieron, hay que
poder decirlo en lugar de devolver un "ok" que oculte el problema.
"""

import models


def _clientes(db, n=3):
    for i in range(n):
        db.add(models.Customer(name=f"Lote {i}", is_active=True, status="Activo"))
    db.commit()
    return [c.id for c in db.query(models.Customer).order_by(models.Customer.name).all()]


def _csrf(client, ruta="/clientes"):
    import re
    html = client.get(ruta).text
    m = re.search(r'name="csrf_token" value="([^"]*)"', html)
    return m.group(1) if m else ""


def _entrar(client):
    client.post("/auth/login", data={"username": "admin", "password": "admin123"})


def test_desactivar_varios_clientes(client, db_session, seed_admin):
    ids = _clientes(db_session, 3)
    _entrar(client)
    r = client.post("/clientes/accion-en-lote",
                    json={"ids": ids[:2], "accion": "desactivar", "motivo": "sin actividad",
                          "csrf_token": _csrf(client)})
    assert r.status_code == 200
    datos = r.json()
    assert datos["aplicados"] == 2
    assert datos["omitidos"] == []

    activos = db_session.query(models.Customer).filter(
        models.Customer.is_active.is_(True)).count()
    assert activos == 1


def test_guardar_el_motivo_de_la_desactivacion(client, db_session, seed_admin):
    ids = _clientes(db_session, 1)
    _entrar(client)
    client.post("/clientes/accion-en-lote",
                json={"ids": ids, "accion": "desactivar", "motivo": "fusionado con otro",
                      "csrf_token": _csrf(client)})
    c = db_session.query(models.Customer).first()
    assert c.is_active is False
    assert "fusionado" in (c.inactivation_reason or "")


def test_informa_los_que_ya_estaban_en_ese_estado(client, db_session, seed_admin):
    """No es un error, pero hay que decirlo: el usuario eligió algo que no cambió."""
    ids = _clientes(db_session, 3)
    _entrar(client)
    client.post("/clientes/accion-en-lote",
                json={"ids": ids[:2], "accion": "desactivar", "motivo": "prueba", "csrf_token": _csrf(client)})

    r = client.post("/clientes/accion-en-lote",
                    json={"ids": ids, "accion": "desactivar", "motivo": "prueba", "csrf_token": _csrf(client)})
    datos = r.json()
    assert datos["aplicados"] == 1
    assert len(datos["omitidos"]) == 2
    assert "ya estaba inactivo" in datos["omitidos"][0]["motivo"]


def test_informa_los_que_no_existen(client, db_session, seed_admin):
    _entrar(client)
    r = client.post("/clientes/accion-en-lote",
                    json={"ids": [999999], "accion": "desactivar", "motivo": "prueba", "csrf_token": _csrf(client)})
    assert r.status_code == 200
    datos = r.json()
    assert datos["aplicados"] == 0
    assert "no existe" in datos["omitidos"][0]["motivo"]


def test_reactivar(client, db_session, seed_admin):
    ids = _clientes(db_session, 2)
    _entrar(client)
    client.post("/clientes/accion-en-lote",
                json={"ids": ids, "accion": "desactivar", "motivo": "prueba", "csrf_token": _csrf(client)})
    r = client.post("/clientes/accion-en-lote",
                    json={"ids": ids, "accion": "reactivar", "csrf_token": _csrf(client)})
    assert r.json()["aplicados"] == 2
    assert db_session.query(models.Customer).filter(
        models.Customer.is_active.is_(True)).count() == 2


def test_una_accion_invalida_se_rechaza(client, db_session, seed_admin):
    ids = _clientes(db_session, 1)
    _entrar(client)
    r = client.post("/clientes/accion-en-lote",
                    json={"ids": ids, "accion": "borrar_todo", "csrf_token": _csrf(client)})
    assert r.status_code == 400


def test_sin_ids_se_rechaza(client, db_session, seed_admin):
    _entrar(client)
    r = client.post("/clientes/accion-en-lote",
                    json={"ids": [], "accion": "desactivar", "motivo": "prueba", "csrf_token": _csrf(client)})
    assert r.status_code == 400


def test_ids_no_numericos_se_rechazan(client, db_session, seed_admin):
    _entrar(client)
    r = client.post("/clientes/accion-en-lote",
                    json={"ids": ["a; DROP TABLE customers"], "accion": "desactivar", "motivo": "prueba",
                          "csrf_token": _csrf(client)})
    assert r.status_code == 400
    # Y la tabla sigue ahí.
    assert db_session.query(models.Customer).count() == 0


def test_requiere_autenticacion(client, db_session):
    ids = _clientes(db_session, 1)
    r = client.post("/clientes/accion-en-lote",
                    json={"ids": ids, "accion": "desactivar"}, follow_redirects=False)
    assert r.status_code == 303


def test_la_columna_de_casillas_esta_en_el_listado(client, db_session, seed_admin):
    _clientes(db_session, 2)
    _entrar(client)
    html = client.get("/clientes").text
    assert "data-lote-todos" in html
    assert "data-lote-item=" in html
    assert "data-lote-barra" in html


def test_la_barra_empieza_oculta(client, db_session, seed_admin):
    """La barra sólo aparece al elegir algo."""
    _clientes(db_session, 2)
    _entrar(client)
    html = client.get("/clientes").text
    import re
    m = re.search(r'<div data-lote-barra[^>]*>', html)
    assert m and "hidden" in m.group(0)


def test_desactivar_sin_motivo_se_rechaza_de_entrada(client, db_session, seed_admin):
    """Es mejor decirlo una vez que devolver veinte filas omitidas por lo mismo.

    La desactivación individual ya exigía el motivo; el lote tiene que ser
    consistente con eso.
    """
    ids = _clientes(db_session, 3)
    _entrar(client)
    r = client.post("/clientes/accion-en-lote",
                    json={"ids": ids, "accion": "desactivar", "csrf_token": _csrf(client)})
    assert r.status_code == 400
    assert "motivo" in r.json()["detail"].lower()
    # Y no se desactivó ninguno.
    assert db_session.query(models.Customer).filter(
        models.Customer.is_active.is_(True)).count() == 3
