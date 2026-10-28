"""Pruebas del catálogo de módulos: qué ve cada usuario.

Lo que más importa acá es la **cobertura**: una ruta que nadie clasificó queda
abierta para todo el mundo, y eso tiene que ser una decisión, no un olvido. Por eso
hay una prueba que recorre las rutas reales de la aplicación y falla si alguna no
pertenece a ningún módulo ni está en la lista de libres.
"""

import pytest

import main
from services import permisos


# ── El catálogo ─────────────────────────────────────────────────────────────

def test_las_claves_no_se_repiten():
    claves = [m.clave for m in permisos.MODULOS]
    assert len(claves) == len(set(claves))


def test_no_hay_dos_modulos_en_la_misma_direccion():
    """Dos módulos con el mismo enlace dejarían un ítem del menú inalcanzable."""
    rutas = [m.ruta for m in permisos.MODULOS]
    assert len(rutas) == len(set(rutas)), "hay dos módulos con la misma dirección"


def test_los_modulos_de_administracion_no_se_pueden_asignar():
    """Si se pudieran, un usuario común entraría a Usuarios y se daría permisos."""
    assert "usuarios" not in permisos.claves_asignables()
    assert "papelera" not in permisos.claves_asignables()
    assert "usuarios" in permisos.claves_validas()


def test_todos_los_modulos_tienen_grupo_y_ayuda():
    for m in permisos.MODULOS:
        assert m.grupo, f"{m.clave} no tiene grupo"
        assert m.ayuda, f"{m.clave} no tiene ayuda para la pantalla de Usuarios"
        assert m.ruta.startswith("/"), f"{m.clave} no tiene dirección"
        assert m.rutas, f"{m.clave} no declara ninguna ruta"


# ── La comparación por prefijo ──────────────────────────────────────────────

def test_el_prefijo_va_por_segmentos():
    """`/relevamiento` no puede alcanzar a `/relevamiento2`."""
    assert permisos.coincide("/relevamiento2", "/relevamiento") is False
    assert permisos.coincide("/relevamiento2/nuevo", "/relevamiento") is False
    assert permisos.coincide("/relevamiento/7/reporte", "/relevamiento") is True
    assert permisos.coincide("/relevamiento", "/relevamiento") is True


def test_la_raiz_solo_coincide_exacta():
    """Si no, `/` se comería todas las direcciones de la aplicación."""
    assert permisos.coincide("/", "/") is True
    assert permisos.coincide("/clientes", "/") is False
    assert permisos.coincide("/equipos", "/") is False


def test_una_ruta_con_hija_coincide():
    assert permisos.coincide("/clientes/exportar-excel", "/clientes") is True


# ── Los tres casos de usuario ───────────────────────────────────────────────

class _Usuario:
    def __init__(self, role="user", modulos=None):
        self.role = role
        self.modulos = modulos


def test_un_administrador_ve_todo():
    vistas = permisos.visibles(_Usuario(role="admin", modulos=[]))
    assert vistas == permisos.claves_validas()


def test_un_usuario_sin_configurar_ve_lo_de_siempre():
    """Los usuarios que ya existían no pueden quedar sin nada."""
    vistas = permisos.visibles(_Usuario(modulos=None))
    assert vistas == permisos.claves_asignables()
    assert "usuarios" not in vistas


def test_un_usuario_configurado_ve_exactamente_su_lista():
    vistas = permisos.visibles(_Usuario(modulos=["clientes", "equipos"]))
    assert vistas == {"clientes", "equipos"}


def test_una_lista_vacia_no_ve_nada():
    vistas = permisos.visibles(_Usuario(modulos=[]))
    assert vistas == set()


def test_no_se_puede_colar_un_modulo_de_administracion():
    """Aunque la clave esté guardada, no se le concede."""
    vistas = permisos.visibles(_Usuario(modulos=["clientes", "usuarios"]))
    assert vistas == {"clientes"}


def test_una_clave_inventada_se_ignora():
    vistas = permisos.visibles(_Usuario(modulos=["clientes", "no_existe"]))
    assert vistas == {"clientes"}


# ── El control de acceso ────────────────────────────────────────────────────

def test_quien_tiene_el_modulo_entra():
    u = _Usuario(modulos=["clientes"])
    assert permisos.puede_ver(u, "/clientes") is True
    assert permisos.puede_ver(u, "/nuevo-cliente") is True
    assert permisos.puede_ver(u, "/editar-cliente/7") is True


