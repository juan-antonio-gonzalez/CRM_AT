"""Pruebas del módulo de clientes: ciclo completo y equipo del cliente.

Es el módulo más grande de la aplicación y el que más lógica propia tiene: alta,
edición, baja y reactivación, equipo del cliente (guardado como JSON), contactos,
organigrama y exportación a Excel.
"""

import io
import re

from openpyxl import load_workbook

import models


def _csrf(client, ruta="/nuevo-cliente"):
    html = client.get(ruta).text
    m = re.search(r'name="csrf-token" content="([^"]+)"', html)
    assert m, f"no se encontró el token CSRF en {ruta}"
    return m.group(1)


def _cliente(idx=0, **extra):
    datos = {
        "name": f"Cliente Prueba {idx}",
        "plant": f"Planta {idx}",
        "industry_sector": "Metalurgia",
        "assigned_commercial": "Carlos Pérez",
        "technical_advisor": "ING. GOMEZ",
        "designer": "Diseñador Uno",
        "address": f"Calle {idx} 123",
        "city": "Rosario",
        "status": "Activo",
        "observations": f"Observación {idx}",
    }
    datos.update(extra)
    return datos


def _crear(client, csrf, idx=0, equipo=None, **extra):
    datos = _cliente(idx, **extra)
    if equipo:
        # FastAPI lee los campos repetidos como listas.
        datos["member_name"] = [m["name"] for m in equipo]
        datos["member_role"] = [m.get("role", "") for m in equipo]
        datos["member_phone"] = [m.get("phone", "") for m in equipo]
        datos["member_reports_to"] = [m.get("reports_to", "") for m in equipo]
        datos["member_sector"] = [m.get("sector", "") for m in equipo]
    datos["csrf_token"] = csrf
    r = client.post("/nuevo-cliente", data=datos, follow_redirects=False)
    assert r.status_code == 303, f"el alta falló: {r.status_code}"
    return r


# ── Alta ───────────────────────────────────────────────────────────────────
def test_crear_cliente_guarda_todos_los_campos(client, db_session, admin_cookie):
    csrf = _csrf(client)
    _crear(client, csrf)

    c = db_session.query(models.Customer).filter_by(name="Cliente Prueba 0").one()
    assert c.plant == "Planta 0"
    assert c.industry_sector == "Metalurgia"
    assert c.assigned_commercial == "Carlos Pérez"
    assert c.technical_advisor == "ING. GOMEZ"
    assert c.designer == "Diseñador Uno"
    assert c.address == "Calle 0 123"
    assert c.city == "Rosario"
    assert c.status == "Activo"
    assert c.observations == "Observación 0"
    assert c.is_active is True


def test_crear_cliente_con_equipo_guarda_los_integrantes(client, db_session, admin_cookie):
    """El equipo se guarda como JSON: es lo más frágil del módulo."""
    csrf = _csrf(client)
    equipo = [
        {"name": "Ana Gómez", "role": "Jefa de Planta", "phone": "341-555-0001",
         "reports_to": "", "sector": "PRODUCCIÓN"},
        {"name": "Luis Pérez", "role": "Supervisor", "phone": "341-555-0002",
         "reports_to": "Ana Gómez", "sector": "MANTENIMIENTO"},
    ]
    _crear(client, csrf, equipo=equipo)

    c = db_session.query(models.Customer).filter_by(name="Cliente Prueba 0").one()
    assert isinstance(c.client_team, list)
    assert len(c.client_team) == 2, f"se esperaban 2 integrantes, hay {len(c.client_team)}"
    assert c.client_team[0]["name"] == "Ana Gómez"
    assert c.client_team[0]["role"] == "Jefa de Planta"
    assert c.client_team[0]["sector"] == "PRODUCCIÓN"
    assert c.client_team[1]["reports_to"] == "Ana Gómez"


def test_las_filas_de_equipo_vacias_no_se_guardan(client, db_session, admin_cookie):
    """El formulario agrega filas en blanco: no deben convertirse en integrantes."""
    csrf = _csrf(client)
    _crear(client, csrf, equipo=[{"name": "   "}, {"name": ""}])
    c = db_session.query(models.Customer).filter_by(name="Cliente Prueba 0").one()
    assert c.client_team == []


