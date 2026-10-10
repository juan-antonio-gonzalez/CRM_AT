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


def _css_comun():
    """Las reglas de impresión compartidas por todos los informes.

    Viven en static/css/style.css y no en cada plantilla: tenerlas duplicadas
    hacía que un arreglo se aplicara a un formulario y no al otro, que es lo que
    pasó con la minuta.
    """
    from pathlib import Path

    css = Path("static/css/style.css").read_text(encoding="utf-8")
    return css[css.index("@media print"):]


def test_los_campos_de_texto_no_se_recortan_al_imprimir():
    """El textarea debe poder crecer: si no, se pierde todo lo que no entra."""
    css = _css_comun()

    assert "overflow: visible" in css, "el textarea seguiría recortando el texto"
    assert "overflow-y: visible" in css
    assert "height: auto !important" in css, "la altura fija del JS recortaría el texto"
    assert "max-height: none !important" in css
    # `field-sizing: content` es la forma nativa de que el control crezca.
    assert "field-sizing: content" in css


def test_el_texto_se_ajusta_sin_palabras_cortadas():
    """Las palabras se parten sólo si no entran; no se fuerza el corte."""
    css = _css_comun()

    assert "overflow-wrap: break-word" in css
    # word-break: normal evita el corte agresivo de "situa / ción".
    assert "word-break: normal" in css
    assert "hyphens: none" in css


def test_hay_configuracion_de_pagina_para_las_hojas_adicionales():
    """Sin @page no hay márgenes ni control del tamaño de hoja."""
    css = _css_comun()
    assert "@page" in css, "falta la regla @page"
    assert "size: A4 portrait" in css


def test_los_titulos_no_quedan_solos_al_final_de_una_hoja():
    css = _css_comun()

    assert "break-after: avoid" in css, "el título de sección podría quedar solo"
    # Las filas de tabla no se parten, pero la tabla sí puede continuar.
    assert "break-inside: avoid" in css
    assert "display: table-header-group" in css, "el encabezado no se repetiría"
    assert "orphans: 2" in css and "widows: 2" in css


def test_el_armazon_de_la_aplicacion_no_se_imprime():
    """El informe salía con la barra lateral y sus 19 enlaces."""
    from pathlib import Path

    bloque = _css_comun()
    assert "#sidebarNav" in bloque, "la barra lateral se imprimiría"
    assert "display: none" in bloque

    html = _render()
    # Los controles del formulario llevan .no-print y las reglas del armazón ya
    # ocultan esa clase (viven en el mismo bloque compartido).
    assert "no-print" in html
    assert ".no-print" in bloque


def test_un_anexo_vacio_no_se_imprime():
    """Un anexo sin texto generaba una hoja con su título y casillas vacías."""
    css = _css_impresion(_render())
    assert '.anexo-block[data-empty="true"]' in css
    assert "display: none !important" in css
    # El marcador del editor tampoco debe imprimirse (regla compartida).
    assert '.ska-rich-text:empty::before' in _css_comun()


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


# ── Minuta de reunión ───────────────────────────────────────────────────────
# La minuta tenía exactamente los mismos problemas que el informe de visita, y
# además un bug de serialización propio: la agenda se guardaba vacía porque el
# tema y el responsable son textarea y se los leía como input.
def _render_minuta(form_data=None):
    return templates.get_template("nueva_minuta.html").render(
        request=_Request(), minuta=None, form_data=form_data or {},
        title="Nueva Minuta de Reunión", action_url="/minutas/nueva",
        active_page="minutas", clientes=[],
    )


def test_la_minuta_lee_la_agenda_como_textarea():
    """El tema y el responsable son textarea: leerlos como input los descartaba."""
    html = _render_minuta()
    # La lectura debe tomar textarea, input y select por posición.
    assert "querySelectorAll('textarea, input')" in html, (
        "la agenda seguiría buscando sólo inputs y el orden del día se guardaría vacío"
    )
    assert "function valorDe" in html


def test_la_minuta_lee_tareas_con_select():
    """La fila de tareas tiene un select (estado) además de textareas."""
    html = _render_minuta()
    assert "querySelectorAll('textarea, input, select')" in html


def test_la_minuta_libera_la_altura_al_imprimir():
    """Mismo recorte que el informe: textarea con rows=1 y overflow hidden."""
    html = _render_minuta()
    assert "beforeprint" in html, "no se ajusta la altura antes de imprimir"
    assert "rows" in html
    # Las reglas comunes viven en style.css.
    from pathlib import Path
    css = Path("static/css/style.css").read_text(encoding="utf-8")
    bloque = css[css.index("@media print"):]
    assert "field-sizing: content" in bloque
    assert "@page" in bloque


def test_la_minuta_no_oculta_su_titulo_en_pantallas_chicas():
    """El `hidden lg:flex` dejaba la página sin título por debajo de 1024px."""
    html = _render_minuta()
    assert 'class="hidden lg:flex items-center gap-4 ml-4"' not in html


@pytest.mark.skipif(
    not __import__("tests.pdf_minuta", fromlist=["disponible"]).disponible(),
    reason="requiere Chrome y pypdf para imprimir y leer el PDF",
)
def test_minuta_serializa_e_imprime_completa():
    """Corre la minuta en un navegador real y verifica el JSON y el PDF."""
    from tests import pdf_minuta

    assert pdf_minuta.main() == 0, (
        "falló la verificación de la minuta; revisá "
        f"{pdf_minuta.PDF}"
    )