def test_quien_no_lo_tiene_no_entra():
    """Esconder el enlace no alcanza: la dirección se escribe a mano."""
    u = _Usuario(modulos=["clientes"])
    assert permisos.puede_ver(u, "/equipos") is False
    assert permisos.puede_ver(u, "/papelera") is False


def test_las_rutas_libres_no_necesitan_modulo():
    u = _Usuario(modulos=[])
    for ruta in ("/auth/perfil", "/buscar", "/health", "/api/agente/chat"):
        assert permisos.puede_ver(u, ruta) is True, ruta


def test_una_direccion_compartida_alcanza_con_un_modulo():
    """`/api/cliente-plantas/` lo usan clientes y Control AT."""
    assert permisos.puede_ver(_Usuario(modulos=["clientes"]), "/api/cliente-plantas/X")
    assert permisos.puede_ver(_Usuario(modulos=["control_at"]), "/api/cliente-plantas/X")
    assert not permisos.puede_ver(_Usuario(modulos=["minutas"]), "/api/cliente-plantas/X")


def test_un_administrador_entra_a_todo():
    admin = _Usuario(role="admin", modulos=[])
    for m in permisos.MODULOS:
        assert permisos.puede_ver(admin, m.ruta) is True, m.clave


# ── El menú ─────────────────────────────────────────────────────────────────

def test_el_menu_de_un_usuario_configurado():
    grupos = permisos.menu(_Usuario(modulos=["clientes", "equipos"]))
    claves = [m.clave for g in grupos for m in g["modulos"]]
    assert claves == ["clientes", "equipos"]


def test_el_menu_de_un_administrador_tiene_los_de_administracion():
    grupos = permisos.menu(_Usuario(role="admin"))
    claves = [m.clave for g in grupos for m in g["modulos"]]
    assert "usuarios" in claves
    assert "papelera" in claves
    assert len(claves) == len(permisos.MODULOS)


def test_el_menu_no_deja_grupos_vacios():
    grupos = permisos.menu(_Usuario(modulos=["equipos"]))
    assert [g["grupo"] for g in grupos] == ["Operaciones"]


def test_el_menu_respeta_el_orden_del_catalogo():
    grupos = permisos.menu(_Usuario(role="admin"))
    en_menu = [m.clave for g in grupos for m in g["modulos"]]
    assert en_menu == [m.clave for m in permisos.MODULOS]


# ── La cobertura de rutas, que es lo que evita el agujero ───────────────────

def _rutas_de_la_app() -> list:
    """Las direcciones reales, tal como las conoce el generador del mapa."""
    from services.agente import knowledge

    return sorted({r.path for r in knowledge.mapa_cacheado().rutas})


def test_ninguna_ruta_queda_sin_clasificar():
    """Una ruta nueva que nadie clasificó queda abierta para todo el mundo.

    Si esta prueba falla, hay que decidir a propósito: o la ruta pertenece a un
    módulo, o va a `RUTAS_LIBRES` con un motivo.
    """
    huerfanas = permisos.sin_clasificar(_rutas_de_la_app())
    assert not huerfanas, (
        "estas direcciones no pertenecen a ningún módulo ni son libres, así que "
        f"quedan abiertas para todos: {huerfanas}. Clasificalas en "
        f"services/permisos.py")


def test_cada_ruta_declarada_existe():
    """Una ruta declarada que ya no existe es una promesa que nadie cumple."""
    reales = set(_rutas_de_la_app())
    declaradas = set()
    for m in permisos.MODULOS:
        declaradas.update(m.rutas)
    for prefijo in permisos.RUTAS_LIBRES:
        declaradas.add(prefijo)

    # Sólo se miran los prefijos que son una dirección completa, no los que cubren
    # una familia de rutas con parámetros.
    for declarada in sorted(declaradas):
        # `/health` se define en main.py y el mapa sólo recorre los routers;
        # `/static` y `/favicon.ico` los sirve el montaje de estáticos.
        if "{" in declarada or declarada in ("/static", "/favicon.ico", "/health"):
            continue
        coincide_algo = any(permisos.coincide(r, declarada) for r in reales)
        assert coincide_algo, (
            f"«{declarada}» está declarada en permisos.py pero no existe ninguna "
            f"ruta así")


