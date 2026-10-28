import re


def test_login_page(client):
    r = client.get('/auth/login')
    assert r.status_code == 200


def test_register_blocked_without_auth(client):
    r = client.get('/auth/register', follow_redirects=False)
    assert r.status_code in (302, 303)


def test_login_admin(client, seed_admin):
    r = client.post('/auth/login', data={
        'username': 'admin',
        'password': 'admin123'
    }, follow_redirects=False)
    assert r.status_code == 303
    assert 'set-cookie' in r.headers


def test_la_raiz_sin_sesion_muestra_la_presentacion(client):
    """Antes redirigía al login. Ahora muestra la presentación, y es a propósito.

    El dominio tenía **una sola** página pública —el formulario de acceso—, y un
    dominio nuevo cuya única página es un login es el perfil que los filtros web
    corporativos clasifican como sospechoso y bloquean. La presentación le da algo
    que categorizar. Ver `routers/publico.py`.

    Lo que sigue prohibido es que se filtre el tablero.
    """
    r = client.get('/', follow_redirects=False)
    assert r.status_code == 200
    assert 'AplicaciónAT' in r.text
    # El armazón de la aplicación —menú, sesión— no aparece.
    assert 'sidebarNav' not in r.text
    assert 'Cerrar sesión' not in r.text


def test_el_tablero_con_sesion_sigue_siendo_el_tablero(client, admin_cookie):
    """Con sesión, la raíz es el tablero: la presentación es sólo para el visitante."""
    r = client.get('/', cookies={'session': admin_cookie.split('=', 1)[1]})
    assert r.status_code == 200
    assert 'sidebarNav' in r.text, 'no se renderizó el armazón de la aplicación' 


def test_admin_register_page(client, admin_cookie):
    r = client.get('/auth/register', headers={'Cookie': admin_cookie})
    assert r.status_code == 200
    assert 'Crear' in r.text


def test_admin_usuarios_page(client, admin_cookie):
    r = client.get('/auth/usuarios', headers={'Cookie': admin_cookie})
    assert r.status_code == 200
    assert 'admin' in r.text


def test_profile_page(client, admin_cookie):
    r = client.get('/auth/perfil', headers={'Cookie': admin_cookie})
    assert r.status_code == 200
    assert 'admin' in r.text or 'Administrador' in r.text


def test_logout(client, admin_cookie):
    r = client.get('/auth/logout', headers={'Cookie': admin_cookie}, follow_redirects=False)
    assert r.status_code == 303


def test_csrf_meta_tag_present(client, admin_cookie):
    r = client.get('/', headers={'Cookie': admin_cookie})
    assert r.status_code == 200
    assert 'csrf-token' in r.text
