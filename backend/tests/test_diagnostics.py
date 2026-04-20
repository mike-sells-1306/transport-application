import pytest

from app import app, transport_service


@pytest.fixture
def client():
    app.config["TESTING"] = True
    with app.test_client() as c:
        yield c


def test_diagnostics_summary_contract_shape(client):
    resp = client.get("/api/diagnostics/summary")
    assert resp.status_code == 200
    data = resp.get_json()

    assert data.get("status") == "ok"
    assert "snapshot_utc" in data
    assert "static_data_only" in data
    assert "stop_cache_ready" in data
    assert "stop_cache_rows" in data
    assert "route_index_db" in data
    assert "route_index_has_connections" in data
    assert "route_processing_metrics" in data

    metrics = data["route_processing_metrics"]
    assert "bus_stops_processed" in metrics
    assert "train_stations_processed" in metrics
    assert "planner_stage" in metrics


def test_diagnostics_summary_redacts_route_index_path(client):
    resp = client.get("/api/diagnostics/summary")
    assert resp.status_code == 200
    data = resp.get_json()
    route_index_db = data.get("route_index_db", "")

    # Should expose either a basename or empty string, not a full path.
    assert route_index_db == "" or "/" not in route_index_db


def test_api_health_remains_backward_compatible_without_metrics_or_snapshot(client):
    resp = client.get("/api/health")
    assert resp.status_code == 200
    data = resp.get_json()

    assert data.get("status") == "ok"
    assert "static_data_only" in data
    assert "stop_cache_ready" in data
    assert "stop_cache_rows" in data
    assert "route_index_db" in data
    assert "route_index_has_connections" in data
    assert "route_processing_metrics" not in data
    assert "snapshot_utc" not in data


def test_diagnostics_summary_handles_partial_failures(client, monkeypatch):
    monkeypatch.setattr(
        transport_service,
        "get_route_processing_metrics",
        lambda: (_ for _ in ()).throw(RuntimeError("metrics unavailable")),
    )

    resp = client.get("/api/diagnostics/summary")
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["route_processing_metrics"]["bus_stops_processed"] == 0
    assert data["route_processing_metrics"]["train_stations_processed"] == 0
