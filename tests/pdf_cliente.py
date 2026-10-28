"""Mide la impresión del informe de clientes en un navegador real.

El informe puede no entrar en una hoja: un cliente con veinte máquinas y treinta
visitas ocupa varias. Lo que hay que verificar no es que el HTML se vea bien en
pantalla, sino que **al imprimir no se pierda nada**, que las hojas se agreguen
solas y que el pie no mienta sobre la cantidad de páginas.

Se renderiza la plantilla con datos de prueba, se embeben las hojas de estilo
reales, se imprime con Chrome headless y se mide sobre el PDF.
"""

import os
import re
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

os.environ.setdefault("DATABASE_URL", "postgresql://u:p@127.0.0.1:5432/x")
os.environ.setdefault("SECRET_KEY", "probe")

from templating import templates  # noqa: E402

CHROME = os.environ.get(
    "CHROME_BIN", "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome")
SALIDA = os.path.join(tempfile.gettempdir(), "cliente_reporte.html")
PDF = os.path.join(tempfile.gettempdir(), "cliente_reporte.pdf")

# Marcadores que tienen que sobrevivir a la impresión. El último es el que
# importa: si el contenido se corta, el final del informe no aparece.
MAQUINAS = 24
VISITAS = 30
MARCA_ULTIMA_MAQUINA = "FIN-DEL-PARQUE"
MARCA_ULTIMA_VISITA = "FIN-DEL-HISTORIAL"

TEXTO_LARGO = (
    "Se relevó el estado general de la línea de envasado y se dejó constancia de "
    "las observaciones del jefe de mantenimiento respecto del plan de recambio. "
) * 3


class _Estado:
    user = {"username": "probe", "role": "admin", "sub": "1"}
    csrf_token = "TOKEN"
    script_nonce = "nonce"


class _Request:
    state = _Estado()

    @staticmethod
    def url_for(name, **params):
        return "/static/" + str(params.get("path", "")).lstrip("/")


class _Cliente:
    id = 7
    name = "CARTOCOR SA"
    plant = "Planta Norte"
    industry_sector = "Corrugado"
    city = "Rosario"
    country = "Argentina"
    address = "Av. Central 1234, Parque Industrial Norte"
    technical_advisor = "ING. GOMEZ"
    assigned_commercial = "CARLOS PÉREZ"
    designer = "DISEÑO UNO"
    observations = TEXTO_LARGO
    client_team = [
        {"name": f"Contacto {i}", "role": "Mantenimiento",
         "email": f"contacto{i}@cartocor.com.ar", "phone": f"+54 341 555-00{i:02d}"}
        for i in range(1, 13)
    ]


class _Maquina:
    def __init__(self, i, ultima=False):
        self.brand = f"MARCA {i}"
        self.model = f"Modelo {i:03d}"
        self.machine_type = "Impresora"
        self.serial_number = MARCA_ULTIMA_MAQUINA if ultima else f"SN-{i:05d}"
        self.line = f"Línea {i}"


class _Visita:
    def __init__(self, i, ultima=False):
        import datetime
        self.date = datetime.date(2026, 1, 1) + datetime.timedelta(days=i)
        self.visit_type = "Preventiva"
        self.objective = MARCA_ULTIMA_VISITA if ultima else f"Objetivo de la visita {i}"
        self.status = "Completada"


class _Generacion:
    @staticmethod
    def strftime(_):
        return "01/06/2026"

    year = 2026


