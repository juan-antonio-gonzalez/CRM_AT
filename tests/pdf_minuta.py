"""Verifica en un navegador real que la minuta serialice bien sus filas.

Ejecuta la página con Chrome headless, llena una fila de cada tabla como lo haría
el usuario y comprueba el JSON que produce `serializeForm`. Esto detecta los
errores de lectura del DOM (por ejemplo buscar un `input` donde hay un
`textarea`), que no se ven mirando el código.

También imprime a PDF y verifica que el texto de los campos salga completo.
"""

import json
import os
import re
import signal
import subprocess
import sys
import tempfile
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

os.environ.setdefault("DATABASE_URL", "postgresql://u:p@127.0.0.1:5432/x")
os.environ.setdefault("SECRET_KEY", "probe")

from templating import templates  # noqa: E402

CHROME = os.environ.get(
    "CHROME_BIN", "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
)
TMP = tempfile.gettempdir()
SALIDA = os.path.join(TMP, "minuta_probe.html")
SALIDA_JSON = os.path.join(TMP, "minuta_probe.json")
PDF = os.path.join(TMP, "minuta_probe.pdf")
SALIDA_IMPRESION = os.path.join(TMP, "minuta_impresion.html")

TEMA = "Revisión del plan de mantenimiento preventivo del segundo trimestre"
RESPONSABLE = "Ing. Roberto Gómez"
ACUERDO = ("Se aprobó por unanimidad postergar el recambio del motorreductor "
           "hasta la parada programada de julio, siempre que se monitoree la "
           "temperatura de forma semanal y se registre en la planilla de control.")
OBSERVACION = ("Queda pendiente confirmar la disponibilidad del repuesto con el "
               "proveedor antes del cierre del mes en curso.")
TAREA = ("Solicitar cotización formal por el rodamiento y el acoplamiento, "
         "incluyendo plazo de entrega y garantía.")
DESARROLLO = ("Se repasó el estado de los equipos críticos de la planta. El "
              "motorreductor de la línea tres presenta un incremento de "
              "temperatura sostenido durante los últimos treinta días, con "
              "valores que superan en quince grados la consigna del fabricante. "
              "El equipo de mantenimiento propone monitorear semanalmente y "
              "postergar el recambio hasta la parada programada de julio.")


class _Estado:
    user = {"username": "probe", "role": "admin", "sub": "1"}
    csrf_token = "TOKEN"
    script_nonce = "nonce"


class _Request:
    state = _Estado()

    @staticmethod
    def url_for(name, **params):
        return "/static/" + str(params.get("path", "")).lstrip("/")


class _Minuta:
    id = 7
    fecha = "2026-06-11"
    status = "Borrador"


def _fila(campos):
    """Arma una fila con la misma estructura que genera el JS de la página."""
    return "".join(campos)


def _html() -> str:
    form_data = {
        "fecha": "2026-06-11", "horaInicio": "09:00", "horaFin": "11:30",
        "lugar": "Sala de reuniones", "tipoReunion": "Seguimiento",
        "objetivo": "Revisar el avance del plan de acción",
        "desarrollo": f"<p>{DESARROLLO}</p>",
        "proximaReunion": "2026-07-09",
        "redactor": "Ing. Roberto Gómez", "firma": "Ing. Roberto Gómez",
        "presentes": [{"nombre": "Roberto Gómez"}, {"nombre": "Alicia Torres"}],
        "ausentes": [{"nombre": "Carlos Pérez"}],
        "agenda": [{"tema": TEMA, "responsable": RESPONSABLE, "tiempo": "30"}],
        "acuerdos": [{"acuerdo": ACUERDO, "observaciones": OBSERVACION}],
        "tareas": [{"tarea": TAREA, "responsable": RESPONSABLE,
                    "plazo": "2026-06-30", "estado": "Pendiente"}],
    }
    html = templates.get_template("nueva_minuta.html").render(
        request=_Request(), minuta=_Minuta(), form_data=form_data,
        title="Editar Minuta #7", action_url="/minutas/7/editar",
        active_page="minutas", clientes=[],
    )

    # Sonda: llama a serializeForm y deja el resultado en un nodo para leerlo.
    sonda = """
<script>
// Con retardo: restoreData() repuebla el formulario de forma asíncrona (usa
// setTimeout), así que leer el DOM al terminar de parsear da todo vacío.
setTimeout(function () {
try {
  var datos = serializeForm();
  var salida = document.createElement('pre');
  salida.id = 'probe-resultado';
  salida.textContent = JSON.stringify(datos);
  salida.className = 'no-print';   // el CSS de impresión lo excluye del PDF
  salida.setAttribute('aria-hidden', 'true');
  document.body.appendChild(salida);
} catch (e) {
  var err = document.createElement('pre');
  err.id = 'probe-error';
  err.className = 'no-print';
  err.textContent = String(e && e.stack || e);
  document.body.appendChild(err);
}
}, 1200);
</script>
"""
    html_sin_sonda = html
    html = html.replace("</body>", sonda + "</body>", 1)

    # Embeber las hojas de estilo reales, para medir lo mismo que el navegador.
    #
    # La raíz es el repo, no `tests/`: con `dirname(__file__)` se buscaba
    # `tests/static/...` y la prueba moría con un FileNotFoundError. No se veía en
    # el servidor porque ahí no hay Chrome y la prueba se saltea.
    raiz = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    css = ""
    for nombre in ("static/css/tailwind.css", "static/css/fonts.css", "static/css/style.css"):
        with open(os.path.join(raiz, nombre), encoding="utf-8") as fh:
            css += f"\n/* ==== {nombre} ==== */\n" + fh.read()
    for hoja in ("tailwind.css", "fonts.css", "style.css"):
        html = re.sub(r'<link[^>]*/css/' + re.escape(hoja) + r'[^>]*>', "", html)
    css = _con_fuentes(css, raiz)
    html_sin_sonda = html_sin_sonda.replace("</head>", f"<style>{css}</style>\n</head>", 1)
    html = html.replace("</head>", f"<style>{css}</style>\n</head>", 1)
    return html, html_sin_sonda


