"""Pruebas del mapa del sistema — el conocimiento de Caty.

Caty es la instructora de uso. Si su mapa del sistema está incompleto, enseña mal,
y ninguna capa de seguridad arregla un instructor que manda a la gente a botones
que no existen.

Estas pruebas son offline y sin costo: no llaman a DeepSeek. Verifican la
propiedad que sostiene todo lo demás — que el mapa cubra la aplicación entera y
que sea estable en el tiempo.
"""

import os
import re

import pytest

from services.agente import knowledge

RAIZ = knowledge.RAIZ


@pytest.fixture(scope="module")
def mapa():
    return knowledge.construir_mapa()


# --------------------------------------------------------------------------- #
# Cobertura: el "sabe el 100%"
# --------------------------------------------------------------------------- #


def test_no_hay_routers_ilegibles(mapa):
    """Un router que no parsea es un hueco silencioso de conocimiento."""
    assert mapa.routers_fallidos == []


def test_todas_las_rutas_del_proyecto_estan_en_el_mapa(mapa):
    """El mapa tiene que tener exactamente las rutas declaradas en `routers/`.

    Se cuenta con una expresión regular independiente del analizador: si los dos
    métodos coinciden, el AST no se está comiendo decoradores.
    """
    declaradas = 0
    patron = re.compile(r"@router\.(get|post|put|delete|patch)\(")
    for nombre in sorted(os.listdir(RAIZ / "routers")):
        if not nombre.endswith(".py") or nombre == "__init__.py":
            continue
        fuente = (RAIZ / "routers" / nombre).read_text(encoding="utf-8")
        declaradas += len(patron.findall(fuente))

    assert len(mapa.rutas) == declaradas
    assert declaradas > 100  # una caída brusca significa que el análisis se rompió


def test_cada_ruta_tiene_metodo_y_camino(mapa):
    for ruta in mapa.rutas:
        assert ruta.metodo in {"GET", "POST", "PUT", "DELETE", "PATCH"}
        assert ruta.path.startswith("/"), ruta
        assert ruta.router.endswith(".py")


def test_el_prefijo_de_auth_se_aplica(mapa):
    """`routers/auth.py` declara el prefijo en el router, no en el decorador."""
    auth = [r.path for r in mapa.rutas if r.router == "auth.py"]
    assert auth, "no se extrajo ninguna ruta de auth.py"
    assert all(p.startswith("/auth/") for p in auth), auth


def test_toda_plantilla_renderizada_existe_en_disco(mapa):
    """Una ruta que nombra una plantilla inexistente es una pantalla rota."""
    for ruta in mapa.rutas:
        if ruta.plantilla:
            assert ruta.plantilla in mapa.pantallas, f"{ruta.clave} -> {ruta.plantilla}"


def test_no_hay_pantallas_huerfanas(mapa):
    """Una plantilla que nadie renderiza es funcionalidad inalcanzable."""
    assert mapa.huerfanas == []


def test_las_pantallas_con_ruta_tienen_contenido(mapa):
    """Una pantalla sin acciones, campos ni encabezados no enseña nada.

    `error.html` es la excepción legítima: se renderiza desde el manejador global
    de excepciones, no desde una ruta, y su contenido son variables.
    """
    vacias = [
        p.plantilla for p in mapa.pantallas_reales
        if p.plantilla != "error.html"
        and not p.acciones and not p.campos and not p.encabezados
    ]
    assert vacias == []


def test_las_pantallas_de_formulario_tienen_campos(mapa):
    """Alta y edición sin campos extraídos significan que el parser falló."""
    for pantalla in mapa.pantallas_reales:
        if pantalla.plantilla.startswith(("nuevo_", "nueva_", "editar_")):
            assert pantalla.campos or pantalla.acciones, pantalla.plantilla


def test_no_se_cuelan_campos_ocultos(mapa):
    """`csrf_token` no es un campo que el usuario complete."""
    nombres = {c.nombre for p in mapa.pantallas.values() for c in p.campos}
    assert "csrf_token" not in nombres


def test_no_se_cuelan_iconos_como_etiquetas(mapa):
    """Los nombres de los iconos de Material Symbols no son texto de la interfaz."""
    iconos = {"save", "add", "edit", "delete", "chevron_right", "close", "search"}
    for pantalla in mapa.pantallas.values():
        assert not (set(pantalla.acciones) & iconos), pantalla.plantilla


def test_el_reparto_de_plantillas_cierra(mapa):
    """Pantallas + layouts + parciales tienen que dar el total de plantillas."""
    total = len(mapa.pantallas_reales) + len(mapa.layouts) + len(mapa.parciales_por_nombre)
    assert total == len(mapa.pantallas)


# --------------------------------------------------------------------------- #
# Calidad de las etiquetas
# --------------------------------------------------------------------------- #


