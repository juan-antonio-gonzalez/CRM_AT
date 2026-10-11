#!/usr/bin/env bash
# Regenera el subset de iconos a partir de los nombres que usan las plantillas.
#
# La fuente completa de Material Symbols Rounded pesa 5.3 MB para ~110 iconos: el
# 99% del peso de la primera carga. Este script pide a la API de Google Fonts un
# subset con exactamente los iconos usados y lo deja vendorizado en static/fonts,
# asi el navegador no depende de ningun CDN.
#
# Uso:  bash deploy/subset-iconos.sh
set -euo pipefail
cd "$(dirname "$0")/.."

python3 - <<'PY'
import re, glob

# Dentro de un span de material symbols puede haber un nombre INTERPOLADO:
#
#     <span class="material-symbols-rounded">{{ 'trending_up' if x else 'trending_down' }}</span>
#
# Buscar solo el texto suelto del span no alcanza: asi se colaron dos iconos que
# se veian como texto en pantalla.
def iconos_de(texto):
    hallados = set()
    for m in re.finditer(r'class="[^"]*material-symbols-rounded[^"]*"[^>]*>(.*?)</span>',
                         texto, re.S):
        for a, b in re.findall(r"'([a-z][a-z_0-9]*)'|\"([a-z][a-z_0-9]*)\"", m.group(1)):
            hallados.add(a or b)
        suelto = m.group(1).strip()
        if re.fullmatch(r'[a-z][a-z_0-9]*', suelto):
            hallados.add(suelto)
    for m in re.finditer(r'indicador\(\s*"[^"]*"\s*,\s*[^,]+,\s*"[^"]*"\s*,\s*"([a-z_0-9]+)"', texto):
        hallados.add(m.group(1))
    for m in re.finditer(r'"icono":\s*"([a-z_0-9]+)"', texto):
        hallados.add(m.group(1))
    for m in re.finditer(r"\(\s*'[^']*'\s*,\s*'[^']*'\s*,\s*'([a-z][a-z_0-9]+)'\s*\)", texto):
        hallados.add(m.group(1))
    return hallados

todos = set()
for f in glob.glob("templates/*.html") + glob.glob("static/js/*.js"):
    todos |= iconos_de(open(f, encoding="utf-8", errors="replace").read())
todos = sorted(todos)
open("static/fonts/material-symbols.icons.txt", "w").write(",".join(todos))
print(f"  iconos: {len(todos)}")
PY

ICONS=$(cat static/fonts/material-symbols.icons.txt)
UA="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36"
curl -sf -A "$UA" "https://fonts.googleapis.com/css2?family=Material+Symbols+Rounded:opsz,wght,FILL,GRAD@20..48,100..700,0..1,-50..200&icon_names=${ICONS}&display=block" -o /tmp/subset.css
URL=$(python3 -c "import re;print(re.search(r'url\((https://[^)]+)\)', open('/tmp/subset.css').read()).group(1))")
curl -sf -A "$UA" "$URL" -o static/fonts/material-symbols.wff2.tmp
mv static/fonts/material-symbols.wff2.tmp static/fonts/material-symbols.woff2
chmod 644 static/fonts/material-symbols.woff2 static/fonts/material-symbols.icons.txt
ls -la static/fonts/material-symbols.woff2
