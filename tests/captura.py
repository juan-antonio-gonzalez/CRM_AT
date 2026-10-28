"""Captura una página real del CRM con Chrome, con los estáticos embebidos.

Es una herramienta de verificación, no una prueba: sirve para MIRAR cómo queda una
pantalla con el CSS y las fuentes de verdad, sin depender del servidor.

Las fuentes van como data URI a propósito. Si se dejan como `/static/...`, desde un
archivo temporal no cargan y los íconos se dibujan como su palabra ligadura
(«diversity_3»), que es justo lo que se quiere ver.

Uso:  python3 tests/captura.py <pagina.html> <salida.png> [ancho]
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


def _con_estaticos(html: str) -> str:
    css = ""
    for nombre in ("static/css/tailwind.css", "static/css/fonts.css",
                   "static/css/style.css"):
        with open(os.path.join(RAIZ, nombre), encoding="utf-8") as fh:
            css += f"\n/* ==== {nombre} ==== */\n" + fh.read()
    for hoja in ("tailwind.css", "fonts.css", "style.css"):
        html = re.sub(r'<link[^>]*/css/' + re.escape(hoja) + r'[^>]*>', "", html)

    for fuente in ("inter.woff2", "material-symbols.woff2"):
        with open(os.path.join(RAIZ, "static", "fonts", fuente), "rb") as fh:
            datos = base64.b64encode(fh.read()).decode("ascii")
        # La `url()` lleva la huella del archivo (`?v=...`), así que se acepta
        # cualquier consulta. Con doble barra el patrón no coincide con nada y la
        # fuente no se embebe: la captura sale con todos los íconos como texto.
        css = re.sub(r"url\('/static/fonts/" + re.escape(fuente) + r"(\?[^')]*)?'\)",
                     f"url(data:font/woff2;base64,{datos})", css)

    # Las imágenes también se piden a /static/... y desde un archivo temporal no
    # existen: sin esto la captura sale sin el logo.
    def _imagen(m):
        # La ruta viene con la huella de caché (`?v=...`): sin sacarla, el archivo
        # no se encuentra y la captura sale con la imagen rota.
        rel = m.group(1).split("?")[0].lstrip("/")
        camino = os.path.join(RAIZ, rel)
        if not os.path.exists(camino):
            return m.group(0)
        tipo = "image/svg+xml" if camino.endswith(".svg") else "image/png"
        with open(camino, "rb") as fh:
            datos = base64.b64encode(fh.read()).decode("ascii")
        return f'src="data:{tipo};base64,{datos}"'

    html = re.sub(r'src="(/static/img/[^"]+)"', _imagen, html)
    html = html.replace("</head>", f"<style>{css}</style>\n</head>", 1)
    # Un ancho de escritorio para que se vea la barra lateral.
    return re.sub(r'content="width=device-width[^"]*"', 'content="width=1400"', html)


def main(argv=None) -> int:
    argv = argv if argv is not None else sys.argv[1:]
    if len(argv) < 2:
        print(__doc__)
        return 2
    origen, destino = argv[0], argv[1]
    ancho = argv[2] if len(argv) > 2 else "1400"

    with open(origen, encoding="utf-8") as fh:
        html = _con_estaticos(fh.read())
    intermedio = os.path.join(tempfile.gettempdir(), "captura_estaticos.html")
    with open(intermedio, "w", encoding="utf-8") as fh:
        fh.write(html)

    import signal
    import time

    if os.path.exists(destino):
        os.remove(destino)
    proceso = subprocess.Popen(
        [CHROME, "--headless=new", "--disable-gpu", "--no-sandbox",
         "--disable-dev-shm-usage", "--no-first-run", "--no-default-browser-check",
         f"--user-data-dir={tempfile.gettempdir()}/chrome-captura-{os.getpid()}",
         "--virtual-time-budget=6000", f"--window-size={ancho},1000",
         f"--screenshot={destino}", f"file://{intermedio}"],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
    try:
        for _ in range(600):
            if os.path.exists(destino) and os.path.getsize(destino) > 0:
                time.sleep(0.8)
                break
            time.sleep(0.1)
    finally:
        try:
            os.killpg(os.getpgid(proceso.pid), signal.SIGKILL)
        except (ProcessLookupError, PermissionError):
            pass
        proceso.wait(timeout=10)

    if not os.path.exists(destino):
        print("Chrome no generó la captura")
        return 1
    print("captura:", destino, os.path.getsize(destino), "bytes")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
