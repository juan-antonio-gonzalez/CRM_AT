"""Pruebas del subset de íconos.

Los íconos se dibujan por ligadura y Google **descarta los nombres inválidos sin
avisar**: si un nombre está mal escrito, la fuente se genera igual, sin ese glifo,
y el ícono se imprime como su nombre. En el menú lateral eso se ve como un título
enorme en mayúsculas —así apareció «DIVERSITY_3» ocupando el lugar del ícono de
Equipos— y no hay ningún error en ningún lado.

Por eso la extracción de nombres necesita pruebas propias: es la parte que se
equivoca en silencio.
"""

import os

import pytest

from deploy import iconos

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


# ── La extracción de nombres ────────────────────────────────────────────────

def test_un_icono_suelto():
    html = '<span class="material-symbols-rounded">diversity_3</span>'
    assert iconos.iconos_de(html) == {"diversity_3"}


def test_un_icono_interpolado_con_comillas():
    """`clientes` es un valor de comparación, no un ícono."""
    html = ('<span class="material-symbols-rounded">'
            "{{ 'group' if clave == 'clientes' else 'precision_manufacturing' }}"
            "</span>")
    assert iconos.iconos_de(html) == {"group", "precision_manufacturing"}


def test_un_icono_en_un_if_de_jinja():
    """`fecha_desc` es un valor de orden y los íconos van sin comillas."""
    html = ('<span class="material-symbols-rounded">'
            "{% if sort == 'fecha_desc' %}expand_more{% else %}expand_less{% endif %}"
            "</span>")
    assert iconos.iconos_de(html) == {"expand_more", "expand_less"}


def test_una_variable_no_es_un_icono():
    """`{{ icono }}` es el nombre de la variable: el ícono real está en quien llama."""
    html = '<span class="material-symbols-rounded">{{ icono }}</span>'
    assert iconos.iconos_de(html) == set()


def test_una_interpolacion_de_javascript_no_es_un_icono():
    html = ('<span class="material-symbols-rounded ${iconColors[type]}">'
            "${icons[type] || icons.info}</span>")
    assert iconos.iconos_de(html) == set()


def test_el_mapa_de_iconos_de_los_avisos():
    """Los íconos de los avisos no están dentro de ningún span."""
    js = "const icons = { success: 'check_circle', error: 'error' };"
    assert iconos.iconos_de(js) == {"check_circle", "error"}


def test_el_mapa_de_colores_no_aporta_iconos():
    """Al lado del mapa de íconos hay uno de formas, que no tiene nombres de ícono."""
    js = "const iconColors = { success: 'text-emerald-500' };"
    assert iconos.iconos_de(js) == set()


# ── La lista del proyecto ───────────────────────────────────────────────────

def test_la_lista_no_tiene_valores_de_comparacion():
    """Eran los dos que se colaron y se veían como texto."""
    lista = set(iconos.iconos_del_proyecto())
    assert "clientes" not in lista
    assert "fecha_desc" not in lista


def test_la_lista_tiene_los_iconos_de_las_tablas_ordenables():
    """`expand_more` y `expand_less` se usan y faltaban de la fuente."""
    lista = set(iconos.iconos_del_proyecto())
    assert "expand_more" in lista
    assert "expand_less" in lista


def test_la_lista_no_tiene_nombres_de_variable():
    lista = set(iconos.iconos_del_proyecto())
    for variable in ("icono", "icons", "type", "clave", "sort"):
        assert variable not in lista, f"«{variable}» es una variable, no un ícono"


def test_el_archivo_de_iconos_esta_al_dia():
    """Si una plantilla estrena un ícono, hay que regenerar la fuente.

    Sin esto, el ícono nuevo se imprime como texto y nadie se entera hasta verlo.
    """
    en_disco = set(open(os.path.join(RAIZ, "static/fonts/material-symbols.icons.txt"),
                        encoding="utf-8").read().strip().split(","))
    del_proyecto = set(iconos.iconos_del_proyecto())
    faltan = del_proyecto - en_disco
    assert not faltan, (
        f"hay íconos sin regenerar: {sorted(faltan)}. "
        f"Corré: bash deploy/subset-iconos.sh")


# ── La fuente de verdad: los glifos ─────────────────────────────────────────

@pytest.mark.skipif(
    not __import__("tests.iconos_subset", fromlist=["disponible"]).disponible(),
    reason="requiere Chrome para dibujar la fuente",
)
def test_todos_los_iconos_del_subset_tienen_glifo():
    """Dibuja la fuente y mide: un nombre sin glifo ocupa el ancho del texto."""
    from tests import iconos_subset

    malos = iconos_subset.faltantes()
    assert not malos, (
        f"estos íconos no están en la fuente y se imprimen como texto: {malos}. "
        f"Revisá el nombre y corré: bash deploy/subset-iconos.sh")


def test_los_iconos_del_catalogo_de_modulos_se_extraen():
    """El menú lateral se arma con un bucle, así que sus íconos ya no están en
    ninguna plantilla: viven en `services/permisos.py`.

    Sin leerlos de ahí, la primera regeneración de la fuente se los llevaba
    puestos y volvían a verse como texto. Pasó con `dashboard`, `checklist_rtl` y
    `manage_accounts`, que sólo se usaban en el menú.
    """
    from services import permisos

    extraidos = set(iconos.iconos_del_proyecto())
    for m in permisos.MODULOS:
        assert m.icono in extraidos, (
            f"el ícono «{m.icono}» del módulo «{m.clave}» no se extrae, así que "
            f"la próxima regeneración lo dejaría afuera")
