"""Pruebas del sistema de diseño.

El objetivo no es sólo que la interfaz se vea bien hoy, sino que no se
desalinee sola: cada regla que se rompió en la auditoría queda cubierta por una
prueba, así que volver a introducirla hace fallar la suite.

La auditoría encontró 21 modales con 4 tamaños de título, 6 anchos, 2 opacidades
de fondo, 4 estructuras distintas y 16 sin relleno; 2599 clases `dark:`; y 780
textos por debajo de 12px (el más frecuente, 9px).
"""

import os
import re
import glob

import pytest

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PLANTILLAS = os.path.join(RAIZ, "templates")

# Plantillas de impresión: su diseño es el del formulario oficial en papel y se
# mantienen congeladas por decisión del usuario.
CONGELADAS = {"nueva_visita2.html", "nueva_minuta.html"}
# El propio componente define los estilos, así que no se le aplican las reglas.
SISTEMA = {"_ui.html"}


class _RequestUI:
    """Request mínimo para renderizar el layout sin levantar la aplicación."""
    class state:
        csrf_token = "test"
        script_nonce = "test"
        user = {"username": "prueba", "role": "admin", "sub": "1"}

    @staticmethod
    def url_for(name, **params):
        return "/static/" + str(params.get("path", "")).lstrip("/")


def _plantillas_aplicacion():
    for ruta in sorted(glob.glob(os.path.join(PLANTILLAS, "*.html"))):
        nombre = os.path.basename(ruta)
        if nombre in CONGELADAS or nombre in SISTEMA:
            continue
        yield nombre, open(ruta, encoding="utf-8").read()


# ── Modales ────────────────────────────────────────────────────────────────
def _modales(texto):
    """Devuelve (id, clases del contenedor, clases del panel, título) por modal."""
    salida = []
    for m in re.finditer(r'<div([^>]*role="dialog"[^>]*)>', texto):
        atrs = m.group(1)
        idm = re.search(r'id="([^"]+)"', atrs)
        cm = re.search(r'class="([^"]*)"', atrs)
        contenedor = cm.group(1) if cm else ""
        resto = texto[m.end():m.end() + 2500]
        pm = re.search(r'class="([^"]*(?:bg-superficie-card|bg-white)[^"]*)"', resto)
        panel = pm.group(1) if pm else ""
        tm = re.search(
            r'<h[23][^>]*class="([^"]*)"[^>]*id="[^"]*"'
            r'|<h[23][^>]*id="[^"]*"[^>]*class="([^"]*)"', resto)
        titulo = (tm.group(1) or tm.group(2) or "") if tm else ""
        salida.append((idm.group(1) if idm else "?", contenedor, panel, titulo))
    return salida


def test_ninguna_plantilla_escribe_un_modal_a_mano():
    """Todos los modales salen del componente `_ui.html`.

    Estas pruebas verificaban antes que los modales escritos a mano compartieran
    fondo, radio y tamaño de título, y en su momento encontraron tres opacidades
    mezcladas y cuatro tamaños distintos. Con los 16 modales ya migrados no queda
    ninguno a mano, así que lo que corresponde verificar es eso: que nadie vuelva
    a escribir un diálogo suelto, porque es de donde salían las diferencias.
    """
    sueltos = []
    for nombre, texto in _plantillas_aplicacion():
        for _id, _contenedor, _panel, _titulo in _modales(texto):
            sueltos.append(nombre)
    assert not sueltos, (
        f"hay modales escritos a mano en lugar de usar el macro: {sorted(set(sueltos))}"
    )


def test_el_componente_define_el_aspecto_de_todos_los_modales():
    """El fondo, el radio y el título se definen en un solo lugar.

    Antes convivían dos opacidades de fondo (40% y 60%), tres radios de panel
    (rounded-2xl, rounded-3xl, rounded-lg) y cuatro tamaños de título. Al estar
    todo en el macro, alcanza con verificar que el macro los fije.
    """
    with open(os.path.join(PLANTILLAS, "_ui.html"), encoding="utf-8") as fh:
        componente = fh.read()
    m = re.search(r"\{% macro modal\(.*?\{% endmacro %\}", componente, re.S)
    assert m, "no se encontró el macro modal en _ui.html"
    cuerpo = m.group(0)

    assert "bg-black/50" in cuerpo, "el macro no fija el fondo del diálogo"
    assert "rounded-lg" in cuerpo, "el macro no fija el radio del panel"
    assert "text-lg" in cuerpo, "el macro no fija el tamaño del título"
    # Los cuatro tamaños, para que no aparezcan anchos sueltos.
    for tamano in ("max-w-sm", "max-w-lg", "max-w-3xl", "max-w-5xl"):
        assert tamano in cuerpo, f"falta el tamaño {tamano} en el componente"