def _html(raiz: str = None, con_datos: bool = True) -> str:
    if con_datos:
        cliente = _Cliente()
        maquinas = [_Maquina(i, ultima=(i == MAQUINAS)) for i in range(1, MAQUINAS + 1)]
        visitas = [_Visita(i, ultima=(i == VISITAS)) for i in range(1, VISITAS + 1)]
    else:
        cliente = _Cliente()
        cliente.client_team = []
        cliente.observations = ""
        maquinas, visitas = [], []

    html = templates.get_template("cliente_reporte.html").render(
        request=_Request(), customer=cliente, machines=maquinas, visits=visitas,
        generation_date=_Generacion(), active_page="clientes",
    )

    raiz = raiz or os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    css = ""
    for nombre in (os.path.join(raiz, x) for x in (
            "static/css/tailwind.css", "static/css/fonts.css", "static/css/style.css")):
        with open(nombre, encoding="utf-8") as fh:
            css += f"\n/* ==== {nombre} ==== */\n" + fh.read()
    for hoja in ("tailwind.css", "fonts.css", "style.css"):
        html = re.sub(r'<link[^>]*/css/' + re.escape(hoja) + r'[^>]*>', "", html)

    # Las fuentes se piden a /static/..., que en un archivo temporal no existe: los
    # íconos se imprimirían como su palabra ligadura («person», «handshake») y las
    # alturas medidas no serían las reales. Se embeben como data URI, que es lo
    # único que Chrome resuelve igual desde un archivo temporal.
    #
    # El reemplazo va sobre el CSS **antes** de insertarlo: hacerlo después sobre el
    # HTML no toca lo que ya está adentro del `<style>`.
    import base64
    for fuente in ("inter.woff2", "material-symbols.woff2"):
        camino = os.path.join(raiz, "static", "fonts", fuente)
        with open(camino, "rb") as fh:
            datos = base64.b64encode(fh.read()).decode("ascii")
        # La `url()` lleva la huella del archivo (`?v=...`), así que no alcanza con
        # buscar la ruta pelada: se acepta cualquier consulta.
        css = re.sub(r"url\('/static/fonts/" + re.escape(fuente) + r"(\?[^')]*)?'\)",
                     f"url(data:font/woff2;base64,{datos})", css)
    html = html.replace("</head>", f"<style>{css}</style>\n</head>", 1)

    # El paginador tiene que correr de verdad: el informe se reparte en hojas con
    # JavaScript, así que medir sin ejecutarlo mediría otra cosa. Se inserta el
    # archivo real en línea, porque `src="/static/..."` no resuelve desde un
    # archivo temporal.
    with open(os.path.join(raiz, "static", "js", "informe-paginado.js"),
              encoding="utf-8") as fh:
        js = fh.read()
    html = re.sub(r'<script[^>]*src="[^"]*informe-paginado\.js"[^>]*></script>', "", html)
    return html.replace("</body>", f"<script>{js}</script>\n</body>", 1)


