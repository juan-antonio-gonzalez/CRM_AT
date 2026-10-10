"""Pruebas de la impresión del informe de visita.

Cubren los dos problemas que tenía el informe al imprimirse:

* el texto de los campos se cortaba, porque los `textarea` se crean con
  `rows="1"` y `overflow:hidden`, y el navegador los imprime con una sola línea
  de alto;
* las hojas de continuación no tenían control de saltos ni márgenes, así que el
  contenido largo se partía mal y la barra lateral de la aplicación se imprimía.

La verificación de fondo —imprimir con Chrome y comprobar sobre el PDF que cada
campo salga completo— está en `tests/pdf_informe.py` y se ejecuta con
`test_informe_impreso_no_corta_el_texto`. Se omite si no hay Chrome o pypdf,
para que la suite siga corriendo en cualquier entorno.
"""

import re

import pytest

from templating import templates


class _Estado:
    user = {"username": "probe", "role": "admin", "sub": "1"}
    csrf_token = "TOKEN"
    script_nonce = "nonce"


class _Request:
    state = _Estado()

    @staticmethod
    def url_for(name, **params):
        return "/static/" + str(params.get("path", "")).lstrip("/")


class _Visit:
    id = 1
    fecha = "2026-05-10"
    status = "Finalizado"


def _render(form_data=None):
    return templates.get_template("nueva_visita2.html").render(
        request=_Request(), visit=_Visit(), form_data=form_data or {},
        title="Informe de Visita Técnica", action_url="/visitas2/1/editar",
        active_page="visitas2", clientes=[], tecnicos=[], distribuidoras=[],
        temas_calidad=[], calidad_at=[], tareas_vinculadas=[],
    )


def _css_impresion(html):
    """Devuelve el bloque @media print de la plantilla."""
    bloques = re.findall(r"@media print\s*\{(.*?)\n\}", html, re.S)
    return "\n".join(bloques)


def test_los_campos_de_texto_no_se_recortan_al_imprimir():
    """El textarea debe poder crecer: si no, se pierde todo lo que no entra."""
    css = _css_impresion(_render())

    assert "overflow: visible" in css, "el textarea seguiría recortando el texto"
    assert "overflow-y: visible" in css
    assert "height: auto !important" in css, "la altura fija del JS recortaría el texto"
    assert "max-height: none !important" in css
    # `field-sizing: content` es la forma nativa de que el control crezca.
    assert "field-sizing: content" in css


def test_el_texto_se_ajusta_sin_palabras_cortadas():
    """Las palabras se parten sólo si no entran; no se fuerza el corte."""
    css = _css_impresion(_render())

    assert "overflow-wrap: break-word" in css
    # word-break: normal evita el corte agresivo de "situa / ción".
    assert "word-break: normal" in css
    assert "hyphens: none" in css


def test_hay_configuracion_de_pagina_para_las_hojas_adicionales():
    """Sin @page no hay márgenes ni control del tamaño de hoja."""
    html = _render()
    assert "@page" in html, "falta la regla @page"
    assert "size: A4 portrait" in html


def test_los_titulos_no_quedan_solos_al_final_de_una_hoja():
    css = _css_impresion(_render())

    assert "break-after: avoid" in css, "el título de sección podría quedar solo"
    # Las filas de tabla no se parten, pero la tabla sí puede continuar.
    assert "break-inside: avoid" in css
    assert "display: table-header-group" in css, "el encabezado no se repetiría"
    assert "orphans: 2" in css and "widows: 2" in css


def test_el_armazon_de_la_aplicacion_no_se_imprime():
    """El informe salía con la barra lateral y sus 19 enlaces."""
    from pathlib import Path

    css = Path("static/css/style.css").read_text(encoding="utf-8")
    bloque = css[css.index("@media print"):]
    assert "#sidebarNav" in bloque, "la barra lateral se imprimiría"
    assert "display: none" in bloque

    html = _render()
    # El botón de guardar y el de agregar anexo llevan .no-print.
    assert "no-print" in html
    assert ".no-print, .ska-actions, .ska-btn" in html


def test_un_anexo_vacio_no_se_imprime():
    """Un anexo sin texto generaba una hoja con su título y casillas vacías."""
    css = _css_impresion(_render())
    assert '.anexo-block[data-empty="true"]' in css
    assert "display: none !important" in css
    # El marcador del editor tampoco debe imprimirse.
    assert '.ska-rich-text:empty::before' in css


def test_las_casillas_de_foto_vacias_no_se_imprimen():
    """Sin fotos, las cuatro casillas ocupaban media hoja con el ícono 📷."""
    css = _css_impresion(_render())
    assert ".ska-img-slot:not(.has-img)" in css
    assert ".ska-img-slot.has-img img" in css, "las fotos cargadas sí deben salir"


def test_los_anexos_se_numeran_por_posicion_visible():
    """Un anexo vacío en el medio dejaba huecos: el informe decía ANEXO III con dos."""
    html = _render()
    # El número ya no se calcula al crear, sino al renumerar por posición.
    assert "function renumerarAnexos" in html
    assert "function toRoman" in html
    assert "anexo-titulo" in html
    # El título base no lleva número: lo asigna renumerarAnexos.
    assert "'ANEXO: DESARROLLO'" in html
    # Y se recalcula al crear, al editar, al restaurar y al eliminar.
    assert html.count("renumerarAnexos()") >= 4


def test_el_titulo_del_anexo_va_en_un_elemento_propio():
    """renumerarAnexos necesita un nodo concreto que actualizar."""
    html = _render()
    assert 'class="anexo-titulo"' in html


@pytest.mark.skipif(
    not __import__("tests.pdf_informe", fromlist=["disponible"]).disponible(),
    reason="requiere Chrome y pypdf para imprimir y leer el PDF",
)
def test_informe_impreso_no_corta_el_texto():
    """Imprime el informe con Chrome y verifica sobre el PDF que esté completo."""
    from tests import pdf_informe

    assert pdf_informe.main() == 0, (
        "alguna verificación sobre el PDF del informe falló; "
        f"revisá {pdf_informe.PDF}"
    )