def test_ningun_modal_conserva_el_fondo_superpuesto():
    """Los modales migrados al componente no deben además pintar su propio velo."""
    for nombre, texto in _plantillas_aplicacion():
        for _id, contenedor, _panel, _titulo in _modales(texto):
            # Un div de fondo interno sumado al del contenedor duplica el velo.
            assert "bg-slate-900/40" not in texto, (
                f"{nombre}: queda un fondo de modal viejo (bg-slate-900/40)"
            )


# ── El componente ──────────────────────────────────────────────────────────
def _render_ui():
    from jinja2 import Environment, FileSystemLoader
    env = Environment(loader=FileSystemLoader(PLANTILLAS))
    t = env.from_string('''{% from "_ui.html" import modal, pie_modal, boton %}
{% call modal("prueba", "Título", "confirmar", "warning", "peligro", "Bajada") %}
<p id="prueba-cuerpo">Contenido</p>
{% call pie_modal() %}{{ boton("Aceptar") }}{% endcall %}
{% endcall %}''')
    return t.render()


def test_el_componente_expone_el_contrato_de_ids():
    """El JavaScript necesita ids estables: es el acuerdo entre vista y código."""
    html = _render_ui()
    for sufijo in ("", "-titulo", "-descripcion", "-icono", "-icono-glifo", "-cuerpo"):
        assert f'id="prueba{sufijo}"' in html, f"falta el id prueba{sufijo}"


def test_el_componente_cierra_con_escape_y_fondo():
    """El cierre lo maneja el controlador común, no cada plantilla."""
    html = _render_ui()
    assert 'data-modal-close="prueba"' in html
    assert 'aria-modal="true"' in html
    assert 'role="dialog"' in html


def test_el_componente_define_los_tres_tamanos():
    """Tres tamaños con nombre, en lugar de seis anchos sueltos."""
    from jinja2 import Environment, FileSystemLoader
    env = Environment(loader=FileSystemLoader(PLANTILLAS))
    for tamano, ancho in (("confirmar", "max-w-sm"), ("formulario", "max-w-lg"), ("amplio", "max-w-3xl")):
        t = env.from_string('{% from "_ui.html" import modal %}{% call modal("m", "T", "' + tamano + '") %}x{% endcall %}')
        assert ancho in t.render(), f"el tamaño {tamano} no usa {ancho}"


# ── Modo oscuro ────────────────────────────────────────────────────────────
def test_no_quedan_clases_de_modo_oscuro():
    """Se retiró por decisión del usuario; una clase suelta reintroduce el problema."""
    sobrantes = []
    for nombre, texto in _plantillas_aplicacion():
        if "dark:" in texto:
            sobrantes.append((nombre, texto.count("dark:")))
    assert not sobrantes, f"quedan clases dark: en {sobrantes}"


def test_el_css_no_genera_modo_oscuro_por_preferencia_del_sistema():
    """`darkMode: false` no desactiva el modo oscuro: Tailwind v3 lo trata como
    `media`, y la interfaz se ve a medio pintar en un equipo con el sistema en
    oscuro. Hay que compilar y verificar, no confiar en la opción."""
    ruta = os.path.join(RAIZ, "static", "css", "tailwind.css")
    css = open(ruta, encoding="utf-8").read()
    assert "prefers-color-scheme" not in css, (
        "el CSS generado aplica estilos oscuros según el sistema operativo"
    )


# ── Legibilidad ────────────────────────────────────────────────────────────
def test_no_hay_texto_por_debajo_del_piso_tipografico():
    """Había 780 usos por debajo de 12px, con text-[10px] como el más frecuente.
    La escala del sistema arranca en 2xs (12px)."""
    ofensores = []
    for nombre, texto in _plantillas_aplicacion():
        for tam in set(re.findall(r"text-\[(\d+)px\]", texto)):
            if int(tam) < 12:
                ofensores.append(f"{nombre}: text-[{tam}px]")
    assert not ofensores, f"texto por debajo de 12px: {ofensores[:8]}"


def test_la_escala_tipografica_tiene_piso_de_12px():
    import json
    import subprocess
    r = subprocess.run(
        ["node", "-e",
         "const r=require('tailwindcss/resolveConfig');"
         "const c=require('./tailwind.config.js');"
         "console.log(JSON.stringify(r(c).theme.fontSize))"],
        cwd=RAIZ, capture_output=True, text=True, timeout=60,
    )
    if r.returncode != 0:
        pytest.skip("no se pudo resolver la configuración de Tailwind")
    escala = json.loads(r.stdout)
    menores = {k: v[0] if isinstance(v, list) else v
               for k, v in escala.items()
               if _a_px(v) < 12}
    assert not menores, f"la escala tiene tamaños menores a 12px: {menores}"


def _a_px(valor):
    v = valor[0] if isinstance(valor, list) else valor
    if isinstance(v, str) and v.endswith("rem"):
        return float(v[:-3]) * 16
    if isinstance(v, str) and v.endswith("px"):
        return float(v[:-2])
    return 999


