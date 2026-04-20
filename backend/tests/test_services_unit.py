import pytest
from flask import Flask

from services import account_management
from services.data_translator import DataTranslator
from services import transport_service


@pytest.fixture
def account_client():
    app = Flask(__name__)
    app.register_blueprint(account_management.account_bp)
    app.config["TESTING"] = True

    account_management.users.clear()
    account_management.saved_routes.clear()

    with app.test_client() as client:
        yield client


def test_account_create_requires_all_fields(account_client):
    response = account_client.post("/api/account/create", json={"email": "a@example.com"})
    assert response.status_code == 400
    assert response.get_json()["error"] == "Missing fields"


def test_account_create_duplicate_returns_conflict(account_client):
    payload = {"email": "a@example.com", "password": "pw", "name": "Alice"}
    first = account_client.post("/api/account/create", json=payload)
    second = account_client.post("/api/account/create", json=payload)

    assert first.status_code == 200
    assert second.status_code == 409
    assert second.get_json()["error"] == "Account already exists"


def test_account_update_and_routes_flow(account_client):
    create_payload = {"email": "a@example.com", "password": "pw", "name": "Alice"}
    account_client.post("/api/account/create", json=create_payload)

    bad_update = account_client.post(
        "/api/account/update",
        json={"email": "a@example.com", "password": "wrong", "new_password": "newpw"},
    )
    assert bad_update.status_code == 401

    good_update = account_client.post(
        "/api/account/update",
        json={"email": "a@example.com", "password": "pw", "new_password": "newpw"},
    )
    assert good_update.status_code == 200
    assert account_management.users["a@example.com"]["password"] == "newpw"

    bad_route = account_client.post(
        "/api/account/save_route",
        json={"email": "missing@example.com", "route": {"from": "A", "to": "B"}},
    )
    assert bad_route.status_code == 401

    saved = account_client.post(
        "/api/account/save_route",
        json={"email": "a@example.com", "route": {"from": "A", "to": "B"}},
    )
    assert saved.status_code == 200
    assert saved.get_json()["routes"] == [{"from": "A", "to": "B"}]

    fetched = account_client.get("/api/account/routes?email=a@example.com")
    assert fetched.status_code == 200
    assert fetched.get_json()["routes"] == [{"from": "A", "to": "B"}]

    deleted = account_client.post(
        "/api/account/delete",
        json={"email": "a@example.com", "password": "newpw"},
    )
    assert deleted.status_code == 200
    assert "a@example.com" not in account_management.users


def test_data_translator_maps_codes_and_falls_back():
    translator = DataTranslator()

    translated = translator.translate_train_event(
        {
            "train_id": "T1",
            "train_service_code": "SVC",
            "toc_id": "88",
            "loc_stanox": "52701",
            "canx_reason_code": "YI",
            "platform": "1",
        }
    )

    assert translated == {
        "train_id": "T1",
        "train_service_code": "SVC",
        "toc": "Northern Trains",
        "location": "Lancaster",
        "reason": "Delay due to infrastructure",
        "platform": "Platform 1",
    }

    fallback = translator.translate_train_event(
        {
            "toc_id": "XX",
            "loc_stanox": "UNKNOWN",
            "canx_reason_code": "ZZ",
            "platform": "99",
        }
    )
    assert fallback["toc"] == "XX"
    assert fallback["location"] == "UNKNOWN"
    assert fallback["reason"] == "ZZ"
    assert fallback["platform"] == "99"

    assert translator.translate_location("77301") == "Manchester Piccadilly"
    assert translator.translate_location("KGX") == "London King's Cross"
    assert translator.translate_location("RAW") == "RAW"
    assert translator.translate_toc("79") == "Avanti West Coast"
    assert translator.translate_toc("NOPE") == "NOPE"
    assert translator.translate_reason("TR") == "Train Reinstatement"
    assert translator.translate_reason("NOPE") == "NOPE"


