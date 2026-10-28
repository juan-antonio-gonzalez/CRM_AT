"""Pruebas del widget flotante de Caty.

Dos cosas se verifican acá que no se ven mirando la pantalla: que el panel no se
anuncie como diálogo modal —porque no lo es, no bloquea nada, y decirlo sería
mentirle al lector de pantalla— y que el JavaScript no construya HTML con
`innerHTML`. El texto viene de un modelo que leyó lo que escribió el usuario:
tratarlo como HTML abriría la puerta que todo el backend se esfuerza en cerrar.
"""

import os
import re
import subprocess

import pytest

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PLANTILLAS = os.path.join(RAIZ, "templates")
JS = os.path.join(RAIZ, "static", "js", "agente.js")


class _Request:
    """Request mínimo para renderizar el parcial sin levantar la aplicación."""

    class state:
        csrf_token = "token-de-prueba"
        script_nonce = "nonce-de-prueba"
        user = {"sub": "7", "username": "probador", "role": "admin"}


def _fuente(nombre):
    return open(os.path.join(PLANTILLAS, nombre), encoding="utf-8").read()


@pytest.fixture
def js():
    return open(JS, encoding="utf-8").read()


@pytest.fixture
def render():
    """Renderiza `_agente.html`. El contexto pisa los globales del entorno."""
    from templating import templates

    def _render(habilitado=True, request=None, nombre="Caty"):
        return templates.env.get_template("_agente.html").render(
            request=request or _Request(),
            agente_habilitado=lambda: habilitado,
            agente_nombre=nombre,
        )

    return _render


# --------------------------------------------------------------------------- #
# Aparece o no aparece
# --------------------------------------------------------------------------- #


def test_el_widget_se_renderiza_cuando_esta_habilitada(render):
    html = render()
    assert 'id="caty"' in html
    assert 'id="caty-panel"' in html
    assert 'id="caty-boton"' in html
    assert 'id="caty-entrada"' in html
    assert "Caty" in html


def test_el_widget_no_deja_rastro_cuando_esta_apagada(render):
    """Sin clave de DeepSeek no se muestra ni el botón."""
    html = render(habilitado=False)
    assert 'id="caty"' not in html
    assert "caty-panel" not in html
    assert "material-symbols" not in html


def test_el_widget_no_aparece_sin_los_globales_del_entorno():
    """`test_ui.py` renderiza el layout con un Environment propio.

    Sin la guarda `is defined`, ese render explota con UndefinedError y se lleva
    puestas las pruebas del sistema de diseño.
    """
    from jinja2 import Environment, FileSystemLoader

    entorno = Environment(loader=FileSystemLoader(PLANTILLAS))
    html = entorno.get_template("_agente.html").render(request=_Request())
    assert "caty" not in html


def test_el_usuario_va_en_un_atributo_para_separar_los_hilos(render):
    assert 'data-usuario="7"' in render()


def test_sin_sesion_el_widget_sigue_renderizando(render):
    class _Anonimo:
        class state:
            csrf_token = "t"
            script_nonce = "n"
            user = None

    assert 'data-usuario="anonimo"' in render(request=_Anonimo())


# --------------------------------------------------------------------------- #
# Semántica: es un panel, no un modal
# --------------------------------------------------------------------------- #


def test_el_panel_no_se_anuncia_como_dialogo_modal(render):
    """No bloquea la pantalla, así que no es un `dialog` ni es `aria-modal`.

    Además, `test_ui.py` trata cualquier `role="dialog"` como un modal escrito a
    mano en lugar de usar el macro de `_ui.html`.
    """
    html = render()
    assert 'role="dialog"' not in html
    assert "aria-modal" not in html
    assert 'role="complementary"' in html


def test_los_mensajes_se_anuncian_sin_interrumpir(render):
    assert 'aria-live="polite"' in render()
    assert 'role="log"' in render()


def test_el_panel_arranca_oculto(render):
    html = render()
    panel = re.search(r'<div id="caty-panel"[^>]*class="([^"]*)"', html)
    assert panel, "no se encontró el panel"
    assert "hidden" in panel.group(1).split()


def test_el_boton_esta_conectado_al_panel(render):
    html = render()
    assert 'aria-controls="caty-panel"' in html
    assert 'aria-expanded="false"' in html


def test_cada_boton_tiene_nombre_accesible(render):
    """Un botón con texto visible ya tiene nombre; uno sólo de icono necesita ayuda."""
    html = render()
    for fragmento in re.findall(r"<button\b.*?</button>", html, re.S):
        declarado = "sr-only" in fragmento or "aria-label" in fragmento
        visible = re.sub(r"<[^>]+>", " ", fragmento)
        assert declarado or visible.strip(), fragmento[:120]


# --------------------------------------------------------------------------- #
# Integración con el layout
# --------------------------------------------------------------------------- #