# ── Fase 4: barrido de colores ─────────────────────────────────────────────
# Familias de color de Tailwind que ya no deben usarse: sus tonos no estaban
# elegidos para pasar contraste y convivían 99 valores distintos.
_FAMILIAS_FUERA = (
    "slate|gray|zinc|neutral|stone|red|rose|pink|orange|amber|yellow|lime|green|"
    "emerald|teal|cyan|sky|blue|indigo|purple|violet|fuchsia"
)
_ROLES_COLOR = (
    "bg|text|border|ring|divide|from|to|via|fill|stroke|shadow|placeholder|"
    "accent|decoration|outline"
)


def test_las_plantillas_usan_los_colores_del_sistema():
    """Quedaban 2998 usos de colores sueltos en 99 valores distintos, elegidos a
    mano. Ahora todo sale de los tokens, que están verificados por contraste."""
    patron = re.compile(r"\b(?:" + _ROLES_COLOR + r")-(?:" + _FAMILIAS_FUERA + r")-[0-9]{2,3}")
    ofensores = []
    for nombre, texto in _plantillas_aplicacion():
        for m in set(patron.findall(texto)):
            ofensores.append(f"{nombre}: {m}")
    assert not ofensores, (
        f"{len(ofensores)} colores fuera del sistema, por ejemplo: {sorted(ofensores)[:6]}"
    )


def test_los_colores_semanticos_pasan_contraste():
    """El tono 500 de cada familia semántica es el que se usa para texto y cifras,
    así que tiene que pasar AA. Antes eran emerald-500 (2.54:1), amber-500
    (2.15:1) y slate-400 (2.56:1): los números más mirados, los menos legibles."""
    import json
    import subprocess

    r = subprocess.run(
        ["node", "-e",
         "const r=require('tailwindcss/resolveConfig');"
         "const c=require('./tailwind.config.js');"
         "console.log(JSON.stringify(r(c).theme.colors))"],
        cwd=RAIZ, capture_output=True, text=True, timeout=60,
    )
    if r.returncode != 0:
        pytest.skip("no se pudo resolver la configuración de Tailwind")
    colores = json.loads(r.stdout)

    def luminancia(hexa):
        hexa = hexa.lstrip("#")
        canales = [int(hexa[i:i + 2], 16) / 255 for i in (0, 2, 4)]
        f = lambda v: v / 12.92 if v <= 0.03928 else ((v + 0.055) / 1.055) ** 2.4
        rojo, verde, azul = (f(c) for c in canales)
        return 0.2126 * rojo + 0.7152 * verde + 0.0722 * azul

    def contraste(a, b="#ffffff"):
        l1, l2 = sorted([luminancia(a), luminancia(b)], reverse=True)
        return (l1 + 0.05) / (l2 + 0.05)

    fallan = []
    for familia in ("exito", "alerta", "peligro", "info"):
        tono = colores.get(familia, {}).get("500")
        if not tono:
            fallan.append(f"{familia}-500 no existe")
            continue
        r_contraste = contraste(tono)
        if r_contraste < 4.5:
            fallan.append(f"{familia}-500 ({tono}) da {r_contraste:.2f}:1")
    # Y los grises de texto.
    for nombre in ("fuerte", "base", "suave", "tenue"):
        tono = colores.get("texto", {}).get(nombre)
        if not tono:
            fallan.append(f"texto-{nombre} no existe")
            continue
        r_contraste = contraste(tono)
        if r_contraste < 4.5:
            fallan.append(f"texto-{nombre} ({tono}) da {r_contraste:.2f}:1")

    assert not fallan, f"colores que no pasan AA sobre blanco: {fallan}"


# ── Condicionales de Jinja ─────────────────────────────────────────────────
def test_los_condicionales_de_jinja_estan_bien_escritos():
    """Había 80 condicionales escritos sin la llave de apertura (`% if x %` en
    lugar de `{% if x %}`), dentro de atributos class.

    Jinja no los reconoce, así que el texto se colaba literal en la clase:
    `<a class="... % if active_page dashboard % sidebar-active % endif %">`.
    Efecto: el menú marcaba TODOS los enlaces como activos, y los badges de
    estado y los puntos de estado nunca recibían su color. Es la causa de que la
    interfaz se viera monocromática: los colores condicionales estaban muertos.
    """
    patron = re.compile(r"(?<!\{)%\s*(?:if|elif|else|endif)\b")
    ofensores = []
    for nombre, texto in _plantillas_aplicacion():
        for m in patron.finditer(texto):
            linea = texto[:m.start()].count("\n") + 1
            ofensores.append(f"{nombre}:{linea}")
    assert not ofensores, (
        f"{len(ofensores)} condicionales sin la llave de apertura: {ofensores[:6]}"
    )