def test_crear_cliente_sin_equipo_no_falla(client, db_session, admin_cookie):
    """Los campos del equipo son opcionales."""
    csrf = _csrf(client)
    _crear(client, csrf)
    c = db_session.query(models.Customer).filter_by(name="Cliente Prueba 0").one()
    assert c.client_team == [] or c.client_team is None


# ── Listado ────────────────────────────────────────────────────────────────
def test_listado_muestra_busqueda_y_paginacion(client, db_session, admin_cookie):
    csrf = _csrf(client)
    for i in range(3):
        _crear(client, csrf, i)

    html = client.get("/clientes").text
    assert "Cliente Prueba 0" in html
    assert "Cliente Prueba 2" in html

    # La búsqueda filtra por nombre. Se mira la fila de la tabla y no el texto
    # suelto: el nombre también aparece en el modal de edición de cada fila.
    html = client.get("/clientes?q=Prueba 1").text
    tabla = html.split("<tbody")[1].split("</tbody>")[0] if "<tbody" in html else html
    assert "Cliente Prueba 1" in tabla
    assert "Cliente Prueba 2" not in tabla

    # Y por sector: los tres coinciden.
    html = client.get("/clientes?q=Metalurgia").text
    # Se mira el cuerpo de la tabla de resultados. No se exige un total exacto de
    # filas, porque la página puede traer otras tablas; lo que importa es que los
    # tres clientes creados estén listados.
    cuerpo = html.split("<tbody", 1)[1].split("</tbody>", 1)[0]
    assert cuerpo.count("<tr data-row") >= 3
    for i in range(3):
        assert f"Cliente Prueba {i}" in cuerpo


def test_las_estadisticas_describen_todo_el_conjunto(client, db_session, admin_cookie):
    """Antes se calculaban sobre la página visible y cambiaban al paginar."""
    csrf = _csrf(client)
    for i in range(12):
        _crear(client, csrf, i)

    html = client.get("/clientes?per_page=5").text
    # Con 12 clientes, el total debe decir 12 aunque la página muestre 5.
    assert re.search(r">\s*12\s*<", html), "el total no refleja el conjunto completo"


def test_las_estadisticas_no_cambian_al_pasar_de_pagina(client, db_session, admin_cookie):
    """El bug: limit y offset se aplicaban antes del agregado, así que las
    tarjetas describían sólo la página visible y cambiaban al paginar."""
    csrf = _csrf(client)
    for i in range(25):
        _crear(client, csrf, i)

    def stats(html):
        # Los valores de las tarjetas de relevamiento.
        return re.findall(r'<h4 class="text-lg font-black[^"]*">\s*(\d+)\s*</h4>', html)

    p1 = stats(client.get("/clientes?per_page=10&page=1").text)
    p2 = stats(client.get("/clientes?per_page=10&page=2").text)
    p3 = stats(client.get("/clientes?per_page=10&page=3").text)

    assert p1, "no se encontraron las tarjetas de estadísticas"
    assert p1 == p2 == p3, (
        f"las estadísticas cambian al paginar: página 1 -> {p1}, "
        f"página 2 -> {p2}, página 3 -> {p3}"
    )
    # Y el total debe ser el conjunto completo, no el de una página.
    assert "25" in p1, f"el total no es 25: {p1}"


# ── Edición ────────────────────────────────────────────────────────────────
def test_editar_cliente_actualiza_los_datos(client, db_session, admin_cookie):
    csrf = _csrf(client)
    _crear(client, csrf)
    c = db_session.query(models.Customer).filter_by(name="Cliente Prueba 0").one()

    datos = _cliente(0, name="Cliente Renombrado", city="Córdoba", status="Inactivo")
    datos["csrf_token"] = csrf
    r = client.post(f"/editar-cliente/{c.id}", data=datos, follow_redirects=False)
    assert r.status_code == 303

    db_session.refresh(c)
    assert c.name == "Cliente Renombrado"
    assert c.city == "Córdoba"
    assert c.status == "Inactivo"