def test_el_layout_incluye_el_widget():
    assert '{% include "_agente.html" %}' in _fuente("layout.html")


def test_el_layout_carga_el_javascript_con_el_nonce():
    """La CSP exige nonce: un `<script>` sin él no se ejecuta."""
    layout = _fuente("layout.html")
    etiqueta = re.search(r"<script[^>]*agente\.js[^>]*>", layout)
    assert etiqueta, "no se encontró la etiqueta de agente.js"
    assert "nonce=" in etiqueta.group(0)


def test_el_login_no_muestra_el_widget():
    """La pantalla de login no extiende del layout, así que no lo incluye."""
    assert "extends" not in _fuente("login.html")
    assert "caty" not in _fuente("login.html")


def test_el_widget_no_sale_impreso():
    """El layout tiene estilos de impresión; el panel no debe aparecer ahí."""
    assert "print:hidden" in _fuente("_agente.html")


# --------------------------------------------------------------------------- #
# Limpiar la conversación
# --------------------------------------------------------------------------- #


def test_el_boton_de_limpiar_esta_en_el_encabezado(render):
    html = render()
    assert 'id="caty-limpiar"' in html
    assert "delete_sweep" in html
    assert "Limpiar la conversación" in html


def test_limpiar_arranca_deshabilitado(render):
    """Con la conversación vacía no hay nada que limpiar, y el botón lo dice."""
    etiqueta = re.search(r"<button[^>]*id=\"caty-limpiar\"[^>]*>", render())
    assert etiqueta, "no se encontró el botón"
    assert "disabled" in etiqueta.group(0)


def test_limpiar_es_un_boton_de_verdad(render):
    """Un `type` sin declarar lo convierte en submit y recarga la página."""
    etiqueta = re.search(r"<button[^>]*id=\"caty-limpiar\"[^>]*>", render())
    assert 'type="button"' in etiqueta.group(0)


def test_el_javascript_limpia_el_hilo_y_el_guardado(js):
    assert "function limpiarConversacion" in js
    assert "hilo = []" in js
    # Si no se borra lo guardado, al recargar vuelve la conversación limpiada.
    cuerpo = js.split("function limpiarConversacion")[1].split("function ")[0]
    assert "guardarHilo()" in cuerpo
    assert "mensajes.textContent = \"\"" in cuerpo


def test_limpiar_se_deshabilita_mientras_caty_responde(js):
    """Vaciar a mitad de una respuesta dejaría un hilo mezclado."""
    assert "function actualizarLimpiar" in js
    cuerpo = js.split("function actualizarLimpiar")[1].split("function ")[0]
    assert "ocupada" in cuerpo
    assert "hilo.length === 0" in cuerpo


def test_limpiar_no_borra_nada_del_servidor(js):
    """Limpiar es local: no puede llamar al backend ni tocar datos."""
    cuerpo = js.split("function limpiarConversacion")[1].split("function ")[0]
    assert "fetch(" not in cuerpo
    assert "sessionStorage" not in cuerpo or "guardarHilo" in cuerpo


def test_el_widget_aparece_en_el_layout_real(monkeypatch):
    """El layout de verdad, con los globales del proyecto, incluye el widget.

    Es la prueba que faltaba: verifica que `agente_habilitado()` resuelva en el
    entorno real de Jinja y que el id del usuario llegue al atributo.
    """
    from config import settings
    from templating import templates

    monkeypatch.setattr(settings, "deepseek_api_key", "clave-de-prueba")
    html = templates.env.get_template("layout.html").render(
        request=_Request(), active_page="dashboard")

    assert 'id="caty"' in html
    assert 'data-usuario="7"' in html
    assert "js/agente.js" in html


def test_sin_clave_el_layout_real_no_trae_el_widget(monkeypatch):
    from config import settings
    from templating import templates

    monkeypatch.setattr(settings, "deepseek_api_key", "")
    html = templates.env.get_template("layout.html").render(
        request=_Request(), active_page="dashboard")

    assert 'id="caty"' not in html
    assert "js/agente.js" in html  # el script se carga igual; no hace nada sin widget


# --------------------------------------------------------------------------- #
# El JavaScript
# --------------------------------------------------------------------------- #


def test_el_javascript_no_tiene_errores_de_sintaxis():
    """Un typo acá rompe el widget en silencio: nada avisa hasta que se usa."""
    resultado = subprocess.run(["node", "--check", JS],
                               capture_output=True, text=True, timeout=60)
    assert resultado.returncode == 0, resultado.stderr