def test_las_expresiones_de_los_condicionales_comparan():
    """Además de la llave faltaba la comparación: `if active_page dashboard` en
    lugar de `if active_page == 'dashboard'`, que no es una expresión válida."""
    patron = re.compile(r"\{%\s*(?:if|elif)\s+([^%]*?)\s*%\}")
    ofensores = []
    for nombre, texto in _plantillas_aplicacion():
        for m in patron.finditer(texto):
            expr = m.group(1).strip()
            if not expr:
                continue
            tiene_operador = re.search(
                r"==|!=|>=|<=|>|<|\band\b|\bor\b|\bnot\b|\bin\b|\bis\b|\(|\)|\|", expr)
            # `variable valor` sin operador es el patrón que estaba mal.
            if not tiene_operador and re.match(
                    r"^[A-Za-z_][\w.\[\]]*\s+[A-Za-z_]", expr):
                ofensores.append(f"{nombre}: {expr}")
    assert not ofensores, f"condicionales sin comparación: {ofensores[:6]}"


def test_el_enlace_activo_del_menu_se_marca_solo_en_uno():
    """El menú debe marcar un solo enlace como activo, no todos."""
    from jinja2 import Environment, FileSystemLoader

    env = Environment(loader=FileSystemLoader(PLANTILLAS))
    # Starlette inyecta url_for en el contexto; con un entorno Jinja pelado hay
    # que registrarlo.
    env.globals["url_for"] = lambda name, **params: "/static/" + str(params.get("path", "")).lstrip("/")
    # `static_url` lo registra templating.py sobre el entorno compartido; acá se
    # replica para poder renderizar el layout en un entorno pelado.
    env.globals["static_url"] = lambda path: "/static/" + str(path).lstrip("/")
    contexto = {
        "active_page": "clientes",
        "today": None, "clientes": {"total": 0, "activos": 0, "prospectos": 0},
        "visitas": {"total": 0, "borrador": 0, "finalizado": 0, "total_asignadas_at": 0,
                    "avance_pct": 0, "tendencia_meses": [], "tendencia_datos": [],
                    "objetivos": [], "objetivos_labels": [], "objetivos_data": [], "por_at": []},
        "maquinas": {"total": 0, "survey_progress": 0, "relevamiento_completado": 0,
                     "por_tipo": [], "por_estado": [], "por_relevamiento": []},
        "minutas": {"total": 0, "borrador": 0, "finalizado": 0, "por_tipo": []},
        "advisors": [], "customer_list": [], "available_years": [], "months": [], "filters": {},
    }
    html = env.get_template("layout.html").render(request=_RequestUI(), **contexto)
    assert html.count('class="') and "sidebar-active" in html
    # Sólo el enlace de clientes queda activo.
    activos = [m.group(1) for m in re.finditer(r'<a class="([^"]*sidebar-active[^"]*)"', html)]
    assert len(activos) == 1, f"hay {len(activos)} enlaces marcados como activos"
    assert "% if" not in html, "quedó texto de Jinja dentro del HTML"


# ── Fase 4: lenguaje visual ────────────────────────────────────────────────
def test_no_queda_texto_en_mayusculas_con_tracking():
    """El par MAYÚSCULAS + letras separadas es el tell de tablero anticuado.

    Había 860 casos en 36 plantillas. Se pasó todo a caja de oración. Esta prueba
    evita que vuelvan: es el cambio de mayor impacto visual y se pierde solo, con
    una etiqueta nueva que alguien escriba a la antigua.
    """
    patron = re.compile(r'class="[^"]*\buppercase\b[^"]*"')
    ofensores = []
    for nombre, texto in _plantillas_aplicacion():
        for m in patron.finditer(texto):
            if re.search(r'tracking-(?:wide|wider|widest)', m.group(0)):
                linea = texto[:m.start()].count("\n") + 1
                ofensores.append(f"{nombre}:{linea}")
    assert not ofensores, (
        f"{len(ofensores)} etiquetas en mayúsculas con tracking: {ofensores[:6]}"
    )


def test_los_indicadores_usan_el_componente_compartido():
    """Cada pantalla tenía sus propias tarjetas de KPI, con otro aspecto.

    Se unificaron 57 llamadas al macro `indicador`. Esta prueba detecta si vuelve
    a aparecer una tarjeta de KPI escrita a mano, que es como se desincronizan.
    """
    patron = re.compile(
        r'<p class="[^"]*\btext-(?:2xs|xs)\b[^"]*"[^>]*>\s*[^<]{2,34}?\s*</p>\s*'
        r'<(?:h3|h4|p) class="[^"]*\btext-(?:lg|xl|2xl|3xl)\b', re.S)
    ofensores = []
    for nombre, texto in _plantillas_aplicacion():
        # Los informes imprimibles tienen su propio encabezado, no son KPIs.
        if "reporte" in nombre:
            continue
        for m in patron.finditer(texto):
            linea = texto[:m.start()].count("\n") + 1
            ofensores.append(f"{nombre}:{linea}")
    assert not ofensores, (
        f"{len(ofensores)} KPIs escritos a mano en lugar de usar indicador(): {ofensores[:6]}"
    )


