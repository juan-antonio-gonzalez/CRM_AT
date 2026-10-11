#!/usr/bin/env bash
# Regenera el subset de iconos a partir de los nombres que usan las plantillas.
#
# La fuente completa de Material Symbols Rounded pesa 5.3 MB para 107 iconos: el
# 99% del peso de la primera carga. Este script pide a la API de Google Fonts un
# subset con exactamente los iconos usados y lo deja vendorizado en static/fonts,
# asi el navegador no depende de ningun CDN.
#
# Uso:  bash deploy/subset-iconos.sh
set -euo pipefail
cd "$(dirname "$0")/.."

python3 - <<'PY'
import re, glob
iconos = set()
for f in glob.glob("templates/*.html") + glob.glob("static/js/*.js"):
    s = open(f, encoding="utf-8", errors="replace").read()
    for m in re.finditer(r'class="[^"]*material-symbols-rounded[^"]*"[^>]*>\s*([a-z][a-z_0-9]*)\s*<', s):
        iconos.add(m.group(1))
    for m in re.finditer(r'indicador\(\s*"[^"]*"\s*,\s*[^,]+,\s*"[^"]*"\s*,\s*"([a-z_0-9]+)"', s):
        iconos.add(m.group(1))
    for m in re.finditer(r"\(\s*'[^']*'\s*,\s*'[^']*'\s*,\s*'([a-z][a-z_0-9]+)'\s*\)", s):
        iconos.add(m.group(1))
iconos = sorted(iconos)
open("static/fonts/material-symbols.icons.txt", "w").write(",".join(iconos))
print(f"  iconos: {len(iconos)}")
PY

ICONS=$(cat static/fonts/material-symbols.icons.txt)
UA="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36"
curl -sf -A "$UA" "https://fonts.googleapis.com/css2?family=Material+Symbols+Rounded:opsz,wght,FILL,GRAD@20..48,100..700,0..1,-50..200&icon_names=${ICONS}&display=block" -o /tmp/subset.css
URL=$(python3 -c "import re;print(re.search(r'url\((https://[^)]+)\)', open('/tmp/subset.css').read()).group(1))")
curl -sf -A "$UA" "$URL" -o static/fonts/material-symbols.woff2
chmod 644 static/fonts/material-symbols.woff2
ls -la static/fonts/material-symbols.woff2
