"""Los permisos, aplicados de verdad sobre la aplicación.

El catálogo de módulos tiene sus pruebas en `test_permisos.py`, pero ésas miran la
lógica. Acá se comprueba lo que importa: que un usuario **no pueda abrir** una
pantalla que no tiene marcada, escribiendo la dirección a mano.

Esconder el enlace del menú no protege nada por sí solo, así que la prueba central
es la que pide una dirección prohibida y espera un 403.
"""

import pytest

import models
from security import hash_password


def _crear_usuario(db_session, username, role="user", modulos=None, activo=True):
    usuario = models.User(
        username=username,
        email=f"{username}@crm-at.com",
        hashed_password=hash_password("clave12345"),
        full_name=username.capitalize(),
        role=role,
        modulos=modulos,
        is_active=activo,
    )
    db_session.add(usuario)
    db_session.commit()
    return usuario


def _entrar(client, username, password="clave12345"):
    r = client.post("/auth/login", data={"username": username, "password": password},
                    follow_redirects=False)
    assert r.status_code == 303, f"login falló: {r.status_code}"
    return r.headers.get("set-cookie", "").split(";")[0]


# ── Lo que se ve ────────────────────────────────────────────────────────────

def test_un_usuario_sin_permiso_recibe_403(client, db_session, seed_admin):
    """La prueba central: la dirección se escribe a mano y no entra."""
    _crear_usuario(db_session, "operador", modulos=["clientes"])
    cookie = _entrar(client, "operador")

    assert client.get("/clientes", cookies={"session": cookie.split("=", 1)[1]}).status_code == 200

    r = client.get("/equipos", cookies={"session": cookie.split("=", 1)[1]})
    assert r.status_code == 403, "entró a una pantalla que no tiene marcada"


def test_el_403_dice_qué_hace_falta(client, db_session, seed_admin):
    _crear_usuario(db_session, "operador", modulos=["clientes"])
    cookie = _entrar(client, "operador")
    r = client.get("/equipos", cookies={"session": cookie.split("=", 1)[1]})

    assert "Equipos" in r.text
    assert "no tiene acceso" in r.text


def test_el_menú_no_muestra_lo_que_no_tiene(client, db_session, seed_admin):
    import re

    _crear_usuario(db_session, "operador", modulos=["clientes"])
    cookie = _entrar(client, "operador")
    html = client.get("/clientes", cookies={"session": cookie.split("=", 1)[1]}).text

    # Se mira el menú, no cualquier enlace de la página: una pantalla puede tener
    # enlaces de ayuda a otra parte.
    nav = re.search(r"<nav.*?</nav>", html, re.S)
    assert nav, "la página no tiene menú"
    enlaces = re.findall(r'href="([^"]+)"', nav.group(0))

    assert "/clientes" in enlaces
    assert "/equipos" not in enlaces, "el menú muestra una pantalla que no tiene"
    assert "/auth/usuarios" not in enlaces


def test_los_enlaces_de_ayuda_también_respetan_los_permisos(client, db_session, seed_admin):
    """El formulario de cliente ofrece «Gestionar equipos»: sin Equipos, no.

    Un enlace a una pantalla prohibida no es sólo ruido: manda al usuario a un 403.
    """
    _crear_usuario(db_session, "operador", modulos=["clientes"])
    cookie = _entrar(client, "operador")
    html = client.get("/nuevo-cliente", cookies={"session": cookie.split("=", 1)[1]}).text

    assert "Gestionar equipos" not in html
    # Y con el módulo, sí aparece.
    _crear_usuario(db_session, "encargado", modulos=["clientes", "equipos"])
    cookie2 = _entrar(client, "encargado")
    html2 = client.get("/nuevo-cliente", cookies={"session": cookie2.split("=", 1)[1]}).text
    assert "Gestionar equipos" in html2


def test_un_administrador_entra_a_todo(client, db_session, admin_cookie):
    for ruta in ("/clientes", "/equipos", "/papelera", "/auth/usuarios"):
        r = client.get(ruta, cookies={"session": admin_cookie.split("=", 1)[1]})
        assert r.status_code == 200, f"{ruta} dio {r.status_code}"


def test_un_usuario_sin_configurar_ve_lo_de_siempre(client, db_session, seed_admin):
    """Los que ya existían no quedan sin nada: `modulos` en None es «sin tocar»."""
    _crear_usuario(db_session, "veterano", modulos=None)
    cookie = _entrar(client, "veterano")

    assert client.get("/clientes", cookies={"session": cookie.split("=", 1)[1]}).status_code == 200
    assert client.get("/equipos", cookies={"session": cookie.split("=", 1)[1]}).status_code == 200
    # Pero no las de administración.
    assert client.get("/auth/usuarios",
                      cookies={"session": cookie.split("=", 1)[1]}).status_code == 403