def test_las_tablas_ocupan_el_ancho_disponible():
    """Las tablas de listado deben declarar `w-full` en el propio <table>.

    Nota sobre un error mío: al arreglar el hueco en blanco de la tabla de
    visitas atribuí el problema a un `w-full` puesto en una columna. Una
    comprobación A/B en el navegador lo desmintió: con y sin ese `w-full` el
    hueco mide 0px; lo único que cambia es cuánto espacio extra recibe la columna
    del cliente (278px contra 240px), que es justamente lo que se busca en la
    columna de texto variable. Así que `w-full` en una columna es válido y esta
    prueba ya no lo prohíbe. Lo que sí se verifica es que la tabla lo declare.
    """
    # Las tablas que traen su propia clase (por ejemplo `ska-table`, del sistema
    # de estilos interno de una plantilla) definen sus anchos en su hoja de
    # estilos y no necesitan `w-full`. La regla aplica a las que se maquetan con
    # utilidades de Tailwind.
    PROPIAS = re.compile(r'<table[^>]*class="(ska-[^"]*|[a-z]+-table[^"]*)"')
    ofensores = []
    for nombre, texto in _plantillas_aplicacion():
        for m in re.finditer(r'<table[^>]*>', texto):
            etiqueta = m.group(0)
            if PROPIAS.match(etiqueta):
                continue
            if "w-full" not in etiqueta:
                linea = texto[:m.start()].count("\n") + 1
                ofensores.append(f"{nombre}:{linea}")
    assert not ofensores, f"tablas sin w-full: {ofensores[:6]}"


def test_las_fechas_se_muestran_en_formato_local():
    """Mostraba `2026-09-24` en la tabla y `24/09/2026` en el resto.

    El filtro no parseaba texto: `strftime` no existe en un `str`, así que
    devolvía el valor tal cual.
    """
    from templating import _fmt_date

    assert _fmt_date("2026-09-24") == "24/09/2026"
    assert _fmt_date("2026-09-24T14:30:00") == "24/09/2026"
    assert _fmt_date("24/09/2026") == "24/09/2026"
    assert _fmt_date(None) == ""
    assert _fmt_date("") == ""
    import datetime as _dt
    assert _fmt_date(_dt.date(2026, 9, 24)) == "24/09/2026"


def test_los_estaticos_llevan_la_huella_de_cache():
    """nginx sirve /static con `immutable` y 30 días.

    Sin huella en la URL, el navegador no vuelve a pedir el archivo y ningún
    cambio de CSS llega al usuario: pasó durante todo el rediseño.
    """
    from templating import ASSET_VERSION, static_url

    assert ASSET_VERSION and ASSET_VERSION != "0"
    assert static_url("css/tailwind.css").endswith(f"?v={ASSET_VERSION}")
    assert "/static/css/tailwind.css?v=" in static_url("css/tailwind.css")

    # Y las plantillas no deben volver a pedir estáticos sin la huella.
    ofensores = []
    for nombre, texto in _plantillas_aplicacion():
        for m in re.finditer(r"url_for\('static'", texto):
            linea = texto[:m.start()].count("\n") + 1
            ofensores.append(f"{nombre}:{linea}")
    assert not ofensores, f"estáticos sin huella de caché: {ofensores[:6]}"


def test_las_plantillas_cierran_todos_los_divs():
    """Un `<div>` sin cerrar hizo que la tabla quedara dentro de la barra de
    encabezado, que es `flex ... justify-between`.

    Como el navegador cierra solo los divs que faltan, el HTML "funcionaba" y el
    error no se veía en el código: se veía en pantalla. La tabla, al ser un flex
    item, se encogía a su contenido y con `justify-between` quedaba empujada a la
    derecha, con un hueco en blanco de varios cientos de píxeles que además
    cambiaba según el ancho de la ventana. Por eso el usuario lo describía como
    "se ajusta y al segundo vuelve a esa posición".
    """
    ofensores = []
    for nombre, texto in _plantillas_aplicacion():
        limpio = re.sub(r'\{#.*?#\}', '', texto, flags=re.S)
        limpio = re.sub(r'<script.*?</script>', '', limpio, flags=re.S)
        saldo = len(re.findall(r'<div\b', limpio)) - len(re.findall(r'</div>', limpio))
        if saldo:
            ofensores.append(f"{nombre}: {saldo:+d}")
    assert not ofensores, f"plantillas con divs desbalanceados: {ofensores}"


