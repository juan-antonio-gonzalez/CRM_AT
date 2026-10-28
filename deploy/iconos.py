"""Saca de las plantillas la lista de íconos que hay que pedirle a Google Fonts.

Vive en un módulo y no dentro del script de bash para poder probarlo: la
extracción es la parte que se equivoca en silencio, y un error acá no rompe nada
—el ícono simplemente se imprime como su nombre— así que necesita pruebas.

Uso:  python3 deploy/iconos.py [--listar]
"""

import glob
import os
import re
import sys

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# El script se corre como `python3 deploy/iconos.py`, así que la raíz del proyecto
# no está en el camino de importación y `services` no se encontraría.
if RAIZ not in sys.path:
    sys.path.insert(0, RAIZ)


def _entrecomillados(texto: str) -> set:
    """Los nombres entre comillas de un fragmento."""
    hallados = set()
    for a, b in re.findall(r"'([a-z][a-z_0-9]*)'|\"([a-z][a-z_0-9]*)\"", texto):
        hallados.add(a or b)
    return hallados


def iconos_de_span(contenido: str) -> set:
    """Los íconos que puede llegar a mostrar un `<span>` de material symbols.

    Un ícono condicional se escribe de dos formas, y las dos se leían mal:

        {{ 'group' if clave == 'clientes' else 'precision_manufacturing' }}
        {% if sort == 'fecha_desc' %}expand_more{% else %}expand_less{% endif %}

    Buscar todas las cadenas entrecomilladas metía ``clientes``, que es un valor de
    comparación y no un ícono. Y en la forma con ``{% if %}`` no se encontraba
    ninguno, porque los nombres van sin comillas. Los dos errores son silenciosos:
    Google descarta los nombres inválidos sin avisar y el ícono se imprime como
    texto, así que nadie se entera hasta que alguien lo ve en pantalla —y en el
    menú lateral se ve como un título enorme.

    Por eso se saca la condición y se miran sólo las ramas.
    """
    hallados = set()

    # De `{{ A if condición else B }}` valen A y B, no la condición. Y valen sólo
    # si son literales: `{{ icono }}` es una variable, y su nombre (`icono`) no es
    # un ícono. En ese caso el nombre real está en quien llama, y se recoge por los
    # otros patrones de `iconos_de`.
    for expr in re.findall(r"\{\{(.*?)\}\}", contenido, re.S):
        for rama in re.split(r"\bif\b.*?\belse\b", expr, flags=re.S):
            hallados |= _entrecomillados(rama)

    # De `{% if condición %}A{% else %}B{% endif %}` quedan A y B, que acá van sin
    # comillas. Las etiquetas se van, y `else` / `elif` / `endif` dejan un espacio
    # para que las dos ramas no se peguen en un solo nombre que no existe. Lo mismo
    # con las interpolaciones de JavaScript: `${colorMap[type]}` no es un ícono.
    sin_jinja = re.sub(r"\{\{.*?\}\}", " ", contenido, flags=re.S)
    sin_jinja = re.sub(r"\$\{.*?\}", " ", sin_jinja, flags=re.S)
    sin_jinja = re.sub(r"\{%\s*(?:else|elif|endif)\s*%\}", " ", sin_jinja)
    sin_jinja = re.sub(r"\{%.*?%\}", "", sin_jinja, flags=re.S)
    for token in re.findall(r"[a-z][a-z_0-9]*", sin_jinja):
        hallados.add(token)

    return hallados


def iconos_de(texto: str) -> set:
    """Todos los íconos que usa un archivo de plantilla o de JavaScript."""
    hallados = set()
    for m in re.finditer(
            r'class="[^"]*material-symbols-rounded[^"]*"[^>]*>(.*?)</span>',
            texto, re.S):
        hallados |= iconos_de_span(m.group(1))
    # El cuarto argumento de `indicador(...)` es el ícono.
    for m in re.finditer(
            r'indicador\(\s*"[^"]*"\s*,\s*[^,]+,\s*"[^"]*"\s*,\s*"([a-z_0-9]+)"',
            texto):
        hallados.add(m.group(1))
    # El ícono de un indicador escrito como dato.
    for m in re.finditer(r'"icono":\s*"([a-z_0-9]+)"', texto):
        hallados.add(m.group(1))
    # El mapa de íconos de los avisos, que no está dentro de ningún span:
    # `const icons = { success: 'check_circle', ... }`. Se busca el bloque por su
    # nombre exacto porque al lado hay otro mapa igual de formas (`iconColors`) que
    # no tiene íconos.
    for m in re.finditer(r"const\s+icons\s*=\s*\{(.*?)\}", texto, re.S):
        hallados |= _entrecomillados(m.group(1))
    # Tuplas `('...', '...', 'icono')`.
    for m in re.finditer(r"\(\s*'[^']*'\s*,\s*'[^']*'\s*,\s*'([a-z][a-z_0-9]+)'\s*\)",
                         texto):
        hallados.add(m.group(1))
    return hallados


def iconos_del_catalogo() -> set:
    """Los íconos que declara el catálogo de módulos.

    El menú lateral se arma con un bucle sobre `services/permisos.py`, así que sus
    íconos **ya no están escritos en ninguna plantilla**. Sin esto, la primera
    regeneración de la fuente se los llevaba puestos y volvían a verse como texto:
    pasó con `dashboard`, `checklist_rtl` y `manage_accounts`, que sólo se usaban
    ahí.
    """
    try:
        from services import permisos
    except Exception:
        return set()
    return {m.icono for m in permisos.MODULOS if m.icono}


def iconos_del_proyecto(raiz: str = None) -> list:
    """La lista ordenada de íconos que usa la aplicación."""
    raiz = raiz or RAIZ
    todos = set()
    for patron in ("templates/*.html", "static/js/*.js"):
        for ruta in glob.glob(os.path.join(raiz, patron)):
            with open(ruta, encoding="utf-8", errors="replace") as fh:
                todos |= iconos_de(fh.read())
    todos |= iconos_del_catalogo()
    return sorted(todos)


def main(argv=None) -> int:
    argv = argv if argv is not None else sys.argv[1:]
    iconos = iconos_del_proyecto()
    if "--listar" in argv:
        for i in iconos:
            print(i)
        return 0
    destino = os.path.join(RAIZ, "static/fonts/material-symbols.icons.txt")
    with open(destino, "w", encoding="utf-8") as fh:
        fh.write(",".join(iconos))
    print(f"  iconos: {len(iconos)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
