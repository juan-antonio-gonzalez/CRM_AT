"""Mapa del sistema — de dónde sale lo que Caty sabe.

Caty es la instructora de uso de la aplicación. Para enseñar dónde está cada cosa
tiene que conocer las pantallas reales, no una descripción de las pantallas.

De ahí la decisión central de este módulo: **el conocimiento se extrae del código,
no de la documentación.** Los tres documentos de ``docs/`` explican intenciones y
se desactualizan; las 42 plantillas de ``templates/`` contienen el texto literal
que el usuario ve en pantalla. Si Caty dice "hacé clic en *Guardar*" y el botón
dice *Registrar*, el instructor pierde credibilidad en la segunda respuesta.

Tres fuentes:

* **A — Manual de negocio** (``docs/*.md``): reglas, flujos, criterios.
* **B — Mapa de rutas**: las 124 rutas reales, por análisis estático de ``routers/``.
* **C — Inventario de interfaz**: botones, campos y columnas de ``templates/``.

Todo es análisis estático: no se importa la aplicación ni se toca la base de datos.
Eso permite construir el mapa desde un test, desde un script o al arrancar el
servicio, sin efectos secundarios y sin depender de que la base esté levantada.

Uso::

    python -m services.agente.knowledge     # regenera docs/_mapa-sistema.md

El archivo generado es un artefacto de revisión humana: sirve para leerlo,
diffearlo y detectar cuándo una pantalla cambió. No se edita a mano.
"""

from __future__ import annotations

import ast
import datetime
import re
from dataclasses import dataclass, field
from html.parser import HTMLParser
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
DIR_ROUTERS = RAIZ / "routers"
DIR_PLANTILLAS = RAIZ / "templates"
DIR_DOCS = RAIZ / "docs"

DESTINO_MAPA = DIR_DOCS / "_mapa-sistema.md"

# El manual de negocio, en el orden en que conviene leerlo: primero qué hace la
# aplicación, después cómo está guardado, y por último el detalle de reconstrucción.
FUENTES_MANUAL = (
    "funcionalidades.md",
    "basededatos.md",
    "prompt-para-ia.md",
)

METODOS_HTTP = {"get", "post", "put", "delete", "patch"}

# Elementos cuyo texto no es una etiqueta visible para el usuario: si se cuelan,
# el inventario se llena de "add", "edit" y "chevron_right".
CLASES_IGNORADAS = ("material-symbols",)
ETIQUETAS_IGNORADAS = {"script", "style", "svg", "path", "noscript"}

# Elementos sin cierre. Si se apilaran, corromperían el seguimiento de etiquetas.
ETIQUETAS_VACIAS = {
    "area", "base", "br", "col", "embed", "hr", "img",
    "input", "link", "meta", "param", "source", "track", "wbr",
}

# Elementos cuyo texto sí le importa al usuario.
ETIQUETAS_CAPTURA = {
    "title", "h1", "h2", "h3", "legend", "button", "a",
    "label", "th", "option", "summary",
}

_ESPACIOS = re.compile(r"\s+")

# Jinja sin resolver. Las plantillas están llenas de `{{ p }}` (el número de
# página), `{{ cli_name }}` y `{{ boton_exportar(...) }}`: son valores que sólo
# existen en tiempo de render. Dejarlos en el mapa le enseña a Caty etiquetas que
# nadie ve en pantalla, y una etiqueta inventada es peor que ninguna.
_EXPRESION_JINJA = re.compile(r"\{\{.*?\}\}", re.DOTALL)
_SENTENCIA_JINJA = re.compile(r"\{%.*?%\}", re.DOTALL)
# Lo que queda cuando se saca una expresión de adentro de un texto: `Limpiar ()`
# o `Resultados para «»`.
_RESIDUO_JINJA = re.compile(r"[«»]|\(\s*\)|\[\s*\]")
# Para descartar lo que quedó sin sustancia: menos de tres letras o dígitos.
_SIN_SUSTANCIA = re.compile(r"\W", re.UNICODE)


def limpiar_jinja(texto: str) -> str:
    """Saca las expresiones de Jinja y deja sólo el texto que el usuario ve.

    No parte los condicionales en ramas: `{% if %}A{% else %}B{% endif %}` queda
    como `A B`. Es deliberado — las dos ramas son etiquetas reales, y separarlas
    requeriría un parser de plantillas para un beneficio que no se nota.
    """
    limpio = _EXPRESION_JINJA.sub(" ", texto or "")
    limpio = _SENTENCIA_JINJA.sub(" ", limpio)
    limpio = _RESIDUO_JINJA.sub(" ", limpio)
    limpio = _ESPACIOS.sub(" ", limpio).strip()
    return limpio.strip(" -–—·,;:|")


