import pytest


@pytest.mark.parametrize('path', [
    '/', '/productos', '/clientes', '/maquinaria',
    '/visitas', '/agenda', '/seguimiento-plan', '/configuracion',
    '/kpis-at',
])
def test_page_render(client, admin_cookie, path):
    r = client.get(path, headers={'Cookie': admin_cookie})
    assert r.status_code == 200, f'{path} returned {r.status_code}'


def test_new_product_form(client, admin_cookie):
    r = client.get('/nuevo-producto', headers={'Cookie': admin_cookie})
    assert r.status_code == 200


def test_new_customer_form(client, admin_cookie):
    r = client.get('/nuevo-cliente', headers={'Cookie': admin_cookie})
    assert r.status_code == 200


def test_visitas_nueva(client, admin_cookie):
    r = client.get('/visitas/nueva', headers={'Cookie': admin_cookie})
    assert r.status_code == 200


def test_search_page(client, admin_cookie):
    r = client.get('/search?q=test', headers={'Cookie': admin_cookie})
    assert r.status_code == 200