def test_un_usuario_sin_ningún_módulo_no_ve_ninguna_pantalla(client, db_session, seed_admin):
    _crear_usuario(db_session, "nuevo", modulos=[])
    cookie = _entrar(client, "nuevo")
    r = client.get("/clientes", cookies={"session": cookie.split("=", 1)[1]})
    assert r.status_code == 403


def test_las_rutas_libres_siguen_abiertas(client, db_session, seed_admin):
    """Sin módulos, el perfil y la búsqueda tienen que seguir andando."""
    _crear_usuario(db_session, "nuevo", modulos=[])
    cookie = _entrar(client, "nuevo")
    for ruta in ("/auth/perfil", "/buscar"):
        r = client.get(ruta, cookies={"session": cookie.split("=", 1)[1]})
        assert r.status_code == 200, f"{ruta} dio {r.status_code}"


def test_desactivar_una_cuenta_la_echa(client, db_session, seed_admin):
    """Antes, desactivar a alguien no lo echaba hasta que venciera el token."""
    usuario = _crear_usuario(db_session, "operador", modulos=["clientes"])
    cookie = _entrar(client, "operador")
    assert client.get("/clientes", cookies={"session": cookie.split("=", 1)[1]}).status_code == 200

    usuario.is_active = False
    db_session.commit()

    r = client.get("/clientes", cookies={"session": cookie.split("=", 1)[1]},
                   follow_redirects=False)
    assert r.status_code == 303
    assert "logout" in r.headers.get("location", "")


# ── Editar ──────────────────────────────────────────────────────────────────

def _csrf(client, cookie):
    import re
    html = client.get("/auth/usuarios", cookies={"session": cookie.split("=", 1)[1]}).text
    m = re.search(r'name="csrf_token" value="([^"]+)"', html)
    assert m, "no se encontró el token CSRF"
    return m.group(1)


def test_la_pantalla_de_edición_muestra_los_checks(client, db_session, admin_cookie):
    objetivo = _crear_usuario(db_session, "operador", modulos=["clientes"])
    r = client.get(f"/auth/usuarios/{objetivo.id}/editar",
                   cookies={"session": admin_cookie.split("=", 1)[1]})

    assert r.status_code == 200
    assert 'name="modulos"' in r.text
    assert 'value="clientes"' in r.text
    assert 'value="equipos"' in r.text
    # Los de administración se muestran pero no se pueden marcar.
    assert 'value="usuarios"' in r.text
    assert "Sólo para administradores" in r.text
    # Y los datos de la cuenta.
    for campo in ("username", "email", "full_name", "phone", "role"):
        assert f'name="{campo}"' in r.text, campo


def test_editar_guarda_los_módulos(client, db_session, admin_cookie):
    objetivo = _crear_usuario(db_session, "operador", modulos=["clientes"])
    cookie = admin_cookie.split("=", 1)[1]

    r = client.post(f"/auth/usuarios/{objetivo.id}/editar",
                    data={"csrf_token": _csrf(client, admin_cookie),
                          "username": "operador", "email": "operador@crm-at.com",
                          "full_name": "Operador de prueba", "phone": "555",
                          "role": "user", "modulos": ["clientes", "equipos"]},
                    cookies={"session": cookie}, follow_redirects=False)
    assert r.status_code == 303

    db_session.expire_all()
    actualizado = db_session.query(models.User).filter_by(id=objetivo.id).one()
    assert set(actualizado.modulos) == {"clientes", "equipos"}
    assert actualizado.full_name == "Operador de prueba"


def test_editar_no_deja_guardar_un_módulo_de_administración(client, db_session, admin_cookie):
    """El formulario se puede armar a mano: el filtro va en el servidor."""
    objetivo = _crear_usuario(db_session, "operador", modulos=["clientes"])
    client.post(f"/auth/usuarios/{objetivo.id}/editar",
                data={"csrf_token": _csrf(client, admin_cookie),
                      "username": "operador", "email": "operador@crm-at.com",
                      "role": "user", "modulos": ["clientes", "usuarios", "papelera"]},
                cookies={"session": admin_cookie.split("=", 1)[1]},
                follow_redirects=False)

    db_session.expire_all()
    actualizado = db_session.query(models.User).filter_by(id=objetivo.id).one()
    assert set(actualizado.modulos) == {"clientes"}