def test_los_modales_usan_los_tres_tamanos_del_componente():
    """El componente define tres tamaños: confirmar, formulario y amplio.

    Los modales escritos a mano usaban cinco anchos distintos (max-w-xs, md, lg,
    2xl, 6xl), así que el mismo tipo de diálogo medía distinto según la pantalla:
    en seguimiento, el modal de crear medía max-w-2xl y el de editar lo mismo
    medía max-w-lg. Ahora todos caen en uno de los tres tamaños.
    """
    # Los cuatro tamaños del componente, más los que aún tienen los modales
    # escritos a mano mientras se migran.
    PERMITIDOS = {"max-w-sm", "max-w-lg", "max-w-3xl", "max-w-5xl", "max-w-4xl"}
    ofensores = []
    for nombre, texto in _plantillas_aplicacion():
        for m in re.finditer(r'<div[^>]*role="dialog"[^>]*>', texto):
            frag = texto[m.start():m.start() + 1400]
            ancho = re.search(r'max-w-[a-z0-9\[\]]+', frag)
            if ancho and ancho.group(0) not in PERMITIDOS:
                linea = texto[:m.start()].count("\n") + 1
                ofensores.append(f"{nombre}:{linea} usa {ancho.group(0)}")
    assert not ofensores, f"modales con ancho fuera del sistema: {ofensores}"


def test_los_modales_se_abren_centrados():
    """Abrir un modal quitando sólo `hidden` lo deja pegado arriba a la izquierda.

    El contenedor del diálogo es

        fixed inset-0 hidden items-center justify-center ...

    `items-center` y `justify-center` sólo funcionan con `display: flex`. El
    controlador compartido (`abrirModal`) quita `hidden` **y agrega `flex`**. Cinco
    modales de cuatro plantillas tenían su propia función que sólo quitaba
    `hidden`, así que el diálogo aparecía en la esquina y el fondo oscuro cubría un
    cuarto de pantalla.

    Esta prueba falla si alguna plantilla abre un modal sin centrarlo.
    """
    ofensores = []
    for nombre, texto in _plantillas_aplicacion():
        if 'role="dialog"' not in texto:
            continue
        # Sólo los identificadores que de verdad declaran un diálogo. Filtrar por
        # el nombre no alcanza: `modal-info` es un bloque de información *dentro*
        # del modal, y alternarlo no tiene por qué centrar nada.
        dialogos = set()
        for m in re.finditer(r'<div[^>]*>', texto):
            etiqueta = m.group(0)
            if 'role="dialog"' not in etiqueta:
                continue
            idd = re.search(r'id="([^"]+)"', etiqueta)
            if idd:
                dialogos.add(idd.group(1))
        variables = {}
        for m in re.finditer(
                r"(\w+)\s*=\s*document\.getElementById\('([^']+)'\)", texto):
            if m.group(2) in dialogos:
                variables[m.group(1)] = m.group(2)
        for var, idd in variables.items():
            # ¿Se abre quitando `hidden` a esa variable?
            abre = re.search(re.escape(var) + r"\.classList\.remove\('hidden'\)", texto)
            if not abre:
                continue
            # Formas válidas: pasa por el controlador, o agrega `flex` él mismo.
            usa_controlador = f"abrirModal('{idd}')" in texto
            agrega_flex = re.search(
                re.escape(var) + r"\.classList\.add\('flex'\)", texto)
            if not usa_controlador and not agrega_flex:
                linea = texto[:abre.start()].count("\n") + 1
                ofensores.append(f"{nombre}:{linea} abre {idd} sin centrar")
    assert not ofensores, f"modales que se abren descuadrados: {ofensores}"


def test_no_hay_tracking_arbitrario_ni_escala_al_pasar_el_mouse():
    """Dos restos del lenguaje anterior.

    * `tracking-[0.2em]` es el mismo patrón de letras separadas que se quitó con
      `tracking-widest`, pero con un valor a medida que el barrido anterior no
      atrapaba. Quedaban 22 casos, casi todos en botones.
    * `hover:scale-105` / `hover:scale-[1.02]` hace que el botón "salte" al pasar
      el mouse. El sistema usa transiciones de color, no de tamaño.
    """
    patron = re.compile(r'tracking-\[[^\]]*\]|hover:scale-')
    ofensores = []
    for nombre, texto in _plantillas_aplicacion():
        # Los informes imprimibles conservan su diseño propio.
        if "reporte" in nombre or nombre == "relevamiento_ver.html":
            continue
        for m in patron.finditer(texto):
            linea = texto[:m.start()].count("\n") + 1
            ofensores.append(f"{nombre}:{linea} {m.group(0)}")
    assert not ofensores, f"restos del lenguaje anterior: {ofensores[:6]}"


