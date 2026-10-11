"""Pruebas de los catálogos del encabezado de la visita.

El formulario tenía cuatro tipos de visita escritos a mano mientras Tablas
Auxiliares mantenía un catálogo con otros valores: **sólo coincidían en
«Seguimiento»**. Agregar un tipo en el catálogo no aparecía en el formulario.
"""

import os
import re

import models

PLANTILLAS = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                          "templates")


def _entrar(client):
    client.post("/auth/login", data={"username": "admin", "password": "admin123"})


def test_los_tipos_de_visita_salen_del_catalogo(client, db_session, seed_admin):
    db_session.add(models.VisitType(name="TIPO DE PRUEBA"))
    db_session.commit()
    _entrar(client)
    html = client.get("/visitas2/nueva").text
    assert "TIPO DE PRUEBA" in html, "el formulario no lee el catálogo"


def test_los_motivos_salen_del_catalogo(client, db_session, seed_admin):
    db_session.add(models.VisitReason(name="MOTIVO DE PRUEBA"))
    db_session.commit()
    _entrar(client)
    html = client.get("/visitas2/nueva").text
    assert "MOTIVO DE PRUEBA" in html


def test_un_catalogo_vacio_no_rompe_el_formulario(client, db_session, seed_admin):
    _entrar(client)
    r = client.get("/visitas2/nueva")
    assert r.status_code == 200


def test_el_formulario_tiene_los_selectores_de_alcance(client, db_session, seed_admin):
    _entrar(client)
    html = client.get("/visitas2/nueva").text
    assert 'name="alcance"' in html
    assert "Recorrí la línea" in html


def test_no_quedan_tipos_de_visita_escritos_a_mano():
    """Si vuelven los valores fijos, el catálogo y el formulario divergen otra vez."""
    with open(os.path.join(PLANTILLAS, "nueva_visita2.html"), encoding="utf-8") as fh:
        texto = fh.read()
    fijos = ["Visita programada", "Análisis No conformidad", "Solicitud del cliente"]
    encontrados = [v for v in fijos if f'value="{v}"' in texto]
    assert not encontrados, f"volvieron los valores fijos: {encontrados}"
    # Y en su lugar hay un bucle sobre el catálogo.
    assert "for t in visit_types" in texto


def test_el_motivo_es_un_catalogo_editable():
    """Debe estar en Tablas Auxiliares, no ser texto libre."""
    with open(os.path.join(PLANTILLAS, "configuracion.html"), encoding="utf-8") as fh:
        texto = fh.read()
    assert "list-visit-reason" in texto, "el motivo no está en Tablas Auxiliares"
    assert "list-visit-type" in texto


def test_el_motivo_se_guarda_y_se_restaura():
    """Sin esto el motivo se carga pero se pierde al guardar."""
    with open(os.path.join(PLANTILLAS, "nueva_visita2.html"), encoding="utf-8") as fh:
        texto = fh.read()
    assert "motivo: document.getElementById('motivo').value" in texto
    assert "data.motivo" in texto
    assert "data.alcance" in texto