def test_ve_todo_guarda_sin_configurar(client, db_session, admin_cookie):
    """«Ve todas» guarda `None`, que además incluye los módulos futuros."""
    objetivo = _crear_usuario(db_session, "operador", modulos=["clientes"])
    client.post(f"/auth/usuarios/{objetivo.id}/editar",
                data={"csrf_token": _csrf(client, admin_cookie),
                      "username": "operador", "email": "operador@crm-at.com",
                      "role": "user", "ve_todo": "1"},
                cookies={"session": admin_cookie.split("=", 1)[1]},
                follow_redirects=False)

    db_session.expire_all()
    actualizado = db_session.query(models.User).filter_by(id=objetivo.id).one()
    assert actualizado.modulos is None


def test_no_se_puede_repetir_el_nombre_de_usuario(client, db_session, admin_cookie, seed_admin):
    otro = _crear_usuario(db_session, "operador", modulos=["clientes"])
    r = client.post(f"/auth/usuarios/{otro.id}/editar",
                    data={"csrf_token": _csrf(client, admin_cookie),
                          "username": "admin", "email": "operador@crm-at.com",
                          "role": "user", "modulos": ["clientes"]},
                    cookies={"session": admin_cookie.split("=", 1)[1]},
                    follow_redirects=False)

    assert r.status_code == 200, "tendría que volver al formulario con el error"
    assert "Ya hay otro usuario con ese nombre" in r.text

    db_session.expire_all()
    assert db_session.query(models.User).filter_by(id=otro.id).one().username == "operador"


def test_un_administrador_no_se_quita_su_propio_rol(client, db_session, admin_cookie, seed_admin):
    """Si se lo sacara, no habría forma de volver a entrar a esta pantalla."""
    r = client.post(f"/auth/usuarios/{seed_admin.id}/editar",
                    data={"csrf_token": _csrf(client, admin_cookie),
                          "username": "admin", "email": "admin@crm-at.com",
                          "role": "user", "modulos": ["clientes"]},
                    cookies={"session": admin_cookie.split("=", 1)[1]},
                    follow_redirects=False)

    assert r.status_code == 200
    assert "No podés quitarte el rol de administrador" in r.text

    db_session.expire_all()
    assert db_session.query(models.User).filter_by(id=seed_admin.id).one().role == "admin"


def test_pasar_a_administrador_limpia_la_lista(client, db_session, admin_cookie):
    """Un administrador ve todo: guardarle una lista sería una restricción falsa."""
    objetivo = _crear_usuario(db_session, "operador", modulos=["clientes"])
    client.post(f"/auth/usuarios/{objetivo.id}/editar",
                data={"csrf_token": _csrf(client, admin_cookie),
                      "username": "operador", "email": "operador@crm-at.com",
                      "role": "admin", "modulos": ["clientes"]},
                cookies={"session": admin_cookie.split("=", 1)[1]},
                follow_redirects=False)

    db_session.expire_all()
    actualizado = db_session.query(models.User).filter_by(id=objetivo.id).one()
    assert actualizado.role == "admin"
    assert actualizado.modulos is None


def test_un_usuario_común_no_entra_a_editar(client, db_session, seed_admin):
    _crear_usuario(db_session, "operador", modulos=["clientes"])
    cookie = _entrar(client, "operador")
    r = client.get("/auth/usuarios/1/editar", cookies={"session": cookie.split("=", 1)[1]})
    assert r.status_code == 403


# ── La búsqueda global ──────────────────────────────────────────────────────

def test_la_búsqueda_no_muestra_lo_que_no_se_ve(client, db_session, seed_admin):
    """Un resultado que lleva a un 403 es peor que no mostrarlo."""
    import models
    from enums import CustomerStatus

    _crear_usuario(db_session, "operador", modulos=["clientes"])
    db_session.add(models.Customer(name="Buscable SA", plant="P1",
                                   status=CustomerStatus.CLIENTE.value, is_active=True))
    db_session.add(models.MeetingMinutes(
        form_data={"objetivo": "Buscable reunión"}, fecha="2026-01-01",
        is_active=True))
    db_session.commit()

    cookie = _entrar(client, "operador")
    html = client.get("/buscar?q=Buscable",
                      cookies={"session": cookie.split("=", 1)[1]}).text

    assert "Buscable SA" in html, "no ve los clientes, que sí tiene"
    assert "Buscable reunión" not in html, "ve minutas, que no tiene"


def test_la_búsqueda_de_un_administrador_ve_todo(client, db_session, admin_cookie):
    import models
    from enums import CustomerStatus

    db_session.add(models.Customer(name="Buscable SA", plant="P1",
                                   status=CustomerStatus.CLIENTE.value, is_active=True))
    db_session.add(models.MeetingMinutes(
        form_data={"objetivo": "Buscable reunión"}, fecha="2026-01-01",
        is_active=True))
    db_session.commit()

    html = client.get("/buscar?q=Buscable",
                      cookies={"session": admin_cookie.split("=", 1)[1]}).text
    assert "Buscable SA" in html
    assert "Buscable reunión" in html