def test_transport_service_routes_weather_and_naptan_cache(monkeypatch):
    class FakeNPTG:
        def fetch_nptg(self):
            return "<xml/>"

        def parse_nptg(self, payload):
            return {"parsed": payload}

    class FakeNaPTAN:
        def __init__(self):
            self.calls = []

        def fetch_naptan(self, dataset="lancashire", full=False):
            self.calls.append((dataset, full))
            return f"<{dataset}>"

        def parse_naptan(self, xml_data):
            return {"xml": xml_data}

    class FakeRoutePlanner:
        def __init__(self):
            self.plan_calls = []

        def plan_routes(self, *args, **kwargs):
            self.plan_calls.append((args, kwargs))
            return [{"id": 1}]

        def get_last_processing_metrics(self):
            return {"bus_stops_processed": 3, "train_stations_processed": 2}

        def get_bus_timetable(self, bus_code):
            return {"bus_code": bus_code}

    class FakeBus:
        def fetch_bus_live(self, bus_code):
            return {"live": bus_code}

    class FakeRail:
        def fetch_corpus(self):
            return {"stations": []}

    class FakeRailDepartures:
        def fetch_departures(self, crs_code):
            return {"crs": crs_code}

    class FakeWeather:
        def fetch_weather(self, lat, lon):
            return {"weather": {"coord": {"lat": lat, "lon": lon}}}

        def parse_weather(self, raw):
            return {"parsed": raw}

    monkeypatch.setattr(transport_service, "NPTGAdapter", FakeNPTG)
    monkeypatch.setattr(transport_service, "NaPTANAdapter", FakeNaPTAN)
    monkeypatch.setattr(transport_service, "BusAdapter", FakeBus)
    monkeypatch.setattr(transport_service, "RailAdapter", FakeRail)
    monkeypatch.setattr(transport_service, "RailDeparturesAdapter", FakeRailDepartures)
    monkeypatch.setattr(transport_service, "RoutePlannerAdapter", FakeRoutePlanner)
    monkeypatch.setattr(transport_service, "WeatherAdapter", FakeWeather)

    service = transport_service.TransportService()

    assert service.get_gazetteer() == {"parsed": "<xml/>"}
    assert service.get_bus_timetable("1") == {"bus_code": "1"}
    assert service.get_bus_live("2") == {"live": "2"}
    assert service.get_rail_corpus() == {"stations": []}
    assert service.get_rail_departures("LAN") == {"crs": "LAN"}

    first = service.get_naptan(dataset="lancashire")
    second = service.get_naptan(dataset="lancashire")
    assert first == {"xml": "<lancashire>"}
    assert second == {"xml": "<lancashire>"}
    assert service.naptan.calls == [("lancashire", False)]

    full_data = service.get_naptan(dataset="ignored", full=True)
    assert full_data == {"xml": "<full>"}
    assert service.naptan.calls[-1] == ("full", True)

    from datetime import datetime, timedelta

    service._naptan_cache_time["lancashire"] = datetime.now() - timedelta(hours=2)
    service.get_naptan(dataset="lancashire")
    assert service.naptan.calls.count(("lancashire", False)) == 2

    routes_payload = service.get_routes(
        "A",
        "B",
        depart_time="09:00",
        from_lat=1.1,
        from_lon=2.2,
        to_lat=3.3,
        to_lon=4.4,
        from_stop_code="STOP1",
        to_stop_code="STOP2",
        sort_by="fewest_changes",
    )
    assert routes_payload == {
        "routes": [{"id": 1}],
        "metrics": {"bus_stops_processed": 3, "train_stations_processed": 2},
    }

    planned_args, planned_kwargs = service.route_planner.plan_calls[-1]
    assert planned_args == ("A", "B")
    assert planned_kwargs["from_stop_code"] == "STOP1"
    assert planned_kwargs["to_stop_code"] == "STOP2"
    assert planned_kwargs["sort_by"] == "fewest_changes"

    assert service.get_route_processing_metrics() == {
        "bus_stops_processed": 3,
        "train_stations_processed": 2,
    }
    assert service.get_weather(53.7, -2.7) == {
        "parsed": {"weather": {"coord": {"lat": 53.7, "lon": -2.7}}}
    }
