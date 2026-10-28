"""Pruebas de la impresión del informe de clientes.

El informe nació como una hoja única y el pie decía «Página 1 de 1» escrito a
mano. Con un cliente de veinte máquinas y treinta visitas el contenido no entra,
y ahí pasaban tres cosas:

* el navegador cortaba las tarjetas de máquina al medio, dejando el título en una
  hoja y el número de serie en la siguiente;
* la tabla de contactos, al no entrar en lo que quedaba de hoja, se iba entera a
  la siguiente y dejaba media hoja en blanco;
* el pie seguía diciendo «Página 1 de 1» con siete hojas impresas.

La verificación de fondo —imprimir con Chrome y medir sobre el PDF— está en
`tests/pdf_cliente.py` y se ejecuta con `test_el_informe_impreso_no_pierde_nada`.
Se omite si no hay Chrome o pypdf, para que la suite siga corriendo en cualquier
entorno.
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


class _Cliente:
    id = 7
    name = "CARTOCOR SA"
    plant = "Planta Norte"
    industry_sector = "Corrugado"
    city = "Rosario"
    country = "Argentina"
    address = "Av. Central 1234"
    technical_advisor = "ING. GOMEZ"
    assigned_commercial = "CARLOS PÉREZ"
    designer = "DISEÑO UNO"
    observations = ""
    client_team = []


class _Generacion:
    year = 2026

    @staticmethod
    def strftime(_):
        return "01/06/2026"


def _render(**extra):
    datos = {
        "request": _Request(), "customer": _Cliente(), "machines": [], "visits": [],
        "generation_date": _Generacion(), "active_page": "clientes",
    }
    datos.update(extra)
    return templates.get_template("cliente_reporte.html").render(**datos)


# ── Lo que se puede verificar sin navegador ─────────────────────────────────

def test_el_informe_se_pagina_con_el_paginador():
    """El reparto en hojas lo hace el paginador, no el navegador."""
    html = _render()
    assert "data-informe-paginado" in html
    assert "data-hoja-modelo" in html
    assert "informe-paginado.js" in html


def test_la_hoja_tiene_cuerpo_y_pie_con_su_numero():
    html = _render()
    assert "data-hoja-cuerpo" in html
    assert "data-hoja-numero" in html


def test_el_pie_no_tiene_un_numero_escrito_a_mano():
    """Era el bug: «Página 1 de 1» fijo mentía en cuanto había más de una hoja."""
    html = _render()
    assert "Página 1 de 1" not in html


def test_la_rejilla_de_maquinas_se_declara_partible():
    """Es lo que evita que una tarjeta quede con su título en otra hoja."""
    html = _render()
    assert 'data-partible="tarjetas"' in html


def test_las_observaciones_se_declaran_partibles():
    """Un texto largo es lo único que no se puede cortar por filas."""
    html = _render(customer=_cliente_con_observaciones())
    assert 'data-partible="texto"' in html


def _cliente_con_observaciones():
    c = _Cliente()
    c.observations = "Una observación larga."
    return c


def test_la_hoja_impresa_es_una_pagina_a4():
    """La hoja es la página: el margen lo pone su padding, no `@page`."""
    html = _render()
    assert "@page" in html
    assert "size: A4" in html
    # El margen de `@page` va en cero y el padding de la hoja en 15 mm: si los dos
    # sumaran, el contenido se correría respecto de lo que se midió.
    bloque = html[html.index("@media print"):]
    assert re.search(r"margin:\s*0", bloque)
    assert "15mm" in html


def test_solo_la_ultima_hoja_no_fuerza_el_salto():
    """Sin esto saldría una página en blanco al final."""
    html = _render()
    assert ".hoja:last-child" in html
    assert "break-after: auto" in html


def test_no_se_oculta_el_header_del_informe():
    """El armazón se oculta por id: un `header` a secas borraría el título."""
    html = _render()
    inicio = html.index("@media print")
    bloque = html[inicio:html.index("</style>", inicio)]
    assert "#sidebarNav" in bloque
    assert re.search(r"^\s*header\s*,", bloque, re.M) is None, (
        "ocultar `header` a secas borraría el encabezado del informe")


# ── La verificación de fondo, con navegador ────────────────────────────────

@pytest.mark.skipif(
    not __import__("tests.pdf_cliente", fromlist=["disponible"]).disponible(),
    reason="requiere Chrome y pypdf para imprimir y leer el PDF",
)
def test_el_informe_impreso_no_pierde_nada():
    """Imprime con Chrome y comprueba sobre el PDF que las hojas se adapten.

    Verifica que el informe ocupe más de una hoja, que el pie diga la cantidad
    real, que no se pierda el final, que ninguna tarjeta quede partida y que el
    encabezado de la tabla se repita al cambiar de hoja.
    """
    from tests import pdf_cliente

    assert pdf_cliente.main() == 0, (
        "alguna verificación sobre el PDF del informe de clientes falló; "
        f"revisá {pdf_cliente.PDF}"
    )


def test_el_boton_de_imprimir_esta_enganchado():
    """Tenía un `id` que no usaba nadie y le faltaba el atributo del manejador.

    El botón estaba, se veía, y no hacía nada: el código que escucha busca
    `[data-print-btn]`.
    """
    html = _render()
    assert "data-print-btn" in html
    assert "window.print()" in html
