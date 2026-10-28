#!/usr/bin/env bash
# Regenera el subset de iconos a partir de los nombres que usan las plantillas.
#
# La fuente completa de Material Symbols Rounded pesa 5.3 MB para ~118 iconos: el
# 99% del peso de la primera carga. Este script pide a la API de Google Fonts un
# subset con exactamente los iconos usados y lo deja vendorizado en static/fonts,
# asi el navegador no depende de ningun CDN.
#
# Uso:  bash deploy/subset-iconos.sh
#
# Dos cosas que hay que saber antes de tocarlo
# --------------------------------------------
# **Google descarta los nombres invalidos sin avisar.** Si un nombre esta mal
# escrito, la fuente se genera igual, sin ese glifo, y el icono se imprime como su
# nombre: en el menu lateral eso se ve como un titulo enorme. No hay error en
# ningun lado. Los nombres se sacan con `deploy/iconos.py`, que tiene sus pruebas,
# y despues se verifica dibujando la fuente con `tests/iconos_subset.py`.
#
# **La `url()` de la fuente lleva la huella de su archivo.** `fonts.css` se pide
# con `?v=<huella de todo lo estatico>`, pero la cache de fuentes va por URL: si la
# `url()` de adentro no cambia, el navegador sigue usando la fuente vieja para
# siempre. Asi fue como `diversity_3` se siguio viendo como «DIVERSITY_3» despues
# de agregar el icono.
set -euo pipefail
cd "$(dirname "$0")/.."

python3 deploy/iconos.py

ICONS=$(cat static/fonts/material-symbols.icons.txt)
UA="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36"
curl -sf -A "$UA" "https://fonts.googleapis.com/css2?family=Material+Symbols+Rounded:opsz,wght,FILL,GRAD@20..48,100..700,0..1,-50..200&icon_names=${ICONS}&display=block" -o /tmp/subset.css
URL=$(python3 -c "import re;print(re.search(r'url\((https://[^)]+)\)', open('/tmp/subset.css').read()).group(1))")
curl -sf -A "$UA" "$URL" -o static/fonts/material-symbols.wff2.tmp
mv static/fonts/material-symbols.wff2.tmp static/fonts/material-symbols.woff2
chmod 644 static/fonts/material-symbols.woff2 static/fonts/material-symbols.icons.txt

# La URL de cada fuente en `fonts.css` lleva la huella de su archivo.
python3 - <<'PY'
import hashlib, re


def versionar(css, archivo):
    with open("static/fonts/" + archivo, "rb") as fh:
        huella = hashlib.sha1(fh.read()).hexdigest()[:8]
    return re.sub(r"/static/fonts/" + re.escape(archivo) + r"(\?v=[0-9a-f]+)?",
                  f"/static/fonts/{archivo}?v={huella}", css)


css = open("static/css/fonts.css", encoding="utf-8").read()
for archivo in ("inter.woff2", "material-symbols.woff2"):
    css = versionar(css, archivo)
open("static/css/fonts.css", "w", encoding="utf-8").write(css)
for linea in css.splitlines():
    if "url(" in linea:
        print("  " + linea.strip())
PY

ls -la static/fonts/material-symbols.woff2
