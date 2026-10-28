"""Pruebas del historial de cambios.

Lo que más importa verificar no es que se registre algo, sino **qué** se registra:
que guarde las diferencias campo por campo —y no el registro entero—, que no anote
como cambio lo que no cambió, y que un fallo del historial no tumbe la operación
del usuario.
"""

import datetime
import os

import models
from tests import apoyo
from services import auditoria

# Ruta a las plantillas, para las pruebas que revisan el marcado.
PLANTILLAS = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                          "templates")


def _csrf(client, ruta=None):
    """Token CSRF de la sesión.

    El token es por usuario, así que sirve el de cualquier página que tenga un
    formulario. Se prueban varias porque no todas lo incluyen, y buscar en la
    equivocada devolvía vacío y el POST fallaba por CSRF.
    """
    import re
    candidatas = [ruta] if ruta else []
    candidatas += ["/clientes", "/nuevo-cliente", "/maquinaria", "/nuevo-producto",
                   "/minutas", "/visitas2", "/productos"]
    for r in candidatas:
        if not r:
            continue
        try:
            html = client.get(r).text
        except Exception:
            continue
        m = re.search(r'name="csrf_token" value="([^"]+)"', html)
        if m:
            return m.group(1)
    return ""


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
        "team_id": apoyo.equipo_de_prueba_id(),
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
        "team_id": apoyo.equipo_de_prueba_id(),
        "address": "Calle 1", "city": "Rosario", "status": "Activo"})

    cid = db_session.query(models.Customer).filter_by(name="Editable SA").first().id
    client.post(f"/editar-cliente/{cid}", data={
        "csrf_token": _csrf(client),
        "name": "Editable SA", "plant": "Planta 9", "industry_sector": "Corrugado",
        "team_id": apoyo.equipo_de_prueba_id(),
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
             "team_id": apoyo.equipo_de_prueba_id(),
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


# ── Los otros módulos ──────────────────────────────────────────────────────
def _csrf_de(client, ruta):
    return _csrf(client, ruta)


def test_editar_una_maquina_registra_la_diferencia(client, db_session, seed_admin):
    _entrar(client)
    c = models.Customer(name="Con máquina", is_active=True)
    db_session.add(c)
    db_session.commit()
    m = models.Machine(customer_id=c.id, serial_number="SN-1", brand="Bobst",
                       model="X5", plant_assigned="P1", machine_type="Impresora",
                       line="L1", status="Operativo", is_active=True)
    db_session.add(m)
    db_session.commit()

    client.post(f"/editar-maquinaria/{m.id}", data={
        "csrf_token": _csrf_de(client, "/maquinaria"),
        "customer_id": c.id, "serial_number": "SN-1", "brand": "Bobst",
        "model_name": "X9", "plant_assigned": "Planta 2", "machine_type": "Impresora",
        "line": "L1", "status": "Operativo"})

    r = db_session.query(models.ActivityLog).filter(
        models.ActivityLog.entity == "machine",
        models.ActivityLog.action == "editar").first()
    assert r is not None
    assert "model" in r.changes or "plant_assigned" in r.changes


def test_crear_un_producto_queda_registrado(client, db_session, seed_admin):
    _entrar(client)
    client.post("/nuevo-producto", data={
        "csrf_token": _csrf_de(client, "/productos"),
        "name": "Caja prueba", "et_number": "ET-1", "material": "Corrugado",
        "manufacturing_route": "R1", "dimensions_l": 10, "dimensions_a": 10,
        "dimensions_h": 10, "status": "Activo"})
    r = db_session.query(models.ActivityLog).filter(
        models.ActivityLog.entity == "product").first()
    assert r is not None
    assert r.action == "crear"
    assert r.entity_label == "Caja prueba"


def test_editar_una_minuta_registra_dentro_del_json(client, db_session, seed_admin):
    """Las minutas guardan todo en `form_data`: hay que ver qué campo cambió."""
    _entrar(client)
    m = models.MeetingMinutes(fecha="2026-05-10", status="Borrador", is_active=True,
                              form_data={"objetivo": "Comité mensual", "tipoReunion": "Seguimiento"})
    db_session.add(m)
    db_session.commit()

    client.post(f"/minutas/{m.id}/editar", data={
        "csrf_token": _csrf_de(client, "/minutas"),
        "form_data": '{"objetivo": "Comité de calidad", "tipoReunion": "Seguimiento", "fecha": "2026-05-10", "status": "Borrador"}'})

    r = db_session.query(models.ActivityLog).filter(
        models.ActivityLog.entity == "minute",
        models.ActivityLog.action == "editar").first()
    assert r is not None
    # El campo se nombra `form_data.<clave>`, no "(2 elementos)".
    assert "form_data.objetivo" in r.changes
    assert r.changes["form_data.objetivo"]["antes"] == "Comité mensual"
    assert r.changes["form_data.objetivo"]["despues"] == "Comité de calidad"


def test_crear_una_minuta_queda_registrada(client, db_session, seed_admin):
    _entrar(client)
    client.post("/minutas/nueva", data={
        "csrf_token": _csrf_de(client, "/minutas"),
        "form_data": '{"objetivo": "Reunión inicial", "fecha": "2026-05-10", "status": "Borrador"}'})
    r = db_session.query(models.ActivityLog).filter(
        models.ActivityLog.entity == "minute").first()
    assert r is not None and r.action == "crear"


def test_borrar_una_minuta_queda_registrado(client, db_session, seed_admin):
    _entrar(client)
    m = models.MeetingMinutes(fecha="2026-05-10", status="Borrador", is_active=True,
                              form_data={"objetivo": "Para borrar"})
    db_session.add(m)
    db_session.commit()
    mid = m.id

    client.post(f"/eliminar-minuta/{mid}", data={"csrf_token": _csrf_de(client, "/minutas")})
    r = db_session.query(models.ActivityLog).filter(
        models.ActivityLog.entity == "minute",
        models.ActivityLog.action == "eliminar",
        models.ActivityLog.entity_id == mid).first()
    assert r is not None


def test_el_historial_cubre_todas_las_entidades_esperadas():
    """Si se agrega auditoría en un módulo nuevo, esto falla si falta la etiqueta."""
    for entidad in ("customer", "machine", "product", "visit", "minute"):
        assert entidad in auditoria.ETIQUETAS, f"falta la etiqueta de {entidad}"


def test_los_listados_tienen_el_boton_de_historial():
    """El botón abre el modal con `data-historial="entidad:id"`."""
    import glob as glob_module
    esperados = {
        "clientes.html": "customer:",
        "maquinaria.html": "machine:",
        "productos.html": "product:",
        "minutas_lista.html": "minute:",
        "visitas2_lista.html": "visit:",
    }
    faltan = []
    for archivo, prefijo in esperados.items():
        ruta = os.path.join(PLANTILLAS, archivo)
        with open(ruta, encoding="utf-8") as fh:
            texto = fh.read()
        if f'data-historial="{prefijo}' not in texto:
            faltan.append(archivo)
    assert not faltan, f"listados sin botón de historial: {faltan}"


def test_las_plantillas_del_historial_usan_la_variable_correcta():
    """El botón tiene que referirse a la variable del `for`, no a un nombre inventado.

    Al insertarlo usé `minuta.id` y `visita.id` cuando los bucles usan `m` y `v`, y
    las páginas devolvían 500.
    """
    import glob as glob_module
    problemas = []
    for ruta in glob_module.glob(os.path.join(PLANTILLAS, "*.html")):
        with open(ruta, encoding="utf-8") as fh:
            texto = fh.read()
        if "data-historial=" not in texto:
            continue
        # La variable del bucle en esa plantilla.
        import re as re_mod
        variables = set(re_mod.findall(r"{%-?\s*for\s+(\w+)\s+in\s", texto))
        usadas = set(re_mod.findall(r'data-historial="[a-z_]+:\{\{\s*(\w+)\.', texto))
        if usadas and not usadas <= variables:
            problemas.append(f"{os.path.basename(ruta)}: usa {sorted(usadas - variables)}, "
                             f"los bucles definen {sorted(variables)}")
    assert not problemas, f"botones de historial con variable inexistente: {problemas}"


def test_el_pie_del_modal_de_historial_esta_dentro_del_modal():
    """El pie tiene que ir dentro del bloque `call modal()`, no después.

    Fuera del modal, los botones quedan colgando al final de la página.
    """
    ruta = os.path.join(PLANTILLAS, "layout.html")
    with open(ruta, encoding="utf-8") as fh:
        texto = fh.read()
    import re as re_mod
    bloque = re_mod.search(r"call modal\('modalHistorial'.*?endcall", texto, re_mod.S)
    assert bloque, "no se encontró el modal de historial"
    assert "call pie_modal" in bloque.group(0), "el pie quedó fuera del modal"


def test_el_contenido_del_historial_no_pisa_el_pie():
    """`abrirHistorial()` escribe sobre un div interno, no sobre el cuerpo del modal.

    Escribir sobre `-cuerpo` borraba el pie de botones, porque el pie vive ahí
    adentro. El botón desaparecía al cargar el historial.
    """
    with open(os.path.join(PLANTILLAS, "layout.html"), encoding="utf-8") as fh:
        layout = fh.read()
    assert 'id="historialContenido"' in layout

    raiz = os.path.dirname(PLANTILLAS)
    with open(os.path.join(raiz, "static/js/app.js"), encoding="utf-8") as fh:
        js = fh.read()
    assert "getElementById('historialContenido')" in js
    assert "getElementById('modalHistorial-cuerpo')" not in js
