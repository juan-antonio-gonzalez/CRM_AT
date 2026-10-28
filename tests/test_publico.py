"""Las páginas públicas: la presentación, `robots.txt` y `sitemap.xml`.

Por qué existen
---------------
La aplicación tenía **una sola** página pública: el formulario de login. Todo lo
demás redirigía ahí, así que lo único que se podía leer del dominio era un login.

Visto por el robot de un filtro web corporativo, un dominio nuevo cuya única página
es un formulario de acceso es el perfil que se clasifica como «sin categorizar» —y
varios filtros directamente como sospechoso, porque es la forma de las páginas de
phishing—. El resultado era que la aplicación quedaba bloqueada en las redes
corporativas sin tener nada de malo.

Estas pruebas corren **sin base de datos**: las páginas públicas no la necesitan, y
eso es parte de lo que se quiere proteger. Si alguien mete una consulta en ese
camino, se rompe acá.
"""

import json
import re

import httpx
import pytest


def pedir(ruta="/", cookie=None):
    """Una petición contra la aplicación, sin base de datos."""
    import main

    async def _correr():
        transporte = httpx.ASGITransport(app=main.app)
        cookies = {"session": cookie} if cookie else None
        async with httpx.AsyncClient(transport=transporte, base_url="http://prueba",
                                     cookies=cookies) as cliente:
            return await cliente.get(ruta)

    return __import__("asyncio").run(_correr())


# ── robots.txt ──────────────────────────────────────────────────────────────

def test_robots_responde_sin_sesion():
    r = pedir("/robots.txt")
    assert r.status_code == 200
    assert "text/plain" in r.headers.get("content-type", "")


def test_robots_permite_el_rastreo():
    """Prohibirlo dejaría al filtro sin forma de saber qué es el sitio."""
    cuerpo = pedir("/robots.txt").text
    assert "User-agent: *" in cuerpo
    assert "Allow: /" in cuerpo
    assert "Disallow: /" not in cuerpo


def test_robots_apunta_al_sitemap_y_dice_qué_es_el_sitio():
    cuerpo = pedir("/robots.txt").text
    assert "Sitemap:" in cuerpo
    assert "sitemap.xml" in cuerpo
    assert "asistencia técnica" in cuerpo


# ── sitemap.xml ─────────────────────────────────────────────────────────────

def test_sitemap_responde_sin_sesion_y_es_xml():
    r = pedir("/sitemap.xml")
    assert r.status_code == 200
    assert "xml" in r.headers.get("content-type", "")

    from xml.etree import ElementTree
    arbol = ElementTree.fromstring(r.text)   # falla si el XML está mal formado
    espacios = "{http://www.sitemaps.org/schemas/sitemap/0.9}"
    urls = [u.findtext(f"{espacios}loc") for u in arbol.findall(f"{espacios}url")]
    assert any(u.endswith("/") for u in urls), urls
    assert any(u.endswith("/auth/login") for u in urls), urls


# ── La presentación ─────────────────────────────────────────────────────────

def test_la_raiz_sin_sesion_muestra_la_presentacion():
    """Antes rebotaba al login: lo único público del dominio era el formulario."""
    r = pedir("/")
    assert r.status_code == 200, "la raíz tendría que mostrar la presentación"
    assert "AplicaciónAT" in r.text
    assert "Iniciar sesión" in r.text


def test_la_presentacion_dice_qué_es_y_de_quién_es():
    html = pedir("/").text
    assert "CRM de asistencia técnica industrial" in html
    assert "AplicaciónAT" in html
    # Sin marcas de terceros: la aplicación se presenta sola.
    assert "AplicacionAT" not in html
    assert "Ejemplo" not in html
    # Y qué se puede hacer, que es lo que le da contenido a la página.
    for modulo in ("Clientes", "Equipos de asistencia", "Máquinas",
                   "Visitas técnicas", "Relevamientos", "Minutas", "Indicadores"):
        assert modulo in html, modulo


def test_la_presentacion_tiene_los_metadatos_que_lee_un_robot():
    html = pedir("/").text
    assert '<meta name="description" content="CRM de asistencia' in html
    assert 'name="robots" content="index, follow"' in html
    assert 'property="og:title"' in html
    assert 'rel="canonical"' in html
    assert '<html lang="es"' in html


def test_la_presentacion_trae_datos_estructurados():
    """Es la forma más directa de decirle a una máquina qué es este sitio."""
    html = pedir("/").text
    m = re.search(r'<script type="application/ld\+json"[^>]*>(.*?)</script>', html, re.S)
    assert m, "no hay datos estructurados"
    datos = json.loads(m.group(1))
    assert datos["@type"] == "SoftwareApplication"
    assert datos["name"] == "AplicaciónAT"
    assert "asistencia técnica" in datos["description"]
    # No declara una organización externa: la aplicación no representa a ninguna.
    assert "publisher" not in datos


def test_la_presentacion_declara_que_es_privada():
    """Decirlo evita que se lea como un servicio abierto al público."""
    html = pedir("/").text
    assert "privada" in html.lower()
    assert "Acceso restringido" in html


def test_la_presentacion_lleva_al_login():
    html = pedir("/").text
    assert html.count('href="/auth/login"') >= 2, "faltan los accesos al login"


# ── Lo que NO cambió ────────────────────────────────────────────────────────

def test_la_raiz_con_sesion_sigue_siendo_el_tablero():
    """Hacerla pública para el visitante no puede abrir el tablero."""
    from services import permisos

    # El catálogo sigue reclamando `/` para el módulo del tablero: un usuario con
    # sesión y sin ese módulo recibe 403, no la presentación.
    duenos = [m.clave for m in permisos.modulos_de("/")]
    assert duenos == ["dashboard"]

    usuario = type("_U", (), {"role": "user", "modulos": ["clientes"]})()
    assert permisos.puede_ver(usuario, "/") is False
    admin = type("_U", (), {"role": "admin", "modulos": None})()
    assert permisos.puede_ver(admin, "/") is True


def test_las_rutas_publicas_salen_de_una_sola_lista():
    """Dos listas de lo mismo es cómo una ruta queda pública en un lado y no en el otro."""
    import main
    from services import permisos

    assert main.PUBLIC_PATHS == set(permisos.RUTAS_SIN_SESION)
    # `/` se abre sin sesión, pero **no** es libre: con sesión es el tablero.
    assert permisos.sin_sesion("/") is True
    assert permisos.es_libre("/") is False

    # Las demás públicas de verdad tampoco piden permiso.
    for ruta in ("/auth/login", "/auth/logout", "/robots.txt", "/sitemap.xml"):
        assert permisos.sin_sesion(ruta) is True, ruta
        assert permisos.es_libre(ruta) is False, ruta
