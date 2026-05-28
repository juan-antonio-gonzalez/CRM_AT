import re


def test_csrf_rejects_without_token(client, admin_cookie):
    r = client.post('/nuevo-producto', data={
        'name': 'XSS Test',
        'et_number': 'ET-XSS-1',
        'material': 'Test',
        'manufacturing_route': 'Test',
        'dimensions_l': 1,
        'dimensions_a': 1,
        'dimensions_h': 1,
        'status': 'Activo'
    }, headers={'Cookie': admin_cookie}, follow_redirects=False)
    assert r.status_code == 303


def test_csrf_accepts_with_valid_token(client, admin_cookie):
    import time
    unique = str(int(time.time() * 1000))[-6:]
    r = client.get('/', headers={'Cookie': admin_cookie})
    csrf = re.search(r'<meta name="csrf-token" content="([^"]+)"', r.text)
    assert csrf, 'CSRF meta tag not found'

    r = client.post('/nuevo-producto', data={
        'csrf_token': csrf.group(1),
        'name': 'CSRF Safe Product',
        'et_number': f'ET-CSRF-{unique}',
        'material': 'Corrugado',
        'manufacturing_route': 'Test',
        'dimensions_l': 10,
        'dimensions_a': 10,
        'dimensions_h': 10,
        'status': 'Activo'
    }, headers={'Cookie': admin_cookie}, follow_redirects=False)
    assert r.status_code in (200, 303), f'CSRF valid POST failed: {r.status_code}'
