"""Verifica el PDF del informe de visita: que cada campo salga completo.

Renderiza la plantilla con datos de prueba, embebe las hojas de estilo reales,
la imprime con Chrome headless y comprueba sobre el PDF.

Todos los estilos de impresión del informe están embebidos en la plantilla, pero
las reglas que ocultan el armazón de la aplicación (barra lateral, cabecera)
viven en static/css/style.css, así que hay que incluirlas para medir lo mismo
que ve el navegador del usuario.
"""

import os
import re
import shutil
import subprocess
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

os.environ.setdefault("DATABASE_URL", "postgresql://u:p@127.0.0.1:5432/x")
os.environ.setdefault("SECRET_KEY", "probe")

from templating import templates  # noqa: E402

CHROME = os.environ.get("CHROME_BIN",
                         "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome")
SALIDA = os.path.join(tempfile.gettempdir(), "informe_visita.html")
PDF = os.path.join(tempfile.gettempdir(), "informe_visita.pdf")

TEXTO_LARGO = (
    "Se realizó la inspección completa de la línea de envasado número tres. "
    "Se detectó desgaste irregular en el rodamiento principal del motorreductor, "
    "acompañado de un incremento de temperatura de aproximadamente quince grados "
    "por encima del valor de consigna establecido por el fabricante. "
    "Se recomienda programar el recambio durante la próxima parada de planta "
    "prevista para el mes de julio y verificar la alineación del acoplamiento "
    "con reloj comparador antes de volver a poner el equipo en servicio."
)
PALABRA_LARGA = "Electroencefalografistaespecializadoenmantenimientoindustrial"
URL_LARGA = ("https://intranet.ejemplo.com/documentos/mantenimiento/2026/"
             "procedimiento-completo-reemplazo-rodamiento-motorreductor-linea-3.pdf")
TEXTO_TABLA = (
    "El operador informa que la alarma se dispara de manera intermitente durante "
    "el arranque, siempre en el mismo punto del ciclo, y que al reiniciar el equipo "
    "el problema desaparece temporalmente hasta la siguiente puesta en marcha."
)
ANEXO_HTML = (
    f"<p>{TEXTO_LARGO}</p><p>{PALABRA_LARGA}</p><p>{URL_LARGA}</p>"
    "<ul><li>Primer punto de la lista de verificación posterior al recambio.</li>"
    "<li>Segundo punto con una observación extensa que debería repartirse entre "
    "varias líneas al imprimirse, sin que se pierda el final de la frase.</li></ul>"
)


class _Estado:
    user = {"username": "probe", "role": "admin", "sub": "1"}
    csrf_token = "TOKEN"
    script_nonce = "nonce"


class _Request:
    state = _Estado()

    @staticmethod
    def url_for(name, **params):
        return "/static/" + str(params.get("path", "")).lstrip("/")


class _Visit:
    id = 42
    fecha = "2026-05-10"
    status = "Finalizado"


def _html(raiz: str = None) -> str:
    form_data = {
        "fecha": "2026-05-10",
        "status": "Finalizado",
        "cliente_nombre": "ACME SA (Planta Norte)",
        "at": "ING. GOMEZ",
        "objetivo": TEXTO_LARGO,
        "swa": [{"texto": TEXTO_LARGO}],
        "cli": [{"texto": TEXTO_LARGO}],
        "tables": {
            "5": [["2026-05-01", "PD-1234", TEXTO_TABLA, TEXTO_TABLA]],
            "6": [["PD-1234", "CALIDAD DE PRODUCTO", TEXTO_TABLA]],
            "7": [["PD-1234", "RESPUESTA OPORTUNA", TEXTO_TABLA]],
            "8": [["PD-1234", TEXTO_TABLA, TEXTO_LARGO]],
            "9": [["ET-001", TEXTO_LARGO, "Roberto", "15/06/2026"]],
        },
        # Anexo 1 vacío (no debe imprimirse ni consumir numeración) y anexo 2 con
        # contenido, que debe salir como "ANEXO I".
        "anexos": [
            {"idx": 1, "html": "<div><br></div>", "images": [None, None, None, None]},
            {"idx": 2, "html": ANEXO_HTML, "images": [None, None, None, None]},
        ],
        "tipo_producto": "Corrugado",
        "planta": "Norte",
        "planta_distribuidora": "BERNAL",
        "firma": "Ing. Roberto Gómez",
    }
    html = templates.get_template("nueva_visita2.html").render(
        request=_Request(), visit=_Visit(), form_data=form_data,
        title="Informe de Visita Técnica", action_url="/visitas2/42/editar",
        active_page="visitas2", clientes=[], tecnicos=[], distribuidoras=[],
        temas_calidad=[], calidad_at=[], tareas_vinculadas=[],
    )
    # Embeber las hojas de estilo reales para medir lo mismo que el navegador.
    css = ""
    raiz = raiz or os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # tests/ -> repo
    for nombre in (os.path.join(raiz, x) for x in (
            "static/css/tailwind.css", "static/css/fonts.css", "static/css/style.css")):
        with open(nombre, encoding="utf-8") as fh:
            css += f"\n/* ==== {nombre} ==== */\n" + fh.read()
    for hoja in ("tailwind.css", "fonts.css", "style.css"):
        html = re.sub(r'<link[^>]*/css/' + re.escape(hoja) + r'[^>]*>', "", html)
    return html.replace("</head>", f"<style>{css}</style>\n</head>", 1)