def test_los_formularios_abren_y_cierran():
    """Un `<form>` sin cerrar hace que el navegador descarte el siguiente.

    Al migrar los modales de seguimiento se perdió el `</form>` de cada uno. HTML
    no permite formularios anidados, así que el navegador anidó el segundo dentro
    del primero y lo **descartó del DOM**: `getElementById('editTrackingForm')`
    devolvía `null` y el modal de edición no abría, aunque el id estuviera en el
    HTML servido. El HTML se veía bien; el que fallaba era el DOM.
    """
    ofensores = []
    for nombre, texto in _plantillas_aplicacion():
        limpio = re.sub(r'<script\b.*?</script>', '', texto, flags=re.S)
        abre = len(re.findall(r'<form\b', limpio))
        cierra = len(re.findall(r'</form>', limpio))
        if abre != cierra:
            ofensores.append(f"{nombre}: {abre} abiertos, {cierra} cerrados")
    assert not ofensores, f"formularios desbalanceados: {ofensores}"


def test_cada_macro_usado_esta_importado():
    """Usar un macro sin importarlo compila, pero falla al renderizar.

    Pasó con `pie_modal` en clientes.html: la plantilla compilaba sin error y el
    fallo aparecía recién al abrir la página, con HTTP 500 y

        jinja2.exceptions.UndefinedError: 'pie_modal' is undefined

    `get_template()` sólo compila: no evalúa el cuerpo de los bloques, así que no
    lo detecta. Esta prueba compara lo que cada plantilla usa contra lo que
    importa.
    """
    MACROS = ("indicador", "estado", "boton", "modal", "pie_modal",
              "barra_filtros", "vacio")
    ofensores = []
    for nombre, texto in _plantillas_aplicacion():
        usados = set()
        for macro in MACROS:
            if re.search(r"\b" + macro + r"\s*\(", texto) or ("call " + macro) in texto:
                usados.add(macro)
        if not usados:
            continue
        m = re.search(r'\{% from "_ui.html" import ([^%]*?) %\}', texto)
        importados = set()
        if m:
            importados = {x.strip() for x in m.group(1).split(",") if x.strip()}
        faltan = usados - importados
        if faltan:
            ofensores.append(f"{nombre}: usa {sorted(faltan)} sin importar")
    assert not ofensores, f"macros sin importar: {ofensores}"


def test_no_vuelven_los_patrones_del_lenguaje_anterior():
    """Restos del sistema de estilos previo, que se barrieron de una pasada.

        bg-white        173 casos  -> salta el sistema de tokens
        font-black      510 casos  -> peso 900 en etiquetas y botones
        rounded-2xl      69 casos  -> radio fuera de la escala
        shadow-*        170 casos  -> el sistema separa con bordes, no con sombras

    Las plantillas de impresión quedan afuera: conservan su diseño propio.
    """
    IMPRESION = {"nuevo_relevamiento2.html", "relevamiento_ver.html",
                 "infraestructura_reporte.html", "relevamiento_reporte.html",
                 "cliente_reporte.html"}
    patrones = {
        "bg-white": re.compile(r"\bbg-white\b"),
        "font-black": re.compile(r"\bfont-black\b"),
        "rounded-2xl": re.compile(r"\brounded-(?:2xl|3xl)\b"),
        "shadow suelto": re.compile(r"\bshadow-(?:sm|md|lg|xl|2xl)\b"),
    }
    ofensores = []
    for nombre, texto in _plantillas_aplicacion():
        if nombre in IMPRESION:
            continue
        for etiqueta, patron in patrones.items():
            for m in patron.finditer(texto):
                linea = texto[:m.start()].count("\n") + 1
                ofensores.append(f"{nombre}:{linea} {etiqueta}")
    assert not ofensores, f"volvieron patrones del lenguaje anterior: {ofensores[:6]}"


def test_todos_los_iconos_estan_en_el_subset():
    """La fuente de iconos es un subset, no la completa.

    Material Symbols Rounded completo pesa 5,3 MB para los 107 iconos que usa la
    aplicación: el 99% del peso de la primera carga. Se reemplazó por un subset de
    160 KB (97% menos) generado con `deploy/subset-iconos.sh`, que deja la lista en
    `static/fonts/material-symbols.icons.txt`.

    El riesgo de un subset es agregar un icono nuevo y que no se vea. Esta prueba
    lo detecta: además encontró dos nombres inválidos que ya estaban en el código
    (`quality` y `groups_off`, que no existen en Material Symbols y se veían como
    texto en lugar de como icono).
    """
    manifiesto = os.path.join(PLANTILLAS, os.pardir, "static", "fonts",
                              "material-symbols.icons.txt")
    with open(manifiesto, encoding="utf-8") as fh:
        disponibles = {x.strip() for x in fh.read().split(",") if x.strip()}
    assert disponibles, "el manifiesto de iconos está vacío"

    usados = set()
    for nombre, texto in _plantillas_aplicacion():
        for m in re.finditer(
                r'class="[^"]*material-symbols-rounded[^"]*"[^>]*>\s*([a-z][a-z_0-9]*)\s*<',
                texto):
            usados.add(m.group(1))
        for m in re.finditer(
                r'indicador\(\s*"[^"]*"\s*,\s*[^,]+,\s*"[^"]*"\s*,\s*"([a-z_0-9]+)"', texto):
            usados.add(m.group(1))

    faltan = sorted(usados - disponibles)
    assert not faltan, (
        f"iconos usados que no están en el subset: {faltan}. "
        f"Corré `bash deploy/subset-iconos.sh` para regenerarlo."
    )