def test_el_javascript_nunca_construye_html(js):
    """El texto del modelo se inserta con `textContent`, jamás como HTML.

    Se buscan los usos reales y no la palabra suelta: los comentarios del archivo
    nombran `innerHTML` justamente para explicar que no se usa.
    """
    for prohibido in (r"\.innerHTML\s*=", r"\.outerHTML\s*=",
                      r"insertAdjacentHTML\s*\(", r"document\.write\s*\("):
        assert not re.search(prohibido, js), f"apareció {prohibido}"
    assert js.count("textContent") > 5


def test_el_javascript_solo_acepta_enlaces_internos(js):
    """Un enlace que no sea de la propia aplicación se muestra como texto."""
    assert 'href.charAt(0) !== "/"' in js
    assert 'href.slice(0, 2) === "//"' in js


def test_el_javascript_toma_el_csrf_del_meta(js):
    assert 'meta[name="csrf-token"]' in js
    assert 'cuerpo.set("csrf_token"' in js


def test_el_javascript_manda_la_pantalla_actual(js):
    """Sin esto, "¿y acá cómo agrego uno?" no tiene referente."""
    assert "window.location.pathname" in js


def test_el_javascript_usa_fetch_y_no_eventsource(js):
    """`EventSource` sólo hace GET y el endpoint necesita POST."""
    assert not re.search(r"new\s+EventSource", js)
    assert "fetch(" in js
    assert "getReader()" in js


def test_el_javascript_guarda_el_hilo_por_pestania(js):
    assert "sessionStorage" in js
    assert "localStorage" not in js


def test_el_javascript_tiene_atajo_de_teclado(js):
    assert '"i"' in js and "ctrlKey" in js


def test_el_javascript_permite_salto_de_linea_con_shift(js):
    """Enter envía, Shift+Enter hace un salto: si no, no se puede escribir una lista."""
    assert 'evento.key === "Enter" && !evento.shiftKey' in js


# --------------------------------------------------------------------------- #
# El CSS construido
# --------------------------------------------------------------------------- #

# Clases de valor arbitrario y colores que sólo aparecen en el JavaScript. Son
# exactamente las que Tailwind puede no extraer: las de valor arbitrario porque
# su extractor tiene que adivinar los corchetes, y las de color porque no están
# en ninguna plantilla. Si alguna falta, el widget se ve a medio pintar y nada
# más lo avisa.
CLASES_FRAGILES = (
    "max-w-[85%]",
    "z-[150]",
    "h-[min(36rem,calc(100vh-7rem))]",
    "w-[min(26rem,calc(100vw-2rem))]",
    "bg-alerta-50",
    "border-alerta-200",
    "bg-peligro-50",
    "border-peligro-200",
    "hover:text-primary-700",
    "shadow-pop",
)


def _css_sin_escapes(css):
    """Devuelve el CSS con los escapes resueltos.

    Tailwind escapa lo que no es válido en un selector: `.max-w-\\[85\\%\\]` y
    `.h-\\[min\\(36rem\\2c calc\\(100vh-7rem\\)\\)\\]`. La coma va como escape
    hexadecimal (`\\2c`), no como `\\,`, así que sacar las barras invertidas no
    alcanza: hay que decodificar de verdad para poder comparar el nombre de la
    clase tal como se escribe en el código.
    """
    def reemplazo(m):
        return chr(int(m.group(1), 16)) if m.group(1) else m.group(2)

    return re.sub(r"\\([0-9a-fA-F]{1,6}) ?|\\(.)", reemplazo, css)


def test_el_css_tiene_las_clases_que_el_widget_necesita():
    """El CSS construido tiene que incluir lo que el widget usa.

    Tailwind busca los nombres de clase en el código y genera sólo esos. Una
    clase escrita en el JavaScript que el extractor no reconoce —o un CSS que
    quedó sin reconstruir— no da ningún error: simplemente el elemento sale sin
    estilo. Esta prueba lo convierte en un fallo.

    Ya encontró algo real: con las clases de tamaño escritas como
    `h-[min(...)]`, la comprobación falló primero por el escape de la coma y
    después por una reconstrucción pendiente. Sin esto, el panel se habría
    renderizado sin alto ni ancho.
    """
    ruta = os.path.join(RAIZ, "static", "css", "tailwind.css")
    if not os.path.exists(ruta):
        pytest.skip("no hay CSS construido; corré `npm run build:css`")

    plano = _css_sin_escapes(open(ruta, encoding="utf-8").read())
    faltan = [c for c in CLASES_FRAGILES if f".{c}" not in plano]

    assert not faltan, (
        f"clases ausentes del CSS construido: {faltan}. "
        f"Corré `npm run build:css`."
    )


def test_la_comprobacion_de_css_detecta_una_clase_inexistente():
    """La prueba de arriba sólo sirve si de verdad falla cuando falta algo."""
    plano = _css_sin_escapes(open(
        os.path.join(RAIZ, "static", "css", "tailwind.css"), encoding="utf-8").read())
    assert ".clase-que-no-existe-en-el-css" not in plano