# Un acrónimo de dos letras en mayúsculas: AT, ID, OK.
_RE_ACRONIMO = re.compile(r"^[A-ZÁÉÍÓÚÑ]{2}$")

# `{% call modal('id', 'Título', ...) %}`: el segundo argumento es el título.
_TITULOS_DE_MODAL = re.compile(r"modal\(\s*'[^']*'\s*,\s*'([^']{3,90})'", re.S)


def tiene_sustancia(texto: str) -> bool:
    """¿Queda algo legible, o sólo signos?

    El piso de tres caracteres descarta «·» y «--», pero se llevaba puestos los
    acrónimos de dos letras, y **AT** es la palabra central de esta aplicación: es
    el Asistente Técnico. La columna «AT» de la tabla de Equipos no llegaba al
    mapa, así que Caty no tenía de dónde sacar el nombre de esa columna.
    """
    limpio = _SIN_SUSTANCIA.sub("", texto or "")
    return len(limpio) >= 3 or bool(_RE_ACRONIMO.match(limpio))


def _limpiar(texto: str) -> str:
    """Colapsa espacios y descarta lo que no aporta como etiqueta."""
    return _ESPACIOS.sub(" ", texto or "").strip()


def _etiqueta(texto: str) -> str:
    """Texto listo para el mapa: sin Jinja, sin espacios de más, con sustancia."""
    limpio = limpiar_jinja(_limpiar(texto))
    return limpio if tiene_sustancia(limpio) else ""


# --------------------------------------------------------------------------- #
# Fuente C — inventario de interfaz
# --------------------------------------------------------------------------- #


@dataclass
class Campo:
    """Un campo de formulario, con el nombre que el usuario lee en pantalla."""

    nombre: str
    etiqueta: str = ""
    tipo: str = ""
    ayuda: str = ""


@dataclass
class Pantalla:
    """Todo lo que el usuario ve en una plantilla."""

    plantilla: str
    titulo: str = ""
    encabezados: list[str] = field(default_factory=list)
    acciones: list[str] = field(default_factory=list)
    campos: list[Campo] = field(default_factory=list)
    columnas: list[str] = field(default_factory=list)
    opciones: dict[str, list[str]] = field(default_factory=dict)
    extiende: str = ""
    rutas: list[str] = field(default_factory=list)

    @property
    def es_parcial(self) -> bool:
        """Los parciales empiezan con guión bajo y no son pantallas completas."""
        return self.plantilla.startswith("_")