def _con_fuentes(css: str, raiz: str) -> str:
    """Embebe las fuentes como data URI.

    Sin esto los íconos se imprimen como su palabra ligadura («person»,
    «handshake») desde un archivo temporal, y lo que se mide no es lo que ve el
    navegador del usuario. La `url()` lleva la huella del archivo (`?v=...`), así
    que se acepta cualquier consulta.
    """
    import base64
    for fuente in ("inter.woff2", "material-symbols.woff2"):
        camino = os.path.join(raiz, "static", "fonts", fuente)
        if not os.path.exists(camino):
            continue
        with open(camino, "rb") as fh:
            datos = base64.b64encode(fh.read()).decode("ascii")
        css = re.sub(r"url\('/static/fonts/" + re.escape(fuente) + r"(\?[^')]*)?'\)",
                     f"url(data:font/woff2;base64,{datos})", css)
    return css


def _chrome_proceso(args, stdout=None):
    """Lanza Chrome sin bloquear. Devuelve el Popen.

    ``stdout`` puede ser un archivo: es lo que se usa para --dump-dom, cuyo
    volcado supera el buffer de una tubería.
    """
    return subprocess.Popen(
        [CHROME, "--headless=new", "--disable-gpu", "--no-sandbox",
         "--disable-dev-shm-usage", "--no-first-run", "--no-default-browser-check",
         f"--user-data-dir={TMP}/chrome-minuta-{os.getpid()}", *args],
        stdout=stdout or subprocess.PIPE, stderr=subprocess.DEVNULL,
        start_new_session=True,
    )


def _matar(proc):
    try:
        os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
    except (ProcessLookupError, PermissionError):
        pass


def _volcar_dom(ruta, timeout=60):
    """Devuelve el DOM renderizado. Sólo --dump-dom: combinarlo con
    --print-to-pdf en la misma corrida hace que el volcado se pierda."""
    # Redirigir a un archivo en vez de leer por tubería: el DOM pesa más que el
    # buffer del pipe (64 KB) y Chrome se queda bloqueado escribiendo, así que una
    # lectura por tramos nunca termina. El archivo no tiene ese límite.
    dom_path = SALIDA + ".dom.html"
    if os.path.exists(dom_path):
        os.remove(dom_path)
    salida_dom = open(dom_path, "wb")
    proc = _chrome_proceso(["--virtual-time-budget=12000", "--dump-dom", f"file://{ruta}"],
                           stdout=salida_dom)
    # Se espera a que Chrome salga por sí solo: el volcado llega en tramos, así
    # que matarlo al aparecer el archivo lo deja incompleto.
    try:
        proc.wait(timeout=timeout)
    except subprocess.TimeoutExpired:
        _matar(proc)
        try:
            proc.wait(timeout=10)
        except Exception:
            pass
    salida_dom.close()
    if os.path.exists(dom_path):
        with open(dom_path, encoding="utf-8", errors="replace") as fh:
            return fh.read()
    return ""


def _imprimir_pdf(ruta, timeout=60):
    """Genera el PDF y espera a que aparezca."""
    if os.path.exists(PDF):
        os.remove(PDF)
    proc = _chrome_proceso([
        "--virtual-time-budget=8000", "--no-pdf-header-footer",
        f"--print-to-pdf={PDF}", f"file://{ruta}",
    ])
    try:
        limite = time.time() + timeout
        while time.time() < limite:
            if os.path.exists(PDF) and os.path.getsize(PDF) > 0:
                time.sleep(0.5)
                return True
            if proc.poll() is not None and os.path.exists(PDF):
                return True
            time.sleep(0.1)
        return False
    finally:
        _matar(proc)
        try:
            proc.wait(timeout=10)
        except Exception:
            pass