def test_no_quedan_expresiones_de_jinja_en_el_mapa(mapa):
    """`{{ p }}` es el número de página, no una etiqueta que el usuario lea.

    Las plantillas están llenas de expresiones que sólo existen en tiempo de
    render. Dejarlas en el mapa le enseña a Caty etiquetas que nadie ve en
    pantalla, y una etiqueta inventada es peor que ninguna: manda a la gente a
    botones que no existen.
    """
    jinja = re.compile(r"\{\{|\{%")
    ofensores = []
    for pantalla in mapa.pantallas.values():
        for tipo, valores in (
            ("acción", pantalla.acciones),
            ("encabezado", pantalla.encabezados),
            ("columna", pantalla.columnas),
            ("opción", [v for vs in pantalla.opciones.values() for v in vs]),
        ):
            for valor in valores:
                if jinja.search(valor):
                    ofensores.append(f"{pantalla.plantilla} {tipo}: {valor[:60]}")
        for campo in pantalla.campos:
            if jinja.search(campo.etiqueta) or jinja.search(campo.ayuda):
                ofensores.append(f"{pantalla.plantilla} campo {campo.nombre}")
        if jinja.search(pantalla.titulo):
            ofensores.append(f"{pantalla.plantilla} título: {pantalla.titulo[:60]}")

    assert not ofensores, f"expresiones de Jinja sin resolver: {ofensores[:6]}"


def test_las_etiquetas_tienen_sustancia(mapa):
    """Una etiqueta de dos letras o de puros signos no le sirve a nadie."""
    for pantalla in mapa.pantallas.values():
        for accion in pantalla.acciones:
            assert knowledge.tiene_sustancia(accion), f"{pantalla.plantilla}: {accion!r}"


def test_limpiar_jinja_deja_el_texto_visible():
    """La limpieza no puede comerse las etiquetas reales que rodean a la expresión."""
    assert knowledge.limpiar_jinja("{{ p }}") == ""
    assert knowledge.limpiar_jinja("{{ cli_name }}") == ""
    assert knowledge.limpiar_jinja(
        "{{ boton_exportar('/x', y) }} Nuevo Relevamiento") == "Nuevo Relevamiento"
    assert knowledge.limpiar_jinja("Vaciar{{ ' (' ~ n ~ ')' if a else '' }}") == "Vaciar"
    assert knowledge.limpiar_jinja("Limpiar ({{ activos }})") == "Limpiar"
    assert knowledge.limpiar_jinja("Importar {{ filas|length }} registros") == "Importar registros"


def test_tiene_sustancia_exige_tres_letras():
    """El umbral de tres no es arbitrario: se midió.

    Las etiquetas más cortas que existen hoy en la aplicación son «Hoy», «Mes»,
    «Rol», «Fin» y «SWA», todas de tres letras. Con dos se cuela basura de la
    limpieza de Jinja; con tres no se pierde nada real.

    La excepción son los acrónimos de dos letras en mayúsculas: **«AT» es el
    Asistente Técnico**, la palabra central de la aplicación, y con el piso pelado
    de tres la columna «AT» de la tabla de Equipos no llegaba al mapa.
    """
    assert knowledge.tiene_sustancia("Hoy")
    assert knowledge.tiene_sustancia("SWA")
    assert knowledge.tiene_sustancia("AT")
    assert knowledge.tiene_sustancia("S/N")
    assert not knowledge.tiene_sustancia("Ir")
    assert not knowledge.tiene_sustancia("de")
    assert not knowledge.tiene_sustancia("")
    assert not knowledge.tiene_sustancia("()")
    assert not knowledge.tiene_sustancia("· |")


def test_las_etiquetas_cortas_son_acronimos(mapa):
    """Lo único que puede quedar por debajo de tres letras es un acrónimo.

    El umbral es de tres caracteres. La excepción son los acrónimos de dos letras
    en mayúsculas, que sí son etiquetas reales: «AT». Cualquier otra cosa corta que
    aparezca en el mapa es basura de la limpieza de Jinja y hay que verla.
    """
    def cortas_de(texto):
        return len(re.sub(r"\W", "", texto, flags=re.UNICODE)) < 3

    culpables = [
        f"{p.plantilla}: {v!r}"
        for p in mapa.pantallas.values()
        for v in p.acciones + p.encabezados + p.columnas
        if cortas_de(v) and not re.fullmatch(r"[A-ZÁÉÍÓÚÑ]{2}",
                                             re.sub(r"\W", "", v, flags=re.UNICODE))
    ]
    assert not culpables, (
        f"etiquetas cortas que no son acrónimos: {culpables}. Si son reales, "
        f"revisá el umbral de `tiene_sustancia`.")


# --------------------------------------------------------------------------- #
# Estabilidad: el caché de prefijo
# --------------------------------------------------------------------------- #


def test_el_conocimiento_es_estable(mapa):
    """Dos construcciones seguidas tienen que dar el mismo texto.

    Si no, el prefijo que DeepSeek cachea cambia solo y cada consulta pasa a
    costar unas cincuenta veces más. Es la clase de falla que no rompe nada
    visible y aparece recién en la factura.
    """
    primera = knowledge.construir_conocimiento()
    segunda = knowledge.construir_conocimiento()
    assert primera == segunda
    assert primera.strip()