# ── Caty ────────────────────────────────────────────────────────────────────

def test_caty_recibe_la_lista_de_lo_que_no_se_ve():
    """Va en el turno del usuario, no en el prefijo del sistema.

    El prefijo tiene que seguir siendo idéntico byte a byte para que el caché de
    contexto sirva: meter los permisos ahí lo partiría en una variante por usuario.
    """
    from services.agente import chat

    nota = chat._nota_de_permisos(["Minutas", "Papelera"])
    assert "Minutas" in nota and "Papelera" in nota
    assert "no tiene acceso" in nota


def test_caty_sin_pantallas_ocultas_no_lleva_nota():
    from services.agente import chat

    assert chat._nota_de_permisos([]) == ""
    assert chat._nota_de_permisos(None) == ""


def test_la_nota_de_permisos_no_cambia_el_prefijo_del_sistema():
    """El caché de contexto depende de que el prefijo no cambie entre consultas."""
    from services.agente import chat, knowledge

    def sistema(modulos_ocultos):
        return chat._mensajes("hola", [], "/", modulos_ocultos)[0]["content"]

    assert sistema([]) == sistema(["Minutas", "Papelera"])

    # Y la nota va en el turno del usuario. Se busca su frase, no el nombre del
    # módulo: el prefijo del sistema menciona TODAS las pantallas —es el mapa
    # completo, y por eso se puede cachear—, así que «Minutas» aparece ahí siempre.
    frase = "no tiene acceso a estas pantallas"
    mensajes = chat._mensajes("hola", [], "/", ["Minutas"])
    assert frase not in mensajes[0]["content"]
    assert frase in mensajes[-1]["content"]
    assert "Minutas" in mensajes[-1]["content"]


def test_un_modulo_no_abre_de_más():
    """Declarar un prefijo entero abre todo lo que empieza así.

    El módulo de clientes declara las cuatro operaciones de tablas auxiliares que
    usa su formulario, pero **no** `/configuracion` a secas: con el prefijo pelado,
    quien sólo necesitaba el ayudante «crear un comercial» entraba a la pantalla
    entera de Tablas Auxiliares.
    """
    cliente = _Usuario(modulos=["clientes"])
    for ruta in ("/configuracion/add/commercial", "/configuracion/list/designer",
                 "/configuracion/edit/designer/3", "/configuracion/delete/designer/3"):
        assert permisos.puede_ver(cliente, ruta) is True, ruta
    assert permisos.puede_ver(cliente, "/configuracion") is False

    # Y quien tiene el módulo, entra a todo.
    encargado = _Usuario(modulos=["configuracion"])
    assert permisos.puede_ver(encargado, "/configuracion") is True
    assert permisos.puede_ver(encargado, "/configuracion/list/designer") is True


# ── Caty tiene que conocer cada pantalla ────────────────────────────────────

def test_cada_modulo_tiene_un_tema_en_el_clasificador():
    """Caty no puede hablar de una pantalla que su clasificador no conoce.

    El clasificador elige el tema de una pregunta de una lista escrita a mano
    (`guard.TEMAS`) y esa lista se le manda al modelo en la instrucción. Si un
    módulo no está, el modelo no puede devolverlo: elige el más parecido o
    «ninguno», y la respuesta pierde la pantalla.

    Pasó con Equipos y con Historial de Asignación AT, que se agregaron después y
    nadie se acordó de la lista. Esta prueba es para que no vuelva a pasar.
    """
    from services.agente import guard

    rutas_conocidas = {dato[1] for dato in guard.TEMAS.values()}
    faltan = [f"{m.clave} ({m.ruta})" for m in permisos.MODULOS
              if m.ruta not in rutas_conocidas]
    assert not faltan, (
        f"Caty no tiene un tema para estas pantallas, así que no puede rutear una "
        f"pregunta hacia ellas: {faltan}. Agregalos a `TEMAS` en "
        f"services/agente/guard.py")


def test_todos_los_temas_apuntan_a_una_pantalla_que_existe():
    """Un tema que apunta a una ruta inexistente manda al usuario a un 404."""
    from services.agente import guard, knowledge

    reales = {r.path for r in knowledge.mapa_cacheado().rutas}
    for clave, (nombre, ruta) in guard.TEMAS.items():
        assert any(permisos.coincide(r, ruta) for r in reales), (
            f"el tema «{clave}» apunta a {ruta}, que no existe")