def test_editar_cliente_permite_cambiar_el_equipo(client, db_session, admin_cookie):
    csrf = _csrf(client)
    _crear(client, csrf, equipo=[{"name": "Ana Gómez", "role": "Jefa"}])
    c = db_session.query(models.Customer).filter_by(name="Cliente Prueba 0").one()

    datos = _cliente(0)
    datos.update({
        "member_name": ["Ana Gómez", "Luis Pérez"],
        "member_role": ["Jefa de Planta", "Supervisor"],
        "member_phone": ["", ""],
        "member_reports_to": ["", "Ana Gómez"],
        "member_sector": ["PRODUCCIÓN", "MANTENIMIENTO"],
        "csrf_token": csrf,
    })
    client.post(f"/editar-cliente/{c.id}", data=datos, follow_redirects=False)

    db_session.refresh(c)
    assert len(c.client_team) == 2
    assert c.client_team[1]["name"] == "Luis Pérez"


def test_el_formulario_de_edicion_solo_responde_a_peticiones_ajax(client, db_session, admin_cookie):
    """Es un parcial para el modal; sin la cabecera AJAX redirige al listado."""
    csrf = _csrf(client)
    _crear(client, csrf)
    c = db_session.query(models.Customer).filter_by(name="Cliente Prueba 0").one()

    r = client.get(f"/editar-cliente/{c.id}", follow_redirects=False)
    assert r.status_code == 302
    assert r.headers["location"] == "/clientes"

    r = client.get(f"/editar-cliente/{c.id}", headers={"X-Requested-With": "XMLHttpRequest"})
    assert r.status_code == 200
    # El parcial es el formulario del modal: se identifica por su acción y por un
    # campo del cliente (no repite el nombre, que ya está en la tabla).
    assert f'action="/editar-cliente/{c.id}"' in r.text
    assert "Rosario" in r.text
    assert 'name="csrf_token"' in r.text


# ── Baja y reactivación ────────────────────────────────────────────────────
def test_desactivar_y_reactivar_cliente(client, db_session, admin_cookie):
    csrf = _csrf(client)
    _crear(client, csrf)
    c = db_session.query(models.Customer).filter_by(name="Cliente Prueba 0").one()

    # El endpoint espera JSON: el frontend lo llama por XHR.
    r = client.post(f"/desactivar-cliente/{c.id}",
                    json={"reason": "Dejó de operar"})
    assert r.status_code == 200, f"desactivar falló: {r.status_code} {r.text[:200]}"
    db_session.refresh(c)
    assert c.is_active is False
    assert c.inactivation_reason == "Dejó de operar"

    # Un cliente inactivo no debe aparecer en el listado...
    assert "Cliente Prueba 0" not in client.get("/clientes").text

    r = client.post(f"/reactivar-cliente/{c.id}")
    assert r.status_code == 200, f"reactivar falló: {r.status_code}"
    db_session.refresh(c)
    assert c.is_active is True
    assert "Cliente Prueba 0" in client.get("/clientes").text


def test_el_cliente_inactivo_no_aparece_en_los_selectores(client, db_session, admin_cookie):
    """Esto era un bug: seguía siendo seleccionable al crear una visita."""
    csrf = _csrf(client)
    _crear(client, csrf)
    c = db_session.query(models.Customer).filter_by(name="Cliente Prueba 0").one()
    client.post(f"/desactivar-cliente/{c.id}", json={"reason": "baja"})

    # El selector de una visita nueva no debe ofrecerlo.
    html = client.get("/visitas2/nueva").text
    assert "Cliente Prueba 0" not in html

    # Ni el de una minuta.
    assert "Cliente Prueba 0" not in client.get("/minutas/nueva").text


# ── Contactos y organigrama ────────────────────────────────────────────────
def test_quick_create_de_contacto_es_idempotente(client, db_session, admin_cookie):
    """Se usa desde el modal del equipo para agregar nombres al catálogo."""
    csrf = _csrf(client)
    r1 = client.post("/api/contact-name/quick-create",
                     data={"csrf_token": csrf, "name": "Ana Gómez"})
    assert r1.status_code == 200
    assert r1.json()["name"] == "ANA GÓMEZ"

    r2 = client.post("/api/contact-name/quick-create",
                     data={"csrf_token": csrf, "name": "ana gómez"})
    assert r2.status_code == 200
    assert r2.json()["id"] == r1.json()["id"], "creó un duplicado"
    assert db_session.query(models.ContactName).count() == 1


