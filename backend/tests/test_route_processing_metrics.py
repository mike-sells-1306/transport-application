import pytest

from adapters.transport_adapters import RoutePlannerAdapter
from app import app, transport_service


@pytest.fixture
def client():
    app.config["TESTING"] = True
    with app.test_client() as c:
        yield c


def test_csa_records_bus_and_train_processing_counts(monkeypatch):
    planner = RoutePlannerAdapter()
    planner._static_data_only = True

    class DummyStore:
        def has_connections(self):
            return True

        def get_dataset_connections_and_stops(self, dataset_ids):
            return (
                [
                    {
                        "from_ref": "ATCO:A",
                        "to_ref": "ATCO:B",
                        "dep_raw": 480,
                        "arr_raw": 490,
                        "dep_abs_fixed": 480,
                        "arr_abs_fixed": 490,
                        "trip_id": "trip-1",
                        "service": "Test Bus",
                        "mode": "bus",
                    }
                ],
                {
                    "ATCO:A": {"name": "Stop A", "lat": 54.0488, "lon": -2.8013, "kind": "bus"},
                    "ATCO:B": {"name": "Stop B", "lat": 54.0104, "lon": -2.7856, "kind": "bus"},
                },
            )

        def get_footpaths(self):
            return []

    planner._connection_index_store = DummyStore()
    monkeypatch.setattr(planner, "_select_bus_timetable_datasets", lambda *args, **kwargs: [])

    planner._plan_routes_csa(
        "Stop A",
        "Stop B",
        54.0488,
        -2.8013,
        54.0104,
        -2.7856,
        from_stop_code="ATCO:A",
        to_stop_code="ATCO:B",
    )

    metrics = planner.get_last_processing_metrics()
    assert metrics["bus_stops_processed"] == 2
    assert metrics["train_stations_processed"] == len(planner.STATIONS)
    assert metrics["planner_stage"] == "csa"


def test_route_processing_metrics_endpoint(client):
    transport_service.route_planner._record_processing_metrics(7, 3, "test")
    resp = client.get("/api/routes/metrics")
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["bus_stops_processed"] == 7
    assert data["train_stations_processed"] == 3
    assert data["planner_stage"] == "test"
