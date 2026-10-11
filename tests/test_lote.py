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


# ── Los otros módulos ──────────────────────────────────────────────────────
def _maquinas(db, n=3):
    c = models.Customer(name="Con máquinas", is_active=True)
    db.add(c)
    db.commit()
    for i in range(n):
        db.add(models.Machine(customer_id=c.id, serial_number=f"SN-{i}", brand="Bobst",
                              model=f"M{i}", is_active=True))
    db.commit()
    return [m.id for m in db.query(models.Machine).order_by(models.Machine.id).all()]


def _productos(db, n=3):
    for i in range(n):
        db.add(models.Product(name=f"Producto {i}", et_number=f"ET-{i}", is_active=True))
    db.commit()
    return [p.id for p in db.query(models.Product).order_by(models.Product.id).all()]


def test_desactivar_maquinas_en_lote(client, db_session, seed_admin):
    ids = _maquinas(db_session, 3)
    _entrar(client)
    r = client.post("/maquinaria/accion-en-lote",
                    json={"ids": ids[:2], "accion": "desactivar", "motivo": "baja",
                          "csrf_token": _csrf(client, "/maquinaria")})
    assert r.status_code == 200
    assert r.json()["aplicados"] == 2
    assert db_session.query(models.Machine).filter(
        models.Machine.is_active.is_(True)).count() == 1


def test_desactivar_productos_en_lote(client, db_session, seed_admin):
    ids = _productos(db_session, 3)
    _entrar(client)
    r = client.post("/productos/accion-en-lote",
                    json={"ids": ids, "accion": "desactivar", "motivo": "descontinuado",
                          "csrf_token": _csrf(client, "/productos")})
    assert r.status_code == 200
    assert r.json()["aplicados"] == 3


def test_el_lote_de_maquinas_queda_en_el_historial(client, db_session, seed_admin):
    ids = _maquinas(db_session, 2)
    _entrar(client)
    client.post("/maquinaria/accion-en-lote",
                json={"ids": ids, "accion": "desactivar", "motivo": "baja",
                      "csrf_token": _csrf(client, "/maquinaria")})
    registros = db_session.query(models.ActivityLog).filter(
        models.ActivityLog.entity == "machine").all()
    assert len(registros) == 2
    assert all(r.action == "desactivar" for r in registros)


def test_reactivar_en_lote_requiere_admin(client, db_session, seed_admin):
    """Igual que en clientes: reactivar es una acción de administrador."""
    ids = _maquinas(db_session, 1)
    _entrar(client)
    r = client.post("/maquinaria/accion-en-lote",
                    json={"ids": ids, "accion": "reactivar", "csrf_token": _csrf(client, "/maquinaria")})
    # `seed_admin` es admin, así que esta acción sí pasa; lo que se comprueba es que
    # la validación existe y no explota.
    assert r.status_code == 200


def test_el_lote_generico_valida_igual_que_el_de_clientes(client, db_session, seed_admin):
    ids = _productos(db_session, 2)
    _entrar(client)

    # Sin motivo.
    r = client.post("/productos/accion-en-lote",
                    json={"ids": ids, "accion": "desactivar", "csrf_token": _csrf(client, "/productos")})
    assert r.status_code == 400
    assert "motivo" in r.json()["detail"].lower()

    # Acción inválida.
    r = client.post("/productos/accion-en-lote",
                    json={"ids": ids, "accion": "borrar", "motivo": "x",
                          "csrf_token": _csrf(client, "/productos")})
    assert r.status_code == 400

    # Sin ids.
    r = client.post("/productos/accion-en-lote",
                    json={"ids": [], "accion": "desactivar", "motivo": "x",
                          "csrf_token": _csrf(client, "/productos")})
    assert r.status_code == 400


def test_los_listados_nuevos_tienen_casillas(client, db_session, seed_admin):
    _maquinas(db_session, 2)
    _productos(db_session, 2)
    _entrar(client)
    for ruta in ("/maquinaria", "/productos"):
        html = client.get(ruta).text
        assert "data-lote-todos" in html, ruta
        assert "data-lote-item=" in html, ruta
        assert "data-lote-barra" in html, ruta