def disponible() -> bool:
    if not os.path.exists(CHROME):
        return False
    try:
        import pypdf  # noqa: F401
    except ImportError:
        return False
    return True


def main() -> int:
    html, html_sin_sonda = _html()
    with open(SALIDA, "w", encoding="utf-8") as fh:
        fh.write(html)
    print(f"HTML: {len(html)} bytes")

    # ── 1. Serialización, leída del DOM real ───────────────────────────────
    dom_serializacion = _volcar_dom(SALIDA)
    if not dom_serializacion:
        print("Chrome no devolvió el DOM")
        return 1

    fallos = []

    def chk(etiqueta, ok):
        print(f"  {'OK   ' if ok else 'FALLA'} {etiqueta}")
        if not ok:
            fallos.append(etiqueta)

    # Sólo cuenta como error si el elemento existe de verdad (el nombre también
    # aparece en el texto del script).
    err = re.search(r'<pre id="probe-error"[^>]*>(.*?)</pre>', dom_serializacion, re.S)
    if err:
        print("  el navegador reportó un error al serializar:")
        print("   ", err.group(1)[:400])
        return 1

    m = re.search(r'id="probe-resultado"[^>]*>(.*?)</pre>', dom_serializacion, re.S)
    if not m:
        print("  no se obtuvo el JSON de serializeForm")
        return 1
    datos = json.loads(m.group(1).replace("&quot;", '"').replace("&amp;", "&")
                       .replace("&lt;", "<").replace("&gt;", ">"))

    print()
    print("=== Serialización (leída del DOM real) ===")
    ag = (datos.get("agenda") or [{}])[0]
    chk("agenda: el tema llega completo", ag.get("tema") == TEMA)
    chk("agenda: el responsable llega", ag.get("responsable") == RESPONSABLE)
    chk("agenda: el tiempo llega", ag.get("tiempo") == "30")
    ac = (datos.get("acuerdos") or [{}])[0]
    chk("acuerdo completo", ac.get("acuerdo") == ACUERDO)
    chk("observaciones del acuerdo", ac.get("observaciones") == OBSERVACION)
    ta = (datos.get("tareas") or [{}])[0]
    chk("tarea completa", ta.get("tarea") == TAREA)
    chk("responsable de la tarea", ta.get("responsable") == RESPONSABLE)
    chk("plazo de la tarea", ta.get("plazo") == "2026-06-30")
    chk("estado de la tarea", ta.get("estado") == "Pendiente")
    chk("desarrollo de la reunión", DESARROLLO in (datos.get("desarrollo") or ""))
    chk("presentes y ausentes",
        len(datos.get("presentes") or []) == 2 and len(datos.get("ausentes") or []) == 1)

    # ── 2. Impresión ───────────────────────────────────────────────────────
    # Archivo propio, SIN la sonda: si se imprimiera el mismo, el PDF incluiría
    # una hoja con el JSON y se mediría de más. Antes se pisaba el archivo de la
    # sonda, que es lo que rompía la lectura.
    with open(SALIDA_IMPRESION, "w", encoding="utf-8") as fh:
        fh.write(html_sin_sonda)
    hay_pdf = _imprimir_pdf(SALIDA_IMPRESION)
    if not hay_pdf:
        print("  Chrome no generó el PDF")
        return 1

    from pypdf import PdfReader
    lector = PdfReader(PDF)
    lig = {"\ufb00": "ff", "\ufb01": "fi", "\ufb02": "fl",
           "\ufb03": "ffi", "\ufb04": "ffl"}

    def norm(s):
        for k, v in lig.items():
            s = s.replace(k, v)
        return re.sub(r"\s+", " ", s).strip()

    plano = norm("\n".join((p.extract_text() or "") for p in lector.pages))
    print()
    print(f"=== PDF: {len(lector.pages)} página(s) ===")
    chk("el tema de la agenda sale completo", norm(TEMA) in plano)
    chk("el acuerdo sale completo", norm(ACUERDO) in plano)
    chk("las observaciones salen completas", norm(OBSERVACION) in plano)
    chk("la tarea sale completa", norm(TAREA) in plano)
    chk("el desarrollo sale completo", norm(DESARROLLO) in plano)
    chk("el FINAL del desarrollo está", "parada programada de julio" in plano)
    chk("el FINAL del acuerdo está", "planilla de control" in plano)
    chk("sin botón Guardar", "Guardar" not in plano)
    chk("sin barra lateral", "Gestión Operativa" not in plano)

    print()
    if fallos:
        print(f"RESULTADO: fallaron {len(fallos)}: {fallos}")
        return 1
    print("RESULTADO: todas las verificaciones pasaron")
    return 0


if __name__ == "__main__":
    sys.exit(main())