def _pdf(html: str) -> None:
    """Imprime el HTML a PDF con Chrome headless.

    Chrome no termina de salir después de escribir el PDF: quedan procesos
    ayudantes que mantienen vivos los descriptores, así que esperar al proceso se
    cuelga indefinidamente. Se espera en cambio a que aparezca el archivo y
    después se mata el grupo completo.
    """
    import signal
    import time

    with open(SALIDA, "w", encoding="utf-8") as fh:
        fh.write(html)
    if os.path.exists(PDF):
        os.remove(PDF)

    proceso = subprocess.Popen(
        [
            CHROME, "--headless=new", "--disable-gpu", "--no-sandbox",
            "--disable-dev-shm-usage", "--no-first-run", "--no-default-browser-check",
            # Un directorio de datos único por corrida: reutilizarlo hace que
            # Chrome encuentre el bloqueo del proceso anterior y se quede esperando.
            f"--user-data-dir={tempfile.gettempdir()}/chrome-crm-at-{os.getpid()}",
            "--no-pdf-header-footer", "--virtual-time-budget=5000",
            f"--print-to-pdf={PDF}", f"file://{SALIDA}",
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
    )
    try:
        for _ in range(400):  # hasta 40 segundos
            if os.path.exists(PDF) and os.path.getsize(PDF) > 0:
                time.sleep(0.5)  # dejar que termine de escribir
                return
            if proceso.poll() is not None and os.path.exists(PDF):
                return
            time.sleep(0.1)
    finally:
        try:
            os.killpg(os.getpgid(proceso.pid), signal.SIGKILL)
        except (ProcessLookupError, PermissionError):
            pass
        proceso.wait(timeout=10)


# Las fuentes del PDF usan ligaduras tipográficas (fi -> U+FB01): visualmente es
# correcto, pero hay que normalizarlas para comparar texto. Los guiones también
# pueden quedar partidos al final de una línea.
_LIG = {"\ufb00": "ff", "\ufb01": "fi", "\ufb02": "fl", "\ufb03": "ffi", "\ufb04": "ffl"}


def norm(s: str) -> str:
    for k, v in _LIG.items():
        s = s.replace(k, v)
    s = re.sub(r"-\s+", "-", s)   # guion partido al final de línea
    return re.sub(r"\s+", " ", s).strip()


def disponible() -> bool:
    """Indica si están las herramientas para imprimir y medir el PDF."""
    if not os.path.exists(CHROME):
        return False
    try:
        import pypdf  # noqa: F401
    except ImportError:
        return False
    return True


def main(raiz: str = None) -> int:
    html = _html(raiz)
    print(f"HTML renderizado: {len(html)} bytes")
    _pdf(html)
    if not os.path.exists(PDF):
        print("Chrome no generó el PDF")
        return 1

    from pypdf import PdfReader
    reader = PdfReader(PDF)
    plano = norm("\n".join((p.extract_text() or "") for p in reader.pages))
    print(f"PDF: {len(reader.pages)} página(s), {os.path.getsize(PDF)} bytes, "
          f"{len(plano)} caracteres")
    print()

    fallos = []

    def chk(etiqueta, aguja, debe=True):
        objetivo = norm(aguja)
        ok = (objetivo in plano) if debe else (objetivo not in plano)
        print(f"  {'OK   ' if ok else 'FALLA'} {etiqueta}")
        if not ok:
            fallos.append(etiqueta)

    print("=== Campos completos ===")
    chk("objetivo (texto largo)", TEXTO_LARGO)
    chk("tabla 5 (situación actual)", TEXTO_TABLA)
    chk("tabla 8 (acción)", TEXTO_LARGO)
    chk("tabla 9 (acción del plan)", TEXTO_LARGO)
    chk("anexo con contenido", TEXTO_LARGO)
    chk("URL larga del anexo", URL_LARGA)
    chk("palabra larga sin espacios", PALABRA_LARGA)

    print()
    print("=== El FINAL de cada texto (detecta recortes por altura) ===")
    chk("final del objetivo", "volver a poner el equipo en servicio")
    chk("final del anexo (URL)", "motorreductor-linea-3.pdf")
    chk("final de la tabla", "siguiente puesta en marcha")
    chk("final de la lista del anexo", "sin que se pierda el final de la frase")

    print()
    print("=== Numeración de anexos ===")
    chk("el anexo visible es el I", "ANEXO I: DESARROLLO")
    chk("no numera un anexo inexistente", "ANEXO III", debe=False)

    print()
    print("=== Controles y armazón no se imprimen ===")
    chk("sin botón Guardar", "Guardar", debe=False)
    chk("sin barra lateral", "Gestión Operativa", debe=False)
    chk("sin ítems del menú", "Biblioteca de Clientes", debe=False)
    chk("sin '+ Agregar Anexo'", "Agregar Anexo", debe=False)
    chk("sin marcador de foto", "📷", debe=False)

    print()
    if fallos:
        print(f"RESULTADO: fallaron {len(fallos)}: {fallos}")
        return 1
    print("RESULTADO: todas las verificaciones pasaron")
    return 0


if __name__ == "__main__":
    sys.exit(main())
