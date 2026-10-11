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


def test_todos_los_modales_comparten_el_fondo():
    """Había dos opacidades mezcladas (40% y 60%) más un tercer valor suelto."""
    usados = set()
    for nombre, texto in _plantillas_aplicacion():
        for _id, contenedor, _panel, _titulo in _modales(texto):
            usados.add(next((t for t in re.findall(r"bg-(?:black|slate)\S*", contenedor)), "-"))
    assert usados == {"bg-black/50"}, f"el fondo del modal varía: {sorted(usados)}"


def test_todos_los_modales_comparten_radio_de_panel():
    """Convivían rounded-2xl, rounded-3xl y rounded-lg en los mismos elementos."""
    usados = set()
    for nombre, texto in _plantillas_aplicacion():
        for _id, _cont, panel, _titulo in _modales(texto):
            if panel:
                usados.add(next((t for t in re.findall(r"rounded-\S+", panel)), "-"))
    assert usados <= {"rounded-lg"}, f"el radio del panel varía: {sorted(usados)}"


def test_todos_los_titulos_de_modal_miden_igual():
    """Había text-sm, text-lg, text-xl y text-2xl en 21 modales."""
    usados = set()
    for nombre, texto in _plantillas_aplicacion():
        for _id, _cont, _panel, titulo in _modales(texto):
            if titulo:
                usados.add(next((t for t in re.findall(r"text-(?:xs|sm|base|lg|xl|2xl)", titulo)), "-"))
    assert usados <= {"text-lg"}, f"el tamaño del título varía: {sorted(usados)}"


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
