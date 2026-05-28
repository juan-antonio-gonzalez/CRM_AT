import re


def test_product_search(client, admin_cookie):
    r = client.get('/api/productos/search?q=ET', headers={'Cookie': admin_cookie})
    assert r.status_code == 200
    data = r.json()
    assert isinstance(data, list)


def test_customer_plants(client, admin_cookie):
    r = client.get('/api/cliente-plantas/Steel%20Metrics%20S.A.', headers={'Cookie': admin_cookie})
    assert r.status_code == 200
    data = r.json()
    assert isinstance(data, list)


def test_kpis_at_page(client, admin_cookie):
    r = client.get('/kpis-at', headers={'Cookie': admin_cookie})
    assert r.status_code == 200
    assert 'KPI' in r.text or 'kpis' in r.text.lower() or 'AT' in r.text


def test_visitas_agenda_api(client, admin_cookie):
    r = client.get('/api/visitas-agenda', headers={'Cookie': admin_cookie})
    assert r.status_code == 200
    data = r.json()
    assert isinstance(data, list)


def test_create_product(client, admin_cookie):
    import time
    unique = str(int(time.time() * 1000))[-6:]
    r = client.get('/productos', headers={'Cookie': admin_cookie})
    csrf = re.search(r'name="csrf_token" value="([^"]+)"', r.text)
    token = csrf.group(1) if csrf else ''

    r = client.post('/nuevo-producto', data={
        'csrf_token': token,
        'name': 'Test Product',
        'et_number': f'ET-TEST-{unique}',
        'material': 'Corrugado',
        'manufacturing_route': 'Corte > Troquelado',
        'dimensions_l': 100,
        'dimensions_a': 200,
        'dimensions_h': 150,
        'status': 'Activo'
    }, headers={'Cookie': admin_cookie}, follow_redirects=False)
    assert r.status_code in (200, 303), f'Create product failed: {r.status_code}'