class _ExtractorInterfaz(HTMLParser):
    """Recorre una plantilla y junta las etiquetas que el usuario ve.

    Se apilan *todos* los elementos abiertos, no sólo los que capturan texto: hace
    falta saber si el texto que llega está dentro de un icono o de un script. Un
    `<button>` con un `<span class="material-symbols">save</span>` adentro tiene
    que aportar "Guardar", no "Guardar save".
    """

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.titulo = ""
        self.encabezados: list[str] = []
        self.acciones: list[str] = []
        self.columnas: list[str] = []
        self.opciones: dict[str, list[str]] = {}
        self._etiqueta_por_id: dict[str, str] = {}
        self._campos: list[Campo] = []
        self._pila: list[dict] = []
        self._ignorar = 0
        self._select: list[str] = []

    # -- recorrido ---------------------------------------------------------- #

    def handle_starttag(self, tag, attrs):
        atributos = {clave: (valor or "") for clave, valor in attrs}

        clases = atributos.get("class", "")
        ignorado = tag in ETIQUETAS_IGNORADAS or any(
            clase in clases for clase in CLASES_IGNORADAS
        )
        if ignorado:
            self._ignorar += 1

        if tag == "select":
            self._select.append(atributos.get("name", "") or "")
        elif tag == "input":
            self._registrar_input(atributos)

        if tag in ETIQUETAS_VACIAS:
            # No se apila, pero el efecto de `ignorado` ya se aplicó arriba. Un
            # elemento vacío nunca abre un bloque, así que no hay nada que cerrar.
            if ignorado:
                self._ignorar -= 1
            return

        self._pila.append({
            "tag": tag,
            "para": atributos.get("for", ""),
            "ignorado": ignorado,
            "buffer": [] if tag in ETIQUETAS_CAPTURA else None,
        })

    def handle_startendtag(self, tag, attrs):
        # `<br/>`, `<input/>`: se procesan los atributos sin tocar la pila.
        atributos = {clave: (valor or "") for clave, valor in attrs}
        if tag == "input":
            self._registrar_input(atributos)

    def handle_endtag(self, tag):
        # Se desapila hasta encontrar la etiqueta que cierra. Las plantillas de
        # Jinja dejan etiquetas sin cerrar según la rama del `if`, así que no se
        # puede confiar en que el cierre sea el tope de la pila.
        for indice in range(len(self._pila) - 1, -1, -1):
            if self._pila[indice]["tag"] == tag:
                for frame in reversed(self._pila[indice:]):
                    self._cerrar_frame(frame)
                del self._pila[indice:]
                break

    def handle_data(self, data):
        if self._ignorar:
            return
        for frame in self._pila:
            if frame["buffer"] is not None:
                frame["buffer"].append(data)

    def close(self):
        super().close()
        # Las plantillas con ramas condicionales pueden dejar la pila abierta.
        for frame in reversed(self._pila):
            self._cerrar_frame(frame)
        self._pila.clear()

    # -- acumulación -------------------------------------------------------- #

    def _cerrar_frame(self, frame: dict) -> None:
        if frame["ignorado"]:
            self._ignorar = max(0, self._ignorar - 1)
        if frame["tag"] == "select" and self._select:
            self._select.pop()
        if frame["buffer"] is None:
            return

        tag = frame["tag"]
        texto = _etiqueta("".join(frame["buffer"]))
        if not texto:
            return

        if tag == "title":
            self.titulo = texto
        elif tag in ("h1", "h2", "h3", "legend", "summary"):
            _agregar_unico(self.encabezados, texto)
        elif tag == "th":
            _agregar_unico(self.columnas, texto)
        elif tag in ("button", "a"):
            _agregar_unico(self.acciones, texto)
        elif tag == "label":
            identificador = _identificador_de_label(frame)
            if identificador:
                self._etiqueta_por_id[identificador] = texto
            else:
                _agregar_unico(self.encabezados, texto)
        elif tag == "option":
            if self._select:
                lista = self.opciones.setdefault(self._select[-1], [])
                _agregar_unico(lista, texto)

    def _registrar_input(self, atributos: dict) -> None:
        nombre = atributos.get("name", "")
        if not nombre:
            return
        tipo = atributos.get("type", "text")
        # Los ocultos no se ven ni se completan: `csrf_token` aparecía como si
        # fuera un campo del formulario de alta de cliente.
        if tipo == "hidden":
            return
        self._campos.append(Campo(
            nombre=nombre,
            tipo=tipo,
            ayuda=_etiqueta(atributos.get("placeholder", "")),
        ))

    def campos(self) -> list[Campo]:
        """Campos con la etiqueta visible ya resuelta.

        La mayoría de los formularios usan ``<label for="x">``, pero varios
        envuelven el input: en ese caso la etiqueta se recoge del texto del label
        y se asocia por posición.
        """
        for campo in self._campos:
            campo.etiqueta = self._etiqueta_por_id.get(campo.nombre, "")
        return self._campos


def _identificador_de_label(frame: dict) -> str:
    return frame.get("para", "") or ""


def _agregar_unico(lista: list[str], valor: str) -> None:
    if valor and valor not in lista:
        lista.append(valor)


_PLANTILLA_EXTIENDE = re.compile(r"{%-?\s*extends\s+[\"']([^\"']+)[\"']")
# Tres formas de traer otra plantilla: incluirla, importar sus macros, o importar
# un macro puntual. `_ui.html` se trae con `{% from %}`, y sin contemplarlo el
# parcial quedaba como si nadie lo usara.
_PLANTILLA_INCLUYE = re.compile(
    r"{%-?\s*(?:include|import|from)\s+[\"']([^\"']+)[\"']"
)
# El `<title>` vive en `layout.html`; cada pantalla aporta el suyo con este bloque.
_BLOQUE_TITULO = re.compile(
    r"{%-?\s*block\s+title\s*-?%}(.*?){%-?\s*endblock", re.DOTALL
)


def leer_pantalla(ruta: Path) -> Pantalla:
    """Inventario de una plantilla."""
    fuente = ruta.read_text(encoding="utf-8", errors="replace")

    pantalla = Pantalla(plantilla=ruta.name)
    hereda = _PLANTILLA_EXTIENDE.search(fuente)
    pantalla.extiende = hereda.group(1) if hereda else ""

    extractor = _ExtractorInterfaz()
    extractor.feed(fuente)
    extractor.close()

    # El bloque `title` es el título real de la pestaña: casi ninguna plantilla
    # trae un `<title>` propio porque lo hereda del layout.
    bloque = _BLOQUE_TITULO.search(fuente)
    pantalla.titulo = extractor.titulo or (_etiqueta(bloque.group(1)) if bloque else "")
    pantalla.encabezados = extractor.encabezados
    # Los títulos de los modales son argumentos de una macro, no elementos del
    # HTML: el extractor no los ve, y con ellos se pierde el nombre de la acción
    # —«Actualizar las asignaciones», «Desactivar equipo»—, que es justo lo que
    # alguien busca cuando pregunta cómo se hace algo que está en un modal.
    for titulo_modal in _TITULOS_DE_MODAL.findall(fuente):
        etiqueta = _etiqueta(titulo_modal)
        if etiqueta:
            _agregar_unico(pantalla.encabezados, etiqueta)
    pantalla.acciones = extractor.acciones
    pantalla.columnas = extractor.columnas
    pantalla.opciones = extractor.opciones
    pantalla.campos = extractor.campos()
    return pantalla


