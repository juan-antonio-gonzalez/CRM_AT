"""Qué pantallas ve cada usuario.

Una sola fuente
---------------
El menú lateral, los checks de la pantalla de Usuarios y el control de acceso se
arman **de esta lista**. Tener tres listas separadas garantizaba que tarde o
temprano una dijera algo distinto de la otra: un check que no coincide con el menú
esconde una pantalla que el usuario igual puede abrir escribiendo la dirección, y un
menú que no coincide con el control de acceso muestra una puerta que da a un 403.

Acá se declara cada módulo una vez: cómo se llama, en qué grupo del menú va, qué
ícono usa y **qué direcciones le pertenecen**.

Esconder el enlace no alcanza
-----------------------------
Ocultar una opción del menú no protege nada: la dirección se escribe a mano. Por eso
cada módulo declara sus rutas y el middleware las comprueba. La comprobación es por
prefijo, así que `/clientes` cubre también `/clientes/exportar-excel` y
`/editar-cliente/7`.

Una ruta puede pertenecer a más de un módulo
--------------------------------------------
Hay endpoints que sirven a varias pantallas: `/api/cliente-plantas/` lo usan el alta
de clientes y el alta de asignaciones AT. Se declara en los dos y alcanza con tener
**cualquiera** de los dos módulos para poder llamarlo. Si no, el usuario tendría una
pantalla a medias.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Modulo:
    """Una pantalla del menú, con las direcciones que le pertenecen."""

    clave: str
    etiqueta: str
    grupo: str
    ruta: str
    icono: str
    # Prefijos de dirección. `coincide()` se encarga de que `/relevamiento` no
    # alcance a `/relevamiento2`.
    rutas: tuple = ()
    # Los módulos de administración no se pueden dar a un usuario común: se
    # muestran en la pantalla de Usuarios pero deshabilitados.
    solo_admin: bool = False
    # Para la ayuda de la pantalla de Usuarios.
    ayuda: str = ""

    def cubre(self, path: str) -> bool:
        return any(coincide(path, prefijo) for prefijo in self.rutas)


def coincide(path: str, prefijo: str) -> bool:
    """¿La dirección `path` cae dentro del prefijo?

    Se compara por segmentos, no por texto: `/relevamiento` **no** tiene que
    alcanzar a `/relevamiento2`, y `/clientes` no tiene que alcanzar a
    `/clientes-viejos`. Y `/` es la única que vale sólo exacta, porque si no
    cualquier dirección quedaría adentro.
    """
    if prefijo == "/":
        return path == "/"
    limpio = prefijo.rstrip("/")
    return path == limpio or path.startswith(limpio + "/")


# ── El catálogo ─────────────────────────────────────────────────────────────
#
# El orden es el del menú lateral.

MODULOS: tuple = (
    # ── Análisis ────────────────────────────────────────────────────────────
    Modulo(
        "dashboard", "KPIs - AT", "Análisis", "/", "dashboard",
        rutas=("/",),
        ayuda="El tablero con los indicadores de visitas.",
    ),
    Modulo(
        "kpi_calidad", "KPIs Calidad AT", "Análisis", "/kpi-calidad", "ssid_chart",
        rutas=("/kpi-calidad",),
        ayuda="Los indicadores de calidad relevados en las visitas.",
    ),
    Modulo(
        "control_at", "KPIs Asignación AT", "Análisis", "/control-at", "assignment",
        rutas=("/control-at", "/kpis-at", "/eliminar-asignacion",
               "/api/customers", "/api/kpis-at",
               # El modal de alta carga las plantas del cliente elegido.
               "/api/cliente-plantas"),
        ayuda="Las visitas asignadas a cada AT, por cliente y planta.",
    ),
    Modulo(
        "historial_at", "Historial Asignación AT", "Análisis", "/historial-at",
        "history",
        rutas=("/historial-at",),
        ayuda="Los cambios de asignaciones AT a lo largo del tiempo.",
    ),

    # ── Operaciones ─────────────────────────────────────────────────────────
    Modulo(
        "clientes", "Biblioteca de Clientes", "Operaciones", "/clientes", "group",
        rutas=("/clientes", "/nuevo-cliente", "/editar-cliente",
               "/desactivar-cliente", "/reactivar-cliente", "/cliente-reporte",
               "/api/cliente-contactos", "/api/cliente-plantas",
               "/api/contact-name", "/api/plantas-lineas", "/api/linea-maquinas",
               # El alta de cliente y su modal de contactos gestionan las tablas
               # auxiliares desde adentro, sin pasar por Configuración. Se declaran
               # las cuatro operaciones y **no** el prefijo `/configuracion` a
               # secas: eso le abría la pantalla entera de Tablas Auxiliares a
               # quien sólo necesitaba el ayudante de «crear un comercial».
               "/configuracion/add", "/configuracion/list",
               "/configuracion/edit", "/configuracion/delete"),
        ayuda="Las fichas de los clientes, sus contactos y sus informes.",
    ),
    Modulo(
        "organigrama", "Organigrama", "Operaciones", "/organigrama", "account_tree",
        rutas=("/organigrama", "/api/cliente-team"),
        ayuda="El árbol de contactos de cada cliente.",
    ),
    Modulo(
        "equipos", "Equipos", "Operaciones", "/equipos", "diversity_3",
        rutas=("/equipos",),
        ayuda="Los equipos de comercial, diseñador y AT que se asignan a los clientes.",
    ),
    Modulo(
        "productos", "Biblioteca de Productos", "Operaciones", "/productos",
        "inventory_2",
        rutas=("/productos", "/nuevo-producto", "/editar-producto",
               "/eliminar-producto", "/api/productos"),
        ayuda="El catálogo de productos y sus especificaciones.",
    ),
    Modulo(
        "maquinaria", "Biblioteca de Máquinas", "Operaciones", "/maquinaria",
        "precision_manufacturing",
        rutas=("/maquinaria", "/nuevo-maquinaria", "/editar-maquinaria",
               "/eliminar-maquinaria", "/upload-foto", "/eliminar-foto",
               "/api/cliente-plantas", "/api/planta-maquinas",
               # El informe técnico de una máquina es la ficha vieja: se llega
               # desde la máquina, no desde el menú.
               "/relevamiento"),
        ayuda="Las máquinas instaladas en cada planta, con su informe técnico.",
    ),

    # ── Gestión ─────────────────────────────────────────────────────────────
    Modulo(
        "relevamiento2", "Relevamiento Técnico", "Gestión", "/relevamiento2",
        "summarize",
        rutas=("/relevamiento2", "/eliminar-relevamiento2", "/api/plantas-lineas",
               "/api/linea-maquinas", "/api/cliente-plantas",
               "/api/planta-maquinas"),
        ayuda="Los relevamientos técnicos V2.",
    ),
    Modulo(
        "visitas2", "Visitas Técnicas", "Gestión", "/visitas2", "assignment",
        rutas=("/visitas2", "/cancelar-visita2", "/eliminar-visita2"),
        ayuda="Las visitas técnicas: planificación, ejecución y su informe.",
    ),
    Modulo(
        "minutas", "Minutas", "Gestión", "/minutas", "description",
        rutas=("/minutas", "/eliminar-minuta"),
        ayuda="Las minutas de reunión con el cliente.",
    ),
    Modulo(
        "infraestructura", "Infraestructura & Logística", "Gestión",
        "/relevamiento-infraestructura", "factory",
        rutas=("/relevamiento-infraestructura", "/api/customers"),
        ayuda="Los relevamientos de infraestructura y logística.",
    ),
    Modulo(
        "seguimiento", "Seguimiento Plan", "Gestión", "/seguimiento-plan",
        "checklist_rtl",
        rutas=("/seguimiento-plan",),
        ayuda="El seguimiento de los planes de acción acordados.",
    ),
    Modulo(
        "agenda", "Agenda de Visitas", "Gestión", "/agenda", "calendar_month",
        rutas=("/agenda", "/api/agenda", "/api/visitas-agenda"),
        ayuda="El calendario de visitas programadas.",
    ),
    Modulo(
        "historial_cambios", "Historial de cambios", "Gestión",
        "/historial-cambios", "history",
        rutas=("/historial-cambios",),
        ayuda="Quién cambió qué y cuándo, en todo el sistema.",
    ),
    Modulo(
        "importar", "Importar desde Excel", "Gestión", "/importar", "cloud_upload",
        rutas=("/importar",),
        ayuda="La carga masiva de clientes y máquinas desde una planilla.",
    ),
    Modulo(
        "configuracion", "Tablas Auxiliares", "Gestión", "/configuracion", "settings",
        rutas=("/configuracion",),
        ayuda="Los catálogos que alimentan los formularios.",
    ),

    # ── Administración ──────────────────────────────────────────────────────
    Modulo(
        "papelera", "Papelera", "Administración", "/papelera", "delete_sweep",
        rutas=("/papelera",),
        solo_admin=True,
        ayuda="Los registros desactivados, para restaurarlos.",
    ),
    Modulo(
        "usuarios", "Usuarios", "Administración", "/auth/usuarios",
        "manage_accounts",
        rutas=("/auth/usuarios", "/auth/register"),
        solo_admin=True,
        ayuda="Las cuentas y qué puede ver cada una.",
    ),
)


# Direcciones que no dependen de ningún módulo.
#
# El criterio: todo lo que **no muestra datos de un módulo**. Entrar y salir, el
# perfil propio, la salud del servicio y la ayuda de Caty. `/api/historial/` entra
# acá porque es el botón «ver historial» que aparece en cualquier listado: muestra
# los cambios de la fila que el usuario ya está mirando.
# Direcciones que se abren **sin sesión**. De acá sale `main.PUBLIC_PATHS`: la
# lista vive en un solo lugar, porque tener una acá y otra allá es la forma de que
# una ruta quede pública en un lado y protegida en el otro.
#
# `/` está porque sin sesión muestra la presentación —y el robot de un filtro web
# tiene que poder leerla—; con sesión es el tablero, y ahí sí manda el módulo.
RUTAS_SIN_SESION: tuple = (
    "/",
    "/auth/login",
    "/auth/logout",
    "/health",
    "/favicon.ico",
    "/robots.txt",
    "/sitemap.xml",
)

# Direcciones que necesitan sesión pero **no** permiso de módulo: son la puerta de
# entrada, el perfil propio, la ayuda y las búsquedas que no muestran datos de un
# módulo. `/api/historial/` entra acá porque es el botón «ver historial» que
# aparece en cualquier listado: muestra los cambios de la fila que el usuario ya
# está mirando.
#
# **Son dos listas y no una**, y la diferencia importa. «Sin sesión» y «sin
# permiso» no son lo mismo: `/` se abre sin sesión —muestra la presentación— pero
# con sesión es el tablero y sí tiene módulo. Con una sola lista, marcar `/` como
# pública la dejaba además **sin permiso**, y un usuario sin el módulo Tablero
# podía abrirlo. Lo encontró la prueba de `tests/test_publico.py`.
RUTAS_SIN_PERMISO: tuple = (
    "/auth/perfil",
    "/api/historial",
    "/api/agente",
    "/buscar",
    "/search",
    "/static",
)

# Compatibilidad: lo que no necesita permiso, venga de donde venga.
RUTAS_LIBRES: tuple = RUTAS_SIN_PERMISO


def modulo_por_clave(clave: str):
    """El módulo con esa clave, o `None`."""
    for m in MODULOS:
        if m.clave == clave:
            return m
    return None


def modulos_por_clave() -> dict:
    return {m.clave: m for m in MODULOS}


def claves_validas() -> set:
    return {m.clave for m in MODULOS}


def claves_asignables() -> set:
    """Las claves que se le pueden dar a un usuario común."""
    return {m.clave for m in MODULOS if not m.solo_admin}


def modulos_de(path: str) -> list:
    """Los módulos a los que pertenece una dirección. Puede ser más de uno."""
    return [m for m in MODULOS if m.cubre(path)]


def es_libre(path: str) -> bool:
    """¿La dirección se puede abrir sin permiso de módulo?

    Ojo: `/` **no** es libre. Se abre sin sesión porque muestra la presentación,
    pero con sesión es el tablero y ahí manda el módulo.
    """
    return any(coincide(path, prefijo) for prefijo in RUTAS_SIN_PERMISO)


def sin_sesion(path: str) -> bool:
    """¿Se puede abrir sin haber entrado?"""
    return any(coincide(path, prefijo) for prefijo in RUTAS_SIN_SESION)


def sin_clasificar(rutas) -> list:
    """Las direcciones que no pertenecen a ningún módulo ni son libres.

    Existe para la prueba de cobertura: una ruta nueva que nadie clasificó queda
    accesible para todo el mundo, y eso hay que decidirlo a propósito, no por
    olvido.
    """
    return sorted(p for p in rutas
                  if not modulos_de(p) and not es_libre(p) and not sin_sesion(p))


# ── Permisos de un usuario ──────────────────────────────────────────────────

def visibles(usuario) -> set:
    """Las claves de módulo que ve un usuario.

    Tres casos:

    * **Administrador:** ve todo, siempre. No depende de la lista, así que agregar
      un módulo nuevo no lo deja afuera.
    * **Sin configurar** (`modulos` en `None`): ve todos los módulos que no son de
      administración. Es el caso de los usuarios que ya existían: se comportan como
      antes de que existieran los permisos, en vez de quedar sin nada.
    * **Configurado:** ve exactamente lo que dice su lista, sin los de
      administración (ésos no se pueden asignar).
    """
    if usuario is None:
        return set()
    if getattr(usuario, "role", None) == "admin":
        return {m.clave for m in MODULOS}

    configurados = getattr(usuario, "modulos", None)
    if configurados is None:
        return claves_asignables()

    pedidos = set(configurados)
    return pedidos & claves_asignables()


def puede_ver(usuario, path: str) -> bool:
    """¿El usuario puede abrir esa dirección?"""
    if es_libre(path):
        return True
    duenos = modulos_de(path)
    if not duenos:
        # Una ruta sin clasificar no se bloquea: bloquearla dejaría la aplicación
        # rota por un olvido. La prueba de cobertura se encarga de que no las haya.
        return True
    vistas = visibles(usuario)
    return any(m.clave in vistas for m in duenos)


def menu(usuario) -> list:
    """El menú lateral, agrupado y ya filtrado.

    Devuelve `[{'grupo': ..., 'modulos': [...]}, ...]` en el orden del catálogo.
    """
    vistas = visibles(usuario)
    grupos = []
    for m in MODULOS:
        if m.clave not in vistas:
            continue
        if not grupos or grupos[-1]["grupo"] != m.grupo:
            grupos.append({"grupo": m.grupo, "modulos": []})
        grupos[-1]["modulos"].append(m)
    return grupos


def agrupados_para_elegir(usuario_destino=None) -> list:
    """Todos los módulos agrupados, para los checks de la pantalla de Usuarios."""
    visibles_ahora = visibles(usuario_destino) if usuario_destino else set()
    grupos = []
    for m in MODULOS:
        if not grupos or grupos[-1]["grupo"] != m.grupo:
            grupos.append({"grupo": m.grupo, "modulos": []})
        grupos[-1]["modulos"].append({
            "clave": m.clave,
            "etiqueta": m.etiqueta,
            "ayuda": m.ayuda,
            "solo_admin": m.solo_admin,
            "marcado": m.clave in visibles_ahora,
        })
    return grupos