def test_el_conocimiento_no_lleva_fecha(mapa):
    """La fecha de generación es para el archivo revisable, no para el prompt."""
    conocimiento = knowledge.construir_conocimiento()
    assert "Generado:" not in conocimiento


def test_el_mapa_revisable_si_lleva_fecha():
    texto = knowledge.render_mapa(knowledge.construir_mapa())
    assert "Generado:" in texto


def test_el_conocimiento_incluye_el_manual_y_el_mapa():
    conocimiento = knowledge.construir_conocimiento()
    assert "===== MAPA DEL SISTEMA =====" in conocimiento
    assert "funcionalidades.md" in conocimiento


# --------------------------------------------------------------------------- #
# Casos borde del análisis
# --------------------------------------------------------------------------- #


def test_una_plantilla_desconocida_no_rompe_el_analisis(tmp_path):
    """El generador no debe depender de que existan las plantillas del proyecto."""
    vacio = tmp_path / "plantillas"
    vacio.mkdir()
    mapa = knowledge.construir_mapa(dir_plantillas=vacio, dir_codigo=tmp_path)
    assert mapa.pantallas == {}
    assert mapa.pantallas_reales == []


def test_un_router_ilegible_se_reporta_y_no_tumba_la_construccion(tmp_path):
    routers = tmp_path / "routers"
    routers.mkdir()
    (routers / "roto.py").write_text("def f(:", encoding="utf-8")
    (routers / "ok.py").write_text(
        "from fastapi import APIRouter\n"
        "router = APIRouter()\n"
        '@router.get("/x")\n'
        "def x():\n"
        '    """Hace algo."""\n'
        "    return None\n",
        encoding="utf-8",
    )
    mapa = knowledge.construir_mapa(
        dir_routers=routers, dir_plantillas=tmp_path, dir_codigo=tmp_path
    )
    assert mapa.routers_fallidos == ["roto.py"]
    assert [r.path for r in mapa.rutas] == ["/x"]
    assert mapa.rutas[0].resumen == "Hace algo."


def test_la_plantilla_se_extrae_de_las_dos_formas_de_template_response(tmp_path):
    routers = tmp_path / "routers"
    routers.mkdir()
    (routers / "dos.py").write_text(
        "from fastapi import APIRouter\n"
        "router = APIRouter()\n"
        '@router.get("/vieja")\n'
        "def vieja():\n"
        '    return templates.TemplateResponse("vieja.html", {})\n'
        '@router.get("/nueva")\n'
        "def nueva():\n"
        '    return templates.TemplateResponse(request, "nueva.html", {})\n',
        encoding="utf-8",
    )
    mapa = knowledge.construir_mapa(
        dir_routers=routers, dir_plantillas=tmp_path, dir_codigo=tmp_path
    )
    assert {r.path: r.plantilla for r in mapa.rutas} == {
        "/vieja": "vieja.html",
        "/nueva": "nueva.html",
    }


def test_una_plantilla_sin_nombre_literal_queda_como_hueco(tmp_path):
    """Si el nombre viene en una variable, se reporta vacío en vez de inventarse."""
    routers = tmp_path / "routers"
    routers.mkdir()
    (routers / "dyn.py").write_text(
        "from fastapi import APIRouter\n"
        "router = APIRouter()\n"
        '@router.get("/d")\n'
        "def d(nombre):\n"
        "    return templates.TemplateResponse(request, nombre, {})\n",
        encoding="utf-8",
    )
    mapa = knowledge.construir_mapa(
        dir_routers=routers, dir_plantillas=tmp_path, dir_codigo=tmp_path
    )
    assert mapa.rutas[0].plantilla == ""
    assert len(mapa.rutas_sin_plantilla) == 1


def test_los_parciales_por_include_e_import_se_detectan(tmp_path):
    plantillas = tmp_path / "plantillas"
    plantillas.mkdir()
    (plantillas / "base.html").write_text("{% include '_a.html' %}", encoding="utf-8")
    (plantillas / "otra.html").write_text("{% from '_b.html' import modal %}", encoding="utf-8")
    (plantillas / "_a.html").write_text("<p>a</p>", encoding="utf-8")
    (plantillas / "_b.html").write_text("<p>b</p>", encoding="utf-8")
    (plantillas / "huerfana.html").write_text("<p>h</p>", encoding="utf-8")

    mapa = knowledge.construir_mapa(
        dir_routers=tmp_path, dir_plantillas=plantillas, dir_codigo=tmp_path
    )
    assert mapa.parciales == {"_a.html", "_b.html"}
    # Ninguna ruta renderiza nada acá, así que las tres pantallas quedan huérfanas;
    # lo que importa es que los parciales no aparezcan entre ellas.
    assert mapa.huerfanas == ["base.html", "huerfana.html", "otra.html"]
    assert not set(mapa.huerfanas) & mapa.parciales