def plantillas_incluidas(fuente: str) -> set[str]:
    """Nombres de plantilla referenciados con ``{% include %}``."""
    return {Path(m).name for m in _PLANTILLA_INCLUYE.findall(fuente)}


# --------------------------------------------------------------------------- #
# Fuente B — mapa de rutas
# --------------------------------------------------------------------------- #


@dataclass
class Ruta:
    """Una ruta HTTP, con la pantalla que renderiza si renderiza alguna."""

    metodo: str
    path: str
    funcion: str
    router: str
    resumen: str = ""
    plantilla: str = ""

    @property
    def clave(self) -> str:
        return f"{self.metodo} {self.path}"


class _LectorRouters(ast.NodeVisitor):
    """Recorre un módulo de router y saca sus rutas."""

    def __init__(self, archivo: Path) -> None:
        self.archivo = archivo
        self.prefijo = ""
        self.rutas: list[Ruta] = []
        # Las funciones del módulo, para poder seguir el render cuando la ruta
        # lo delega en un ayudante.
        self.funciones: dict = {}

    def analizar(self, arbol: ast.Module) -> list[Ruta]:
        self.prefijo = _prefijo_del_router(arbol)
        self.funciones = {
            n.name: n for n in ast.walk(arbol)
            if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
        }
        for nodo in ast.walk(arbol):
            if isinstance(nodo, (ast.FunctionDef, ast.AsyncFunctionDef)):
                self._revisar_funcion(nodo)
        return self.rutas

    def _revisar_funcion(self, nodo) -> None:
        for decorador in nodo.decorator_list:
            if not isinstance(decorador, ast.Call):
                continue
            funcion = decorador.func
            if not isinstance(funcion, ast.Attribute):
                continue
            if funcion.attr not in METODOS_HTTP:
                continue

            camino = _primer_texto(decorador.args) or _texto_kw(decorador, "path")
            if camino is None:
                continue

            self.rutas.append(Ruta(
                metodo=funcion.attr.upper(),
                path=self.prefijo + camino,
                funcion=nodo.name,
                router=self.archivo.name,
                resumen=_resumen(nodo),
                plantilla=_plantilla_de(nodo, self.funciones) or "",
            ))


def _prefijo_del_router(arbol: ast.Module) -> str:
    """``APIRouter(prefix="/auth")`` — hoy sólo lo usa ``routers/auth.py``."""
    for nodo in ast.walk(arbol):
        if not isinstance(nodo, ast.Assign):
            continue
        if not isinstance(nodo.value, ast.Call):
            continue
        funcion = nodo.value.func
        if not (isinstance(funcion, ast.Name) and funcion.id == "APIRouter"):
            continue
        # En este proyecto el prefijo siempre va por palabra clave: los decoradores
        # declaran la ruta completa salvo en `auth.py`, que la declara en el router.
        for clave in nodo.value.keywords:
            if clave.arg == "prefix" and isinstance(clave.value, ast.Constant):
                return str(clave.value.value)
    return ""


def _primer_texto(argumentos: list[ast.expr]) -> str | None:
    for argumento in argumentos:
        if isinstance(argumento, ast.Constant) and isinstance(argumento.value, str):
            return argumento.value
    return None


def _texto_kw(llamada: ast.Call, nombre: str) -> str | None:
    for clave in llamada.keywords:
        if clave.arg == nombre and isinstance(clave.value, ast.Constant):
            return str(clave.value.value)
    return None


def _resumen(nodo) -> str:
    """Primera línea del docstring: es la mejor descripción de para qué sirve."""
    documento = ast.get_docstring(nodo) or ""
    for linea in documento.splitlines():
        linea = linea.strip()
        if linea:
            return linea
    return ""


def _renderiza_directo(nodo) -> str | None:
    """El ``TemplateResponse`` que haya en el cuerpo de la función, si hay uno."""
    for llamada in ast.walk(nodo):
        if not isinstance(llamada, ast.Call):
            continue
        funcion = llamada.func
        nombre = funcion.attr if isinstance(funcion, ast.Attribute) else (
            funcion.id if isinstance(funcion, ast.Name) else ""
        )
        if nombre != "TemplateResponse":
            continue
        candidato = _primer_texto(llamada.args) or _texto_kw(llamada, "name")
        if candidato and candidato.endswith(".html"):
            return Path(candidato).name
    return None