def test_api_del_equipo_devuelve_los_integrantes(client, db_session, admin_cookie):
    csrf = _csrf(client)
    _crear(client, csrf, equipo=[
        {"name": "Ana Gómez", "role": "Jefa"},
        {"name": "Luis Pérez", "role": "Supervisor"},
    ])
    c = db_session.query(models.Customer).filter_by(name="Cliente Prueba 0").one()

    r = client.get(f"/api/cliente-team/{c.id}")
    assert r.status_code == 200
    assert len(r.json()) == 2

    r = client.get(f"/api/cliente-contactos/{c.id}")
    assert r.status_code == 200
    assert r.json() == ["Ana Gómez", "Luis Pérez"]


def test_organigrama_responde(client, db_session, admin_cookie):
    csrf = _csrf(client)
    _crear(client, csrf)
    r = client.get("/organigrama")
    assert r.status_code == 200


# ── Reporte y exportación ──────────────────────────────────────────────────
def test_reporte_del_cliente_responde(client, db_session, admin_cookie):
    csrf = _csrf(client)
    _crear(client, csrf)
    c = db_session.query(models.Customer).filter_by(name="Cliente Prueba 0").one()
    r = client.get(f"/cliente-reporte/{c.id}")
    assert r.status_code == 200
    assert "Cliente Prueba 0" in r.text


def test_exportar_clientes_a_excel(client, db_session, admin_cookie):
    csrf = _csrf(client)
    for i in range(3):
        _crear(client, csrf, i)

    r = client.get("/clientes/exportar-excel")
    assert r.status_code == 200
    assert "spreadsheetml" in r.headers["content-type"]
    assert r.content[:2] == b"PK"

    total = db_session.query(models.Customer).count()
    ws = load_workbook(io.BytesIO(r.content)).active
    assert ws.max_row == total + 1, (
        f"el Excel tiene {ws.max_row - 1} filas y hay {total} clientes en la base"
    )
    valores = [str(ws.cell(row=f, column=c).value) for f in range(1, ws.max_row + 1)
               for c in range(1, 5)]
    assert any("Cliente Prueba" in v for v in valores)


def test_exportar_omite_los_clientes_dados_de_baja(client, db_session, admin_cookie):
    """La exportación debe coincidir con el listado, que oculta los inactivos.

    Antes hacía `query(Customer).all()` sin filtrar, así que el Excel mostraba
    clientes que la pantalla no listaba.
    """
    csrf = _csrf(client)
    _crear(client, csrf, 0)
    _crear(client, csrf, 1)
    c = db_session.query(models.Customer).filter_by(name="Cliente Prueba 1").one()
    client.post(f"/desactivar-cliente/{c.id}", json={"reason": "baja"})

    ws = load_workbook(io.BytesIO(client.get("/clientes/exportar-excel").content)).active
    nombres = [str(ws.cell(row=f, column=1).value) for f in range(2, ws.max_row + 1)]
    assert "Cliente Prueba 0" in nombres
    assert "Cliente Prueba 1" not in nombres, "la exportación incluye un cliente inactivo"


def test_exportar_puede_incluir_los_inactivos_a_pedido(client, db_session, admin_cookie):
    """Para el histórico completo se pueden pedir explícitamente."""
    csrf = _csrf(client)
    _crear(client, csrf, 0)
    _crear(client, csrf, 1)
    c = db_session.query(models.Customer).filter_by(name="Cliente Prueba 1").one()
    client.post(f"/desactivar-cliente/{c.id}", json={"reason": "baja"})

    r = client.get("/clientes/exportar-excel?include_inactive=true")
    ws = load_workbook(io.BytesIO(r.content)).active
    nombres = [str(ws.cell(row=f, column=1).value) for f in range(2, ws.max_row + 1)]
    assert "Cliente Prueba 1" in nombres