def _pdf(html: str, destino: str = None) -> None:
    """Igual que en `pdf_informe.py`: Chrome no termina solo, hay que matarlo."""
    import signal
    import subprocess
    import time

    destino = destino or PDF
    with open(SALIDA, "w", encoding="utf-8") as fh:
        fh.write(html)
    if os.path.exists(destino):
        os.remove(destino)

    proceso = subprocess.Popen(
        [CHROME, "--headless=new", "--disable-gpu", "--no-sandbox",
         "--disable-dev-shm-usage", "--no-first-run", "--no-default-browser-check",
         f"--user-data-dir={tempfile.gettempdir()}/chrome-crm-at-cli-{os.getpid()}",
         "--no-pdf-header-footer", "--virtual-time-budget=5000",
         f"--print-to-pdf={destino}", f"file://{SALIDA}"],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
    try:
        for _ in range(400):
            if os.path.exists(destino) and os.path.getsize(destino) > 0:
                time.sleep(0.5)
                return
            if proceso.poll() is not None and os.path.exists(destino):
                return
            time.sleep(0.1)
    finally:
        try:
            os.killpg(os.getpgid(proceso.pid), signal.SIGKILL)
        except (ProcessLookupError, PermissionError):
            pass
        proceso.wait(timeout=10)


_LIG = {"\ufb00": "ff", "\ufb01": "fi", "\ufb02": "fl", "\ufb03": "ffi", "\ufb04": "ffl"}


def norm(s: str) -> str:
    for k, v in _LIG.items():
        s = s.replace(k, v)
    s = re.sub(r"-\s+", "-", s)
    return re.sub(r"\s+", " ", s).strip()


def disponible() -> bool:
    if not os.path.exists(CHROME):
        return False
    try:
        import pypdf  # noqa: F401
    except ImportError:
        return False
    return True


def _texto_por_pagina(pdf: str):
    from pypdf import PdfReader
    lector = PdfReader(pdf)
    return [norm(p.extract_text() or "") for p in lector.pages]


def main(raiz: str = None) -> int:
    if not disponible():
        print("Faltan Chrome o pypdf: no se puede medir la impresión.")
        return 0

    html = _html(raiz)
    print(f"HTML renderizado: {len(html)} bytes")
    _pdf(html)
    if not os.path.exists(PDF):
        print("Chrome no generó el PDF")
        return 1

    paginas = _texto_por_pagina(PDF)
    completo = " ".join(paginas)
    print(f"Páginas impresas: {len(paginas)}")

    fallos = []

    # 1. Que el informe se haya paginado. Si el paginador no corrió, no hay
    #    numeración y todo lo demás mide otra cosa.
    if "Página 1 de 1" in completo and len(paginas) > 1:
        fallos.append("el paginador no corrió: el pie sigue diciendo «Página 1 de 1»")

    # 2. Que el informe ocupe más de una hoja: si entrara en una, la prueba no
    #    estaría ejercitando el salto.
    if len(paginas) < 3:
        fallos.append(
            f"el informe de prueba ocupa {len(paginas)} página(s): no está "
            f"ejercitando el salto de hoja")

    # 3. Que el número de páginas impresas coincida con el que declara el pie. Es
    #    la comprobación central: el pie no puede mentir.
    import re as _re
    m = _re.search(r"Página (\d+) de (\d+)", completo)
    if not m:
        fallos.append("el pie no tiene numeración de páginas")
    else:
        ultima, total = int(m.group(1)), int(m.group(2))
        if total != len(paginas):
            fallos.append(
                f"el pie dice que hay {total} páginas y se imprimieron {len(paginas)}")
        if total < 3:
            fallos.append(f"el pie declara {total} páginas, menos de las esperadas")
        # Y que la última hoja exista con su número.
        if f"Página {total} de {total}" not in completo:
            fallos.append(f"falta el pie de la última hoja («Página {total} de {total}»)")

    # 4. Que no se pierda el final: el contenido tiene que llegar hasta el fondo.
    for marca, que in ((MARCA_ULTIMA_MAQUINA, "la última máquina"),
                       (MARCA_ULTIMA_VISITA, "la última visita"),
                       ("Ref: MAST-7", "el pie con la referencia")):
        if marca not in completo:
            fallos.append(f"no se imprimió {que} ({marca!r}): el contenido se cortó")

    # 5. Que ninguna tarjeta de máquina quede partida entre dos hojas: su marca y su
    #    línea tienen que estar en la misma.
    for i, texto in enumerate(paginas):
        for numero in range(1, MAQUINAS + 1):
            if f"MARCA {numero} " not in texto:
                continue
            if not _re.search(rf"Línea: Línea {numero}(?!\d)", texto):
                fallos.append(
                    f"la tarjeta de la máquina {numero} quedó partida: su título está "
                    f"en la hoja {i + 1} y su línea no")

    # 6. Que el encabezado de una tabla que cruza de hoja se repita.
    encabezado = "Objetivo Principal"
    if completo.count(encabezado) < 2:
        fallos.append(
            f"el encabezado de la tabla aparece {completo.count(encabezado)} vez/veces "
            f"en {len(paginas)} páginas: no se repite al cambiar de hoja")

    if not completo.strip():
        fallos.append("el PDF no tiene texto: no se imprimió nada")

    if fallos:
        print("\nPROBLEMAS:")
        for f in fallos:
            print(f"  - {f}")
        return 1

    print("La impresión está bien.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