def _plantilla_de(nodo, funciones: dict | None = None,
                  visitados: set | None = None) -> str | None:
    """Nombre de la plantilla que termina renderizando la función.

    Se aceptan las dos formas de ``TemplateResponse``: la nueva
    (``request, "x.html"``) y la vieja (``"x.html", {...}``). En ambas alcanza con
    buscar el primer argumento que sea un texto terminado en ``.html``; si el
    nombre viene en una variable no se puede resolver de forma estática, y eso se
    reporta como hueco en vez de inventarse.

    **Si la ruta no renderiza directamente, se sigue la llamada a una función del
    mismo módulo.** Una ruta que delega el render en un ayudante —como
    ``_pantalla()`` en ``routers/teams.py``— quedaba sin plantilla asociada, y el
    mapa perdía la relación entre `/equipos` y la pantalla de Equipos. Sin esa
    relación, Caty no puede decir dónde está cada cosa y la prueba de cobertura
    del set de evaluación ni se entera de que falta.

    El conjunto de visitados evita que dos funciones que se llaman entre sí
    cuelguen el generador.
    """
    visitados = visitados if visitados is not None else set()
    if nodo.name in visitados:
        return None
    visitados.add(nodo.name)

    directo = _renderiza_directo(nodo)
    if directo:
        return directo

    if not funciones:
        return None

    for llamada in ast.walk(nodo):
        if not isinstance(llamada, ast.Call) or not isinstance(llamada.func, ast.Name):
            continue
        ayudante = funciones.get(llamada.func.id)
        if ayudante is None:
            continue
        encontrado = _plantilla_de(ayudante, funciones, visitados)
        if encontrado:
            return encontrado
    return None


def leer_rutas(directorio: Path = DIR_ROUTERS) -> tuple[list[Ruta], list[str]]:
    """Todas las rutas de ``routers/``.

    Devuelve también los archivos que no se pudieron analizar: un router que no
    parsea es un hueco de conocimiento y tiene que ser visible, no silencioso.
    """
    rutas: list[Ruta] = []
    fallidos: list[str] = []
    for archivo in sorted(directorio.glob("*.py")):
        if archivo.name == "__init__.py":
            continue
        try:
            arbol = ast.parse(archivo.read_text(encoding="utf-8"))
        except SyntaxError:
            fallidos.append(archivo.name)
            continue
        rutas.extend(_LectorRouters(archivo).analizar(arbol))
    return rutas, fallidos


def plantillas_renderizadas(directorio: Path = RAIZ) -> set[str]:
    """Plantillas nombradas en cualquier ``TemplateResponse`` del proyecto.

    No alcanza con mirar los routers. ``error.html`` se renderiza desde el
    manejador global de excepciones (``main.py:189``), así que sin este barrido
    aparecería como pantalla huérfana cuando en realidad el usuario la ve cada vez
    que algo falla. Una detección de huérfanos con falsos positivos deja de
    usarse.
    """
    encontradas: set[str] = set()
    archivos = sorted(directorio.glob("*.py")) + sorted((directorio / "routers").glob("*.py"))
    for archivo in archivos:
        try:
            arbol = ast.parse(archivo.read_text(encoding="utf-8"))
        except (SyntaxError, OSError):
            continue
        for llamada in ast.walk(arbol):
            if not isinstance(llamada, ast.Call):
                continue
            funcion = llamada.func
            nombre = funcion.attr if isinstance(funcion, ast.Attribute) else (
                funcion.id if isinstance(funcion, ast.Name) else ""
            )
            if nombre != "TemplateResponse":
                continue
            candidato = _primer_texto(llamada.args) or _texto_kw(llamada, "name")
            if candidato and candidato.endswith(".html"):
                encontradas.add(Path(candidato).name)
    return encontradas


# --------------------------------------------------------------------------- #
# Fuente A — manual de negocio
# --------------------------------------------------------------------------- #


def leer_manual(directorio: Path = DIR_DOCS) -> str:
    """Concatena los documentos de negocio en el orden de ``FUENTES_MANUAL``."""
    partes: list[str] = []
    for nombre in FUENTES_MANUAL:
        archivo = directorio / nombre
        if not archivo.exists():
            continue
        partes.append(f"\n\n===== {nombre} =====\n\n{archivo.read_text(encoding='utf-8')}")
    return "".join(partes).strip()


# --------------------------------------------------------------------------- #
# Conjunto
# --------------------------------------------------------------------------- #


