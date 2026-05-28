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


def test_dashboard_requires_auth(client):
    r = client.get('/', follow_redirects=False)
    assert r.status_code in (302, 303)
    assert 'login' in r.headers.get('location', '')


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
