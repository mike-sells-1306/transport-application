"""Tests for the live transport notifications feed."""

import json
from unittest.mock import patch

from app import app, db, transport_service


def reset_database():
    app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite://"
    app.config["TESTING"] = True
    with app.app_context():
        db.drop_all()
        db.create_all()


def test_transport_notifications_include_rail_and_bus_updates():
    reset_database()
    client = app.test_client()

    fake_rail_board = {
        "station": "Lancaster",
        "crs": "LAN",
        "services": [
            {
                "std": "09:00",
                "etd": "09:12",
                "platform": "1",
                "operator": "Northern",
                "operator_code": "NT",
                "service_type": "train",
                "service_id": "svc-1",
                "origin": {"name": "Lancaster"},
                "destination": {"name": "Preston"},
                "calling_points": [
                    {"name": "Preston", "scheduled": "09:20", "estimated": "09:32"},
                ],
            }
        ],
    }

    fake_bus_services = [
        {
            "service": "Stagecoach 1",
            "operator": "Stagecoach",
            "stops": [
                {"name": "Lancaster Bus Station"},
                {"name": "Morecambe Bus Station"},
            ],
        }
    ]

    def fake_departures_cached(crs_code):
        if crs_code == "LAN":
            return fake_rail_board
        return {"services": []}

    def fake_live_departures(service_name, now_mins):
        if service_name == "Stagecoach 1":
            return [now_mins + 10, now_mins + 25], 18
        return [], None

    def fake_estimate_segment_mins(service):
        if service.get("service") == "Stagecoach 1":
            return [6, 6, 6]
        return [10]

    with patch.object(transport_service.route_planner, "_fetch_rail_departures_cached", side_effect=fake_departures_cached), \
         patch.object(transport_service.route_planner, "_live_departures_for_service", side_effect=fake_live_departures), \
         patch.object(transport_service.route_planner, "_estimate_segment_mins", side_effect=fake_estimate_segment_mins), \
         patch.object(transport_service.route_planner, "BUS_SERVICES", fake_bus_services, create=True):
        updates = transport_service.get_transport_notifications(limit=10)

    assert any(item["transportType"] == "rail" for item in updates)
    assert any(item["transportType"] == "bus" for item in updates)
    assert any(item["area"] == "Lancaster" for item in updates)


def test_transport_notifications_endpoint_returns_feed():
    reset_database()
    client = app.test_client()

    with patch.object(transport_service, "get_transport_notifications", return_value=[
        {
            "notificationID": "rail-LAN-svc-1",
            "area": "Lancaster",
            "category": "delay",
            "transportType": "rail",
            "title": "Lancaster to Preston delayed by 12 min",
            "summary": "Lancaster: Lancaster to Preston delayed by 12 min",
            "message": "Northern service 09:00 → 09:12 at Lancaster",
            "issuedAt": "2026-04-23T12:00:00Z",
            "expiresAt": "2026-04-23T14:00:00Z",
            "details": {"source": "SCC rail departures"},
            "priority": 112,
        }
    ]):
        response = client.get("/api/transport/notifications")

    assert response.status_code == 200
    payload = json.loads(response.data)
    assert "notifications" in payload
    assert payload["notifications"][0]["transportType"] == "rail"