@dataclass
class MapaSistema:
    rutas: list[Ruta]
    pantallas: dict[str, Pantalla]
    routers_fallidos: list[str] = field(default_factory=list)
    parciales: set[str] = field(default_factory=set)
    renderizadas: set[str] = field(default_factory=set)

    @property
    def layouts(self) -> set[str]:
        """Plantillas que otras extienden: son la base, no pantallas.

        ``layout.html`` renderiza una ruta (``GET /search``) y por eso aparecía
        como pantalla, con las 25 acciones de la barra lateral como si fueran
        botones de esa página. No lo son: son la navegación de todas.
        """
        return {p.extiende for p in self.pantallas.values() if p.extiende}

    @property
    def pantallas_reales(self) -> list[Pantalla]:
        """Las pantallas de verdad: ni parciales ni layout."""
        base = self.layouts
        return sorted(
            (p for p in self.pantallas.values()
             if not p.es_parcial and p.plantilla not in base),
            key=lambda p: p.plantilla,
        )

    @property
    def parciales_por_nombre(self) -> list[str]:
        """Plantillas que empiezan con guión bajo: fragmentos, no destinos."""
        return sorted(n for n in self.pantallas if n.startswith("_"))

    @property
    def rutas_sin_plantilla(self) -> list[Ruta]:
        return [r for r in self.rutas if not r.plantilla]

    @property
    def huerfanas(self) -> list[str]:
        """Plantillas que ninguna ruta renderiza y nadie incluye.

        Una pantalla huérfana es funcionalidad que Caty no puede enseñar: no hay
        forma de llegar a ella. Puede ser código muerto, o puede ser una ruta que
        quedó sin registrar y nadie notó.
        """
        return sorted(
            nombre for nombre, pantalla in self.pantallas.items()
            if nombre not in self.renderizadas
            and nombre not in self.parciales
            and nombre not in self.layouts
            and not pantalla.es_parcial
        )


def construir_mapa(
    dir_routers: Path = DIR_ROUTERS,
    dir_plantillas: Path = DIR_PLANTILLAS,
    dir_codigo: Path = RAIZ,
) -> MapaSistema:
    """Reúne las tres fuentes. Análisis estático puro: sin importar la aplicación."""
    rutas, fallidos = leer_rutas(dir_routers)

    pantallas: dict[str, Pantalla] = {}
    parciales: set[str] = set()
    for archivo in sorted(dir_plantillas.glob("*.html")):
        fuente = archivo.read_text(encoding="utf-8", errors="replace")
        parciales |= plantillas_incluidas(fuente)
        pantallas[archivo.name] = leer_pantalla(archivo)

    for ruta in rutas:
        if ruta.plantilla and ruta.plantilla in pantallas:
            pantalla = pantallas[ruta.plantilla]
            if ruta.clave not in pantalla.rutas:
                pantalla.rutas.append(ruta.clave)

    return MapaSistema(
        rutas=rutas,
        pantallas=pantallas,
        routers_fallidos=fallidos,
        parciales=parciales,
        renderizadas=plantillas_renderizadas(dir_codigo),
    )


# --------------------------------------------------------------------------- #
# Render
# --------------------------------------------------------------------------- #


def _tabla(cabeceras: list[str], filas: list[list[str]]) -> str:
    if not filas:
        return "_(sin datos)_\n"
    lineas = ["| " + " | ".join(cabeceras) + " |",
              "|" + "---|" * len(cabeceras)]
    for fila in filas:
        celdas = [str(c).replace("|", "\\|") or "—" for c in fila]
        lineas.append("| " + " | ".join(celdas) + " |")
    return "\n".join(lineas) + "\n"


