import json

from app import app


def test_health():
    client = app.test_client()
    resp = client.get('/health')
    assert resp.status_code == 200
    data = json.loads(resp.data)
    assert data.get('status') == 'ok'


def test_api_health_includes_route_diagnostics():
    client = app.test_client()
    resp = client.get('/api/health')
    assert resp.status_code == 200
    data = json.loads(resp.data)
    assert data.get('status') == 'ok'
    assert 'static_data_only' in data
    assert 'stop_cache_ready' in data
    assert 'stop_cache_rows' in data
    assert 'route_index_db' in data
    assert 'route_index_has_connections' in data
