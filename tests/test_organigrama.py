"""Pruebas de la página de organigrama.

La lógica del árbol vive en JavaScript (se arma en el navegador a partir del
equipo del cliente) y se prueba con Node en `tests/organigrama.mjs`, que se
invoca desde acá. Estas pruebas cubren el lado del servidor: la página, el
selector de clientes y la API que la alimenta.
"""

import os
import re
import shutil
import subprocess

import pytest

import models

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _csrf(client, ruta="/nuevo-cliente"):
    html = client.get(ruta).text
    m = re.search(r'name="csrf-token" content="([^"]+)"', html)
    assert m, f"no se encontró el token CSRF en {ruta}"
    return m.group(1)


def _crear(client, csrf, nombre, equipo=None, activo=True):
    datos = {
        "name": nombre, "plant": "Planta", "industry_sector": "Metalurgia",
        "assigned_commercial": "Comercial", "technical_advisor": "ING. GOMEZ",
        "designer": "Diseñador", "address": "Calle 1", "city": "Rosario",
        "status": "Activo", "observations": "", "csrf_token": csrf,
    }
    if equipo:
        datos.update({
            "member_name": [m["name"] for m in equipo],
            "member_role": [m.get("role", "") for m in equipo],
            "member_phone": [m.get("phone", "") for m in equipo],
            "member_reports_to": [m.get("reports_to", "") for m in equipo],
            "member_sector": [m.get("sector", "") for m in equipo],
        })
    client.post("/nuevo-cliente", data=datos, follow_redirects=False)
    return nombre


def test_la_pagina_de_organigrama_responde(client, db_session, admin_cookie):
    r = client.get("/organigrama")
    assert r.status_code == 200
    assert 'id="customerSelect"' in r.text
    assert 'id="orgContent"' in r.text


def test_el_selector_no_ofrece_clientes_dados_de_baja(client, db_session, admin_cookie):
    csrf = _csrf(client)
    _crear(client, csrf, "Cliente Activo")
    _crear(client, csrf, "Cliente Dado de Baja")
    c = db_session.query(models.Customer).filter_by(name="Cliente Dado de Baja").one()
    client.post(f"/desactivar-cliente/{c.id}", json={"reason": "baja"})

    html = client.get("/organigrama").text
    assert "Cliente Activo" in html
    assert "Cliente Dado de Baja" not in html


def test_la_api_del_equipo_alimenta_el_organigrama(client, db_session, admin_cookie):
    """El organigrama consume /api/cliente-team: debe devolver el equipo crudo."""
    csrf = _csrf(client)
    _crear(client, csrf, "Cliente Con Equipo", equipo=[
        {"name": "Ana Gómez", "role": "Jefa", "phone": "341-555-1",
         "reports_to": "", "sector": "PRODUCCIÓN"},
        {"name": "Luis Pérez", "role": "Operario", "phone": "",
         "reports_to": "Ana Gómez", "sector": "PRODUCCIÓN"},
    ])
    c = db_session.query(models.Customer).filter_by(name="Cliente Con Equipo").one()

    equipo = client.get(f"/api/cliente-team/{c.id}").json()
    assert len(equipo) == 2
    # El organigrama necesita estos cinco campos.
    for campo in ("name", "role", "phone", "reports_to", "sector"):
        assert campo in equipo[0], f"falta el campo {campo}"
    assert equipo[1]["reports_to"] == "Ana Gómez"


def test_el_organigrama_no_carga_clientes_fuera_de_la_api(client, db_session, admin_cookie):
    """La página no debe incrustar los equipos: se piden por la API."""
    csrf = _csrf(client)
    _crear(client, csrf, "Cliente X", equipo=[{"name": "Persona Interna", "role": "R"}])
    html = client.get("/organigrama").text
    assert "Persona Interna" not in html


@pytest.mark.skipif(shutil.which("node") is None,
                    reason="requiere Node.js para ejecutar el JavaScript de la plantilla")
def test_la_logica_del_arbol_pasa_sus_pruebas():
    """Ejecuta tests/organigrama.mjs, que prueba el JS real de la plantilla."""
    r = subprocess.run(
        ["node", os.path.join(RAIZ, "tests", "organigrama.mjs")],
        capture_output=True, text=True, timeout=120,
    )
    assert r.returncode == 0, (
        "fallaron las pruebas del organigrama:\n" + r.stdout + r.stderr
    )
    assert "RESULTADO: todo bien" in r.stdout