def render_mapa(
    mapa: MapaSistema,
    generado: datetime.datetime | None = None,
    con_fecha: bool = True,
) -> str:
    """El mapa en markdown.

    ``con_fecha`` existe por el caché de DeepSeek, no por estética. La fecha de
    generación cambia el texto, y el texto es el prefijo que DeepSeek cachea: con
    la fecha adentro, el prefijo se invalida solo cada vez que cambia el minuto y
    cada consulta pasa a costar unas cincuenta veces más. Cuando el mapa se usa
    como conocimiento, va sin fecha; cuando se escribe a un archivo para revisarlo
    a mano, la fecha es justamente lo que se quiere saber.
    """
    generado = generado or datetime.datetime.now()
    sin_titulo = [p for p in mapa.pantallas_reales if not p.titulo]

    partes: list[str] = []
    agregar = partes.append

    agregar("# Mapa del sistema\n")
    agregar("Artefacto generado por `services/agente/knowledge.py`. **No se edita a mano.**\n")
    if con_fecha:
        agregar(f"Generado: {generado:%Y-%m-%d %H:%M}\n")
    agregar(
        "Es el conocimiento de Caty sobre la aplicación, extraído del código y no de la\n"
        "documentación. Sirve para revisar a mano que el mapa esté completo antes de que\n"
        "Caty lo use para enseñar.\n"
    )

    agregar("\n## Cobertura\n")
    agregar(_tabla(["Qué", "Cantidad"], [
        ["Rutas extraídas", len(mapa.rutas)],
        ["Plantillas", len(mapa.pantallas)],
        ["Pantallas", len(mapa.pantallas_reales)],
        ["Layouts", len(mapa.layouts)],
        ["Parciales", len(mapa.parciales_por_nombre)],
        ["Parciales referenciados", len(mapa.parciales)],
        ["Plantillas sin ruta", len(mapa.huerfanas)],
        ["Rutas sin plantilla", len(mapa.rutas_sin_plantilla)],
        ["Routers ilegibles", len(mapa.routers_fallidos)],
        ["Pantallas sin título", len(sin_titulo)],
    ]))
    if mapa.routers_fallidos:
        agregar(f"\n**Atención:** no se pudieron analizar {', '.join(mapa.routers_fallidos)}.\n")
    if sin_titulo:
        agregar("\nPantallas sin título: "
                + ", ".join(f"`{p.plantilla}`" for p in sin_titulo) + "\n")

    # -- índice ------------------------------------------------------------- #
    agregar("\n## Pantallas\n")
    agregar(_tabla(
        ["Plantilla", "Título", "Rutas", "Acciones"],
        [[f"`{p.plantilla}`", p.titulo or "—", len(p.rutas), len(p.acciones)]
         for p in mapa.pantallas_reales],
    ))

    # -- detalle ------------------------------------------------------------ #
    agregar("\n## Detalle por pantalla\n")
    for pantalla in mapa.pantallas_reales:
        agregar(f"\n### `{pantalla.plantilla}`\n")
        if pantalla.extiende:
            agregar(f"Hereda de `{pantalla.extiende}`.\n")
        if pantalla.rutas:
            agregar("**Rutas:** " + ", ".join(f"`{r}`" for r in pantalla.rutas) + "\n")
        if pantalla.encabezados:
            agregar("**Encabezados:** " + " · ".join(pantalla.encabezados) + "\n")
        if pantalla.acciones:
            agregar("\n**Acciones visibles:**\n")
            for accion in pantalla.acciones:
                agregar(f"- {accion}")
            agregar("")
        if pantalla.campos:
            agregar("\n**Campos:**\n")
            agregar(_tabla(
                ["Campo", "Etiqueta", "Tipo", "Ayuda"],
                [[f"`{c.nombre}`", c.etiqueta, c.tipo, c.ayuda] for c in pantalla.campos],
            ))
        if pantalla.opciones:
            agregar("\n**Opciones de listas:**\n")
            for nombre, valores in pantalla.opciones.items():
                agregar(f"- `{nombre}`: " + " · ".join(valores))
            agregar("")
        if pantalla.columnas:
            agregar("\n**Columnas de tabla:** " + " · ".join(pantalla.columnas) + "\n")

    # -- huecos ------------------------------------------------------------- #
    agregar("\n## Rutas sin pantalla\n")
    agregar(
        "Redirecciones, descargas, endpoints JSON y acciones de formulario. Caty no las\n"
        "enseña como pantallas, pero tienen que estar en su mapa: son el resultado de\n"
        "tocar un botón.\n"
    )
    agregar(_tabla(
        ["Ruta", "Router", "Para qué"],
        [[f"`{r.clave}`", f"`{r.router}`", r.resumen]
         for r in sorted(mapa.rutas_sin_plantilla, key=lambda x: (x.router, x.path))],
    ))

    agregar("\n## Plantillas sin ruta\n")
    agregar(
        "Una pantalla sin ruta es funcionalidad a la que no se puede llegar. Puede ser\n"
        "código muerto, o una ruta que quedó sin registrar y nadie notó.\n"
    )
    if mapa.huerfanas:
        for nombre in mapa.huerfanas:
            agregar(f"- `{nombre}`")
        agregar("")
    else:
        agregar("_(ninguna)_\n")

    agregar("\n## Parciales\n")
    agregar(
        "Fragmentos de interfaz: no son destinos, pero sus campos y botones sí son\n"
        "visibles para el usuario dentro de otra pantalla. Un parcial que nadie\n"
        "referencia puede ser código muerto, o puede cargarse por JavaScript y no por\n"
        "Jinja (como `_editar_cliente_partial.html`, que se pide por `fetch`).\n"
    )
    agregar(_tabla(
        ["Parcial", "Referenciado", "Encabezados", "Acciones", "Campos"],
        [[f"`{n}`",
          "sí" if n in mapa.parciales else "por JavaScript",
          len(mapa.pantallas[n].encabezados) if n in mapa.pantallas else 0,
          len(mapa.pantallas[n].acciones) if n in mapa.pantallas else 0,
          len(mapa.pantallas[n].campos) if n in mapa.pantallas else 0]
         for n in mapa.parciales_por_nombre],
    ))

    return "\n".join(partes)


