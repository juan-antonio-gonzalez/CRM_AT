"""Pruebas de los catálogos de Tablas Auxiliares.

Todos los catálogos se guardan en **mayúsculas**, y eso no es cosmético: los filtros
comparan por igualdad, así que «Retiro de muestra» y «RETIRO DE MUESTRA» serían dos
valores distintos y el filtro por uno no encontraría el otro.

La regla se aplica en dos lugares, y hacen falta los dos:

* **En el formulario**, con `toUpperCase()` al escribir, para que se vea mientras se
  carga.
* **En el modelo**, porque el formulario se puede saltear (una llamada directa, una
  importación, un script). El formulario es comodidad; el modelo es la garantía.
"""

import inspect
import os
import re

import models

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PLANTILLAS = os.path.join(RAIZ, "templates")


def _catalogos():
    return sorted(
        (m for _n, m in inspect.getmembers(models, inspect.isclass)
         if issubclass(m, models.BaseCatalogMixin) and m is not models.BaseCatalogMixin),
        key=lambda m: m.__name__)


def test_todos_los_catalogos_estan_registrados_en_tablas_auxiliares():
    """Un catálogo que no está en Tablas Auxiliares no se puede mantener."""
    with open(os.path.join(RAIZ, "routers", "configuracion.py"), encoding="utf-8") as fh:
        fuente = fh.read()
    faltan = [m.__name__ for m in _catalogos() if f"models.{m.__name__}" not in fuente]
    assert not faltan, f"catálogos fuera de Tablas Auxiliares: {faltan}"


def test_todos_los_catalogos_suben_a_mayusculas():
    """Se comprueba sobre el modelo, no sobre el formulario.

    El formulario se puede saltear; el modelo no.
    """
    problemas = []
    for modelo in _catalogos():
        if not hasattr(modelo, "validate_name"):
            problemas.append(f"{modelo.__name__}: sin validador")
            continue
        # El validador tiene que convertir a mayúsculas de verdad.
        instancia = modelo(name="  prueba en minúscula  ")
        if instancia.name != "PRUEBA EN MINÚSCULA":
            problemas.append(f"{modelo.__name__}: no sube a mayúsculas ({instancia.name!r})")
    assert not problemas, f"catálogos que no normalizan: {problemas}"


def test_todas_las_tarjetas_lo_muestran_al_escribir():
    """El `toUpperCase()` en el formulario, para que se vea al cargar."""
    with open(os.path.join(PLANTILLAS, "configuracion.html"), encoding="utf-8") as fh:
        texto = fh.read()
    inputs = re.findall(r'<input id="input-[a-z-]+"[\s\S]{0,400}?>', texto)
    sin = [i for i in inputs if "toUpperCase" not in i]
    assert not sin, f"{len(sin)} campos de catálogo no fuerzan mayúsculas al escribir"


def test_no_quedan_valores_en_minuscula_en_la_base(db_session):
    """Un valor viejo en minúscula rompe el filtro aunque el modelo ya valide."""
    problemas = []
    for modelo in _catalogos():
        for (nombre,) in db_session.query(modelo.name).all():
            if nombre and nombre != nombre.upper():
                problemas.append(f"{modelo.__tablename__}: {nombre!r}")
    assert not problemas, f"valores en minúscula: {problemas}"


def test_el_validador_tambien_recorta_los_espacios():
    """Espacios al principio o al final también rompen la comparación por igualdad."""
    for modelo in _catalogos():
        instancia = modelo(name="  CON ESPACIOS  ")
        assert instancia.name == "CON ESPACIOS", f"{modelo.__name__} no recorta"
