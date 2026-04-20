from adapters.connection_index import ConnectionIndexStore
from adapters.weather_adapter import WeatherAdapter


def test_connection_index_store_crud_and_queries(tmp_path):
    db_path = tmp_path / "connection-index.sqlite3"
    store = ConnectionIndexStore(db_path)
    store.init_schema()

    assert store.has_connections() is False
    assert store.get_dataset_connections_and_stops([]) == ([], {})
    assert store.get_footpaths() == []

    store.upsert_dataset("ds-1", "2026-04-20", "Operator A")
    stop_meta = {
        "BUS_A": {"name": "Bus A", "lat": 53.7600, "lon": -2.7000, "kind": "bus"},
        "RAIL_B": {"name": "Rail B", "lat": 53.7604, "lon": -2.7004, "kind": "rail"},
        "BUS_C": {"name": "Bus C", "lat": 53.9000, "lon": -2.9000, "kind": "bus"},
    }
    connections = [
        {
            "from_ref": "BUS_A",
            "to_ref": "RAIL_B",
            "dep_raw": 100,
            "arr_raw": 120,
            "trip_id": "T1",
            "service": "S1",
            "mode": "bus",
        },
        {
            "from_ref": "RAIL_B",
            "to_ref": "BUS_C",
            "dep_raw": 200,
            "arr_raw": 260,
            "trip_id": "T2",
            "service": "S2",
            "mode": "rail",
        },
        {
            "from_ref": "",
            "to_ref": "BUS_C",
            "dep_raw": 0,
            "arr_raw": 0,
            "trip_id": "IGNORED",
            "service": "IGNORED",
            "mode": "bus",
        },
    ]
    store.replace_dataset_connections("ds-1", stop_meta, connections)
    assert store.has_connections() is True

    loaded_connections, loaded_stops = store.get_dataset_connections_and_stops(["ds-1"])
    assert len(loaded_connections) == 2
    assert {c["trip_id"] for c in loaded_connections} == {"T1", "T2"}
    assert loaded_stops["BUS_A"]["name"] == "Bus A"
    assert loaded_stops["RAIL_B"]["kind"] == "rail"

    store.rebuild_footpaths(max_walk_km=0.6, walk_speed_m_per_min=80, walk_factor=1.0)
    footpaths = store.get_footpaths()
    assert len(footpaths) >= 2
    path_pairs = {(f["from_ref"], f["to_ref"]) for f in footpaths}
    assert ("BUS_A", "RAIL_B") in path_pairs
    assert ("RAIL_B", "BUS_A") in path_pairs
    assert ("BUS_A", "BUS_C") not in path_pairs

    store.clear()
    assert store.has_connections() is False
    assert store.get_dataset_connections_and_stops(["ds-1"]) == ([], {})


def test_weather_adapter_fetch_cache_and_parse(monkeypatch):
    monkeypatch.setenv("LIVE_POLL_MIN_SECONDS", "60")
    adapter = WeatherAdapter()

    class FakeResponse:
        def __init__(self, payload):
            self._payload = payload
            self.content = b"PNGDATA"

        def raise_for_status(self):
            return None

        def json(self):
            return self._payload

    calls = {"count": 0}

    def fake_get(url, timeout):
        calls["count"] += 1
        return FakeResponse(
            {
                "weather": {
                    "coord": {"lat": 53.76, "lon": -2.7},
                    "main": {"temp": 10, "feels_like": 8, "humidity": 80, "pressure": 1010},
                    "wind": {"speed": 4.2, "deg": 250},
                    "clouds": {"all": 75},
                    "visibility": 10000,
                    "weather": [{"main": "Clouds", "description": "broken clouds", "icon": "04d"}],
                    "dt": 123,
                }
            }
        )

    monkeypatch.setattr("adapters.weather_adapter.requests.get", fake_get)

    first = adapter.fetch_weather(53.76001, -2.70002)
    second = adapter.fetch_weather(53.76002, -2.70001)
    assert calls["count"] == 1
    assert first == second

    parsed = adapter.parse_weather(first)
    assert parsed["location"] == {"latitude": 53.76, "longitude": -2.7}
    assert parsed["temperature"]["current"] == 10
    assert parsed["icon"]["icon_url"] == "/api/weather/icon/04d"

    assert adapter.get_weather_icon("04d") == b"PNGDATA"
    assert adapter.parse_weather({"error": "failed"}) == {"error": "failed"}


def test_weather_adapter_request_failure_paths(monkeypatch):
    adapter = WeatherAdapter()

    def failing_get(url, timeout):
        import requests

        raise requests.exceptions.RequestException("boom")

    monkeypatch.setattr("adapters.weather_adapter.requests.get", failing_get)

    weather = adapter.fetch_weather(54.0, -2.8)
    assert weather["error"]
    assert weather["latitude"] == 54.0
    assert weather["longitude"] == -2.8

    assert adapter.get_weather_icon("missing") is None