def escribir_mapa(destino: Path = DESTINO_MAPA, mapa: MapaSistema | None = None) -> Path:
    """Genera y guarda el mapa. Devuelve la ruta escrita."""
    mapa = mapa or construir_mapa()
    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_text(render_mapa(mapa), encoding="utf-8")
    return destino


def construir_conocimiento() -> str:
    """El texto completo que Caty lleva en contexto: manual + mapa del sistema.

    Es la base de la fase 2. Se arma siempre igual para que el prefijo no cambie
    entre consultas: si cambia un byte, el caché de DeepSeek se invalida y cada
    consulta pasa a costar unas cincuenta veces más. Por eso el mapa va sin fecha
    de generación.
    """
    mapa = construir_mapa()
    return (
        f"{leer_manual()}\n\n===== MAPA DEL SISTEMA =====\n\n"
        f"{render_mapa(mapa, con_fecha=False)}"
    )


# --------------------------------------------------------------------------- #
# Caché de proceso
# --------------------------------------------------------------------------- #
#
# Construir el conocimiento recorre 21 routers, 42 plantillas y 92 KB de manual.
# Eso no puede pasar en cada consulta. Se arma una vez y se reusa: además de ser
# más rápido, garantiza que el prefijo sea idéntico entre consultas, que es lo
# que sostiene el caché de DeepSeek.

_mapa: MapaSistema | None = None
_conocimiento: str | None = None
_rutas_conocidas: frozenset[str] | None = None


def mapa_cacheado() -> MapaSistema:
    global _mapa
    if _mapa is None:
        _mapa = construir_mapa()
    return _mapa


def conocimiento_cacheado() -> str:
    global _conocimiento
    if _conocimiento is None:
        _conocimiento = construir_conocimiento()
    return _conocimiento


def rutas_conocidas() -> frozenset[str]:
    """Rutas válidas de la aplicación.

    Sirve para validar la pantalla que informa el navegador: es entrada del
    usuario, y una ruta inventada no tiene por qué llegar al prompt.
    """
    global _rutas_conocidas
    if _rutas_conocidas is None:
        _rutas_conocidas = frozenset(r.path for r in mapa_cacheado().rutas)
    return _rutas_conocidas


def reiniciar_cache() -> None:
    """Descarta lo cacheado. Para los tests, y para un recargado en caliente."""
    global _mapa, _conocimiento, _rutas_conocidas, _patrones_ruta
    _mapa = _conocimiento = None
    _rutas_conocidas = None
    _patrones_ruta = None


_patrones_ruta: list[re.Pattern] | None = None


def _patron_de_ruta(plantilla: str) -> re.Pattern:
    """Convierte ``/clientes/{id}`` en algo contra lo que comparar ``/clientes/12``.

    El navegador informa la ruta que está mirando el usuario, con los valores
    reales. Compararla contra la plantilla literal nunca daría: hay que comparar
    contra el patrón.
    """
    partes = re.split(r"\{[^}]+\}", plantilla)
    return re.compile("^" + "[^/]+".join(re.escape(p) for p in partes) + "/?$")


def ruta_valida(ruta: str) -> bool:
    """¿La ruta informada por el navegador es una pantalla de esta aplicación?

    Se valida porque es entrada del usuario. Si no coincide con ninguna ruta
    conocida, se descarta: una ruta inventada no tiene por qué llegar al prompt.
    """
    global _patrones_ruta
    if not ruta or not ruta.startswith("/") or len(ruta) > 200:
        return False
    if _patrones_ruta is None:
        _patrones_ruta = [_patron_de_ruta(p) for p in sorted(rutas_conocidas())]
    return any(patron.match(ruta) for patron in _patrones_ruta)


def main() -> None:
    mapa = construir_mapa()
    destino = escribir_mapa(mapa=mapa)
    print(f"{destino}")
    print(f"  rutas:      {len(mapa.rutas)}")
    print(f"  plantillas: {len(mapa.pantallas)}")
    print(f"  sin ruta:   {len(mapa.huerfanas)}")
    print(f"  sin plantilla: {len(mapa.rutas_sin_plantilla)}")
    if mapa.routers_fallidos:
        print(f"  ILEGIBLES:  {', '.join(mapa.routers_fallidos)}")


if __name__ == "__main__":
    main()