def test_no_quedan_librerias_sin_usar():
    """`tabulator.min.js` (390 KB) no lo referenciaba ninguna plantilla."""
    js = os.path.join(PLANTILLAS, os.pardir, "static", "js")
    plantillas_y_js = ""
    for nombre, texto in _plantillas_aplicacion():
        plantillas_y_js += texto
    for ruta in glob.glob(os.path.join(js, "*.js")):
        # app.js es el controlador compartido; no se referencia a sí mismo.
        if os.path.basename(ruta) != "app.js":
            with open(ruta, encoding="utf-8", errors="replace") as fh:
                plantillas_y_js += fh.read()

    huerfanas = []
    for ruta in glob.glob(os.path.join(js, "*.js")):
        base = os.path.basename(ruta)
        if base in plantillas_y_js and base != "app.js":
            continue
        if base != "app.js" and base not in plantillas_y_js:
            huerfanas.append(base)
    assert not huerfanas, f"librerías que nadie referencia: {huerfanas}"


def test_los_macros_no_dependen_del_contexto():
    """Un macro de Jinja no ve el contexto del template.

    `boton_exportar` leía `request.url.query` para reusar los filtros. Los macros
    sólo reciben sus argumentos, así que `request` no existe dentro y la página
    fallaba con:

        jinja2.exceptions.UndefinedError: 'request' is undefined

    La plantilla compilaba bien: el error aparecía al renderizar. Por eso no
    alcanza con `get_template()`. Esta prueba revisa que ningún macro de _ui.html
    use variables de contexto.
    """
    with open(os.path.join(PLANTILLAS, "_ui.html"), encoding="utf-8") as fh:
        componente = fh.read()

    prohibidas = ("request", "session", "user", "csrf_token")
    ofensores = []
    for m in re.finditer(r"\{% macro (\w+)\((.*?)\) %\}(.*?)\{% endmacro %\}",
                         componente, re.S):
        nombre, params, cuerpo = m.group(1), m.group(2), m.group(3)
        # Sólo se analiza lo que está fuera de comentarios Jinja.
        cuerpo_limpio = re.sub(r"\{#.*?#\}", "", cuerpo, flags=re.S)
        variables = {p.split("=")[0].strip() for p in params.split(",") if p.strip()}
        for prohibida in prohibidas:
            # `request.url.query` o `request.state...` dentro del macro.
            if re.search(r"\b" + prohibida + r"\b", cuerpo_limpio) and prohibida not in variables:
                ofensores.append(f"{nombre} usa '{prohibida}'")
    assert not ofensores, (
        f"macros que dependen del contexto del template: {ofensores}. "
        f"Pasá el valor como argumento."
    )


def test_los_modulos_no_usan_nombres_sin_definir():
    """Nombres usados que no están importados ni definidos.

    Al extraer consultas a funciones compartidas quedaron atrás los imports
    locales que vivían dentro de esas funciones. El código se veía bien y fallaba
    recién en ejecución:

        NameError: name 'or_' is not defined
        NameError: name 'normalize_tracking_status' is not defined

    Este chequeo recorre el árbol sintáctico y compara los nombres que se leen
    contra los que están definidos, importados o son del lenguaje.
    """
    import ast
    import builtins

    RAIZ = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    ofensores = []
    for patron in ("services/*.py", "routers/*.py"):
        for ruta in glob.glob(os.path.join(RAIZ, patron)):
            with open(ruta, encoding="utf-8") as fh:
                arbol = ast.parse(fh.read())
            definidos = set(dir(builtins))
            for nodo in ast.walk(arbol):
                if isinstance(nodo, (ast.Import, ast.ImportFrom)):
                    for a in nodo.names:
                        definidos.add((a.asname or a.name).split(".")[0])
                elif isinstance(nodo, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                    definidos.add(nodo.name)
                elif isinstance(nodo, ast.arg):
                    definidos.add(nodo.arg)
                elif isinstance(nodo, ast.Name) and isinstance(nodo.ctx, ast.Store):
                    definidos.add(nodo.id)
                elif isinstance(nodo, ast.ExceptHandler) and nodo.name:
                    definidos.add(nodo.name)
            usados = {n.id for n in ast.walk(arbol)
                      if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Load)}
            faltan = sorted(usados - definidos)
            if faltan:
                ofensores.append(f"{os.path.basename(ruta)}: {faltan[:6]}")
    assert not ofensores, f"nombres sin definir: {ofensores}"
