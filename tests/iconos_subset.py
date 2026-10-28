"""Dibuja todos los íconos del subset para ver cuáles faltan de la fuente.

Por qué existe
--------------
Los íconos de Material Symbols se dibujan por ligadura: el `<span>` contiene el
nombre del ícono y la fuente lo reemplaza por el glifo. **Si el glifo no está en el
archivo no hay ningún error**: se imprime el nombre. En el menú lateral eso se ve
como un título enorme en mayúsculas con guiones bajos, que es exactamente cómo
apareció «DIVERSITY_3» ocupando el lugar del ícono de Equipos.

Google descarta los nombres inválidos sin avisar, así que un nombre mal escrito no
rompe la generación: la fuente sale sin ese glifo y nadie se entera hasta que
alguien lo ve en pantalla.

Cómo lo detecta
---------------
Se dibuja una casilla por ícono y se mide el ancho de cada `<span>` desde
JavaScript. Un glifo ocupa alrededor de un cuadro; un nombre que no se reemplazó
ocupa el ancho del texto, varias veces más. Comparando contra la mediana —que es la
del glifo normal— los que se salen se delatan solos, sin depender de una lista de
anchos escrita a mano.

Se puede ejecutar solo para mirar la lámina:

    python3 tests/iconos_subset.py            # verifica
    python3 tests/iconos_subset.py --captura  # además guarda la imagen
"""

import base64
import os
import re
import subprocess
import sys
import tempfile

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CHROME = os.environ.get(
    "CHROME_BIN", "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome")
SALIDA = os.path.join(tempfile.gettempdir(), "iconos_subset.html")
CAPTURA = os.path.join(tempfile.gettempdir(), "iconos_subset.png")
DOM = os.path.join(tempfile.gettempdir(), "iconos_subset.dom")

# Un glifo que no se reemplazó ocupa el ancho del texto. Con 30 px de fuente el
# glifo mide ~30 y «precision_manufacturing» pasa de 300: el 1.8 sobre la mediana
# deja margen de sobra sin depender de un número ajustado a mano.
FACTOR_SOSPECHOSO = 1.8


def _iconos() -> list:
    with open(os.path.join(RAIZ, "static/fonts/material-symbols.icons.txt"),
              encoding="utf-8") as fh:
        return sorted(i for i in fh.read().strip().split(",") if i)


def construir() -> str:
    with open(os.path.join(RAIZ, "static/fonts/material-symbols.woff2"), "rb") as fh:
        datos = base64.b64encode(fh.read()).decode("ascii")

    filas = "".join(
        f'<div class="c">'
        f'<span class="material-symbols-rounded" data-icono="{i}">{i}</span>'
        f'<code>{i}</code></div>' for i in _iconos())

    return f'''<!DOCTYPE html><html><head><meta charset="utf-8"><style>
@font-face {{
  font-family: 'Material Symbols Rounded';
  font-style: normal; font-weight: 100 700;
  src: url(data:font/woff2;base64,{datos}) format('woff2');
}}
.material-symbols-rounded {{
  font-family: 'Material Symbols Rounded';
  font-weight: normal; font-style: normal;
  font-size: 30px; line-height: 1; letter-spacing: normal;
  text-transform: none; display: inline-block; white-space: nowrap;
  direction: ltr; font-feature-settings: 'liga';
}}
body {{ font-family: system-ui, sans-serif; padding: 16px; background: #fff;
        color: #000; }}
.grid {{ display: grid; grid-template-columns: repeat(6, 1fr); gap: 8px; }}
.c {{ border: 1px solid #ddd; border-radius: 6px; padding: 6px; text-align: center;
      overflow: hidden; height: 74px; }}
code {{ display: block; font-size: 8px; color: #666; margin-top: 4px;
        word-break: break-all; }}
</style></head><body>
<p style="font-size: 13px">Cada casilla: el glifo y, debajo, su nombre. Si el
nombre se ve grande arriba, el glifo FALTA en la fuente.</p>
<div class="grid">{filas}</div>
<pre id="faltantes"></pre>
<script>
// Se mide cada span y quedan los que son demasiado anchos para ser un glifo.
//
// Hay que esperar a `document.fonts.ready`: medir antes de que la fuente se
// aplique da el ancho del TEXTO de todos los spans, la mediana se va a ~125 px y
// el resultado es una lista de falsos positivos con los nombres más largos.
function medir() {{
  var spans = Array.prototype.slice.call(document.querySelectorAll('[data-icono]'));
  var anchos = spans.map(function (s) {{
    return s.getBoundingClientRect().width;
  }}).sort(function (a, b) {{ return a - b; }});
  var mediana = anchos[Math.floor(anchos.length / 2)] || 0;
  var malos = spans.filter(function (s) {{
    return s.getBoundingClientRect().width > mediana * {FACTOR_SOSPECHOSO};
  }}).map(function (s) {{ return s.getAttribute('data-icono'); }});
  document.getElementById('faltantes').textContent =
    'MEDIANA=' + mediana.toFixed(1) + ';FALTAN=' + malos.join(',');
}}
if (document.fonts && document.fonts.ready) {{
  document.fonts.ready.then(medir);
}} else {{
  window.addEventListener('load', medir);
}}
</script>
</body></html>'''


def _chrome(args, esperar_archivo, stdout_a=None):
    """Corre Chrome y espera, no a que termine.

    Chrome no termina de salir después de escribir su salida: quedan procesos
    ayudantes que mantienen vivos los descriptores y esperar al proceso se cuelga.
    Por eso se espera al archivo que produce —`--dump-dom` escribe en la salida
    estándar, así que se la redirige a un archivo— y después se mata el grupo.
    """
    import signal
    import time

    for ruta in (esperar_archivo, stdout_a):
        if ruta and os.path.exists(ruta):
            os.remove(ruta)

    destino = open(stdout_a, "w", encoding="utf-8") if stdout_a else subprocess.DEVNULL
    try:
        proceso = subprocess.Popen(
            [CHROME, "--headless=new", "--disable-gpu", "--no-sandbox",
             "--disable-dev-shm-usage", "--no-first-run",
             "--no-default-browser-check",
             f"--user-data-dir={tempfile.gettempdir()}/chrome-iconos-{os.getpid()}",
             "--virtual-time-budget=5000"] + args,
            stdout=destino, stderr=subprocess.DEVNULL, start_new_session=True)
    finally:
        if stdout_a:
            destino.close()

    try:
        for _ in range(600):
            if os.path.exists(esperar_archivo) and os.path.getsize(esperar_archivo) > 0:
                time.sleep(0.8)
                return True
            time.sleep(0.1)
    finally:
        try:
            os.killpg(os.getpgid(proceso.pid), signal.SIGKILL)
        except (ProcessLookupError, PermissionError):
            pass
        proceso.wait(timeout=10)
    return os.path.exists(esperar_archivo)


def faltantes() -> list:
    """Los íconos del subset cuyo glifo no está en la fuente."""
    with open(SALIDA, "w", encoding="utf-8") as fh:
        fh.write(construir())
    if not _chrome(["--dump-dom", f"file://{SALIDA}"], DOM, stdout_a=DOM):
        raise RuntimeError("Chrome no devolvió el DOM")
    with open(DOM, encoding="utf-8", errors="replace") as fh:
        dom = fh.read()
    m = re.search(r"FALTAN=([^<]*)", dom)
    if not m:
        raise RuntimeError("no se encontró el resultado en el DOM")
    return [x for x in m.group(1).strip().split(",") if x]


def captura() -> str:
    if not _chrome(["--window-size=1100,1500", f"--screenshot={CAPTURA}",
                    f"file://{SALIDA}"], CAPTURA):
        return ""
    return CAPTURA


def disponible() -> bool:
    return os.path.exists(CHROME)


def main(argv=None) -> int:
    argv = argv if argv is not None else sys.argv[1:]
    if not disponible():
        print("No hay Chrome: no se puede verificar la fuente de íconos.")
        return 0

    total = len(_iconos())
    malos = faltantes()
    print(f"Íconos en el subset: {total}")
    if "--captura" in argv:
        ruta = captura()
        if ruta:
            print("Captura:", ruta)

    if malos:
        print("\nSIN GLIFO EN LA FUENTE (se imprimen como texto):")
        for m in malos:
            print(f"  - {m}")
        print("\nRevisá el nombre y volvé a correr: bash deploy/subset-iconos.sh")
        return 1

    print("Los íconos del subset tienen su glifo.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
