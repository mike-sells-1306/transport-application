"""
Weather API Tests

Tests for all weather-related endpoints:
- GET  /api/weather                              — Point weather lookup (public)
- POST /api/weather/route                        — Weather along a route (auth required)
- GET  /api/weather/icon/<icon_code>             — Weather icon proxy (public)
- GET  /api/account/weather-locations            — List tracked locations (auth required)
- POST /api/account/weather-locations            — Add tracked location (auth required)
- DELETE /api/account/weather-locations/<loc>    — Remove tracked location (auth required)

Run with: pytest tests/test_weather.py -v --tb=short
"""

import json
from unittest.mock import patch

import pytest

from app import app, db


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture(autouse=True)
def setup_database():
    """Reset the in-memory database before every test."""
    app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite://"
    app.config["TESTING"] = True
    app.config["AUTH_TOKEN_MAX_AGE_SECONDS"] = 86400
    with app.app_context():
        db.drop_all()
        db.create_all()
    yield
    with app.app_context():
        db.drop_all()


@pytest.fixture
def client():
    return app.test_client()


@pytest.fixture
def auth_user(client):
    """Register a user and return their token and credentials."""
    resp = client.post(
        "/api/auth/register",
        data=json.dumps({
            "email": "weather@example.com",
            "userName": "WeatherUser",
            "password": "password123",
        }),
        content_type="application/json",
    )
    data = json.loads(resp.data)
    return {
        "token": data["token"],
        "user": data["user"],
        "email": "weather@example.com",
        "password": "password123",
    }


@pytest.fixture
def second_user(client):
    resp = client.post(
        "/api/auth/register",
        data=json.dumps({
            "email": "second@example.com",
            "userName": "SecondUser",
            "password": "password456",
        }),
        content_type="application/json",
    )
    data = json.loads(resp.data)
    return {"token": data["token"], "user": data["user"]}


def _auth(token):
    return {"Authorization": f"Bearer {token}"}


# Realistic parsed weather payload mirroring WeatherAdapter.parse_weather() output.
MOCK_WEATHER_RESPONSE = {
    "location": {"latitude": 53.76, "longitude": -2.70},
    "temperature": {"current": 8.5, "feels_like": 6.2, "unit": "Celsius"},
    "atmospheric_conditions": {
        "humidity": 82,
        "humidity_unit": "%",
        "pressure": 1012,
        "pressure_unit": "hPa",
    },
    "wind": {"speed": 4.1, "speed_unit": "m/s", "direction_degrees": 245},
    "visibility": {"distance": 10000, "distance_unit": "meters"},
    "cloud_coverage": {"percentage": 75},
    "conditions": {"code": "Clouds", "description": "broken clouds"},
    "icon": {"code": "04d", "icon_url": "/api/weather/icon/04d"},
    "timestamp": 1740571200,
    "data_age_note": "Data updated every few minutes. Locations binned into areas due to API rate limits.",
}

# Minimal PNG magic bytes — enough to represent a real icon payload.
FAKE_PNG = b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR"


# =============================================================================
# 1. GET /api/weather
# =============================================================================


class TestWeatherPoint:
    """Tests for GET /api/weather?lat=...&lon=..."""

    def test_valid_coords_returns_200(self, client):
        """Valid lat/lon returns 200 with structured weather data."""
        with patch("app.transport_service.get_weather", return_value=MOCK_WEATHER_RESPONSE):
            resp = client.get("/api/weather?lat=53.76&lon=-2.70")
        assert resp.status_code == 200

    def test_response_contains_expected_keys(self, client):
        """Response contains all top-level keys from the parsed weather structure."""
        with patch("app.transport_service.get_weather", return_value=MOCK_WEATHER_RESPONSE):
            resp = client.get("/api/weather?lat=53.76&lon=-2.70")
        data = json.loads(resp.data)
        for key in (
            "location", "temperature", "atmospheric_conditions",
            "wind", "visibility", "cloud_coverage", "conditions", "icon", "timestamp",
        ):
            assert key in data, f"Missing expected key in weather response: {key}"

    def test_missing_lat_returns_400(self, client):
        """Omitting lat parameter returns 400."""
        resp = client.get("/api/weather?lon=-2.70")
        assert resp.status_code == 400
        assert "error" in json.loads(resp.data)

    def test_missing_lon_returns_400(self, client):
        """Omitting lon parameter returns 400."""
        resp = client.get("/api/weather?lat=53.76")
        assert resp.status_code == 400
        assert "error" in json.loads(resp.data)

    def test_missing_both_params_returns_400(self, client):
        """Omitting both lat and lon returns 400."""
        resp = client.get("/api/weather")
        assert resp.status_code == 400

    def test_non_numeric_lat_returns_400(self, client):
        """Non-numeric lat returns 400."""
        resp = client.get("/api/weather?lat=notanumber&lon=-2.70")
        assert resp.status_code == 400

    def test_non_numeric_lon_returns_400(self, client):
        """Non-numeric lon returns 400."""
        resp = client.get("/api/weather?lat=53.76&lon=notanumber")
        assert resp.status_code == 400

    def test_service_exception_returns_500(self, client):
        """Unhandled exception from the weather service returns 500."""
        with patch("app.transport_service.get_weather", side_effect=Exception("upstream down")):
            resp = client.get("/api/weather?lat=53.76&lon=-2.70")
        assert resp.status_code == 500
        assert "error" in json.loads(resp.data)

    def test_correct_coords_forwarded_to_service(self, client):
        """The exact float values from the query string are passed to the service."""
        with patch("app.transport_service.get_weather", return_value=MOCK_WEATHER_RESPONSE) as mock_get:
            client.get("/api/weather?lat=54.05&lon=-2.80")
        mock_get.assert_called_once_with(54.05, -2.80)

    def test_endpoint_is_public(self, client):
        """No authentication token is required."""
        with patch("app.transport_service.get_weather", return_value=MOCK_WEATHER_RESPONSE):
            resp = client.get("/api/weather?lat=53.76&lon=-2.70")
        assert resp.status_code == 200


# =============================================================================
# 2. POST /api/weather/route  (auth required)
# =============================================================================


class TestWeatherForRoute:
    """Tests for POST /api/weather/route"""

    ROUTE_POINTS = [
        {"latitude": 53.76, "longitude": -2.70, "name": "Preston"},
        {"latitude": 53.82, "longitude": -3.05, "name": "Blackpool"},
    ]

    def test_returns_200_for_valid_request(self, client, auth_user):
        """Authenticated request with valid route_points returns 200."""
        with patch("app.transport_service.get_weather", return_value=MOCK_WEATHER_RESPONSE):
            resp = client.post(
                "/api/weather/route",
                headers=_auth(auth_user["token"]),
                data=json.dumps({"route_points": self.ROUTE_POINTS}),
                content_type="application/json",
            )
        assert resp.status_code == 200

    def test_response_has_entry_per_point(self, client, auth_user):
        """Response contains one entry for every route point supplied."""
        with patch("app.transport_service.get_weather", return_value=MOCK_WEATHER_RESPONSE):
            resp = client.post(
                "/api/weather/route",
                headers=_auth(auth_user["token"]),
                data=json.dumps({"route_points": self.ROUTE_POINTS}),
                content_type="application/json",
            )
        data = json.loads(resp.data)
        assert "weather_along_route" in data
        assert len(data["weather_along_route"]) == 2

    def test_each_entry_has_location_name_and_weather(self, client, auth_user):
        """Each result entry contains location_name and weather keys."""
        with patch("app.transport_service.get_weather", return_value=MOCK_WEATHER_RESPONSE):
            resp = client.post(
                "/api/weather/route",
                headers=_auth(auth_user["token"]),
                data=json.dumps({"route_points": self.ROUTE_POINTS}),
                content_type="application/json",
            )
        data = json.loads(resp.data)
        for entry in data["weather_along_route"]:
            assert "location_name" in entry
            assert "weather" in entry

    def test_location_names_match_request(self, client, auth_user):
        """The location_name values in the response match the names sent in the request."""
        with patch("app.transport_service.get_weather", return_value=MOCK_WEATHER_RESPONSE):
            resp = client.post(
                "/api/weather/route",
                headers=_auth(auth_user["token"]),
                data=json.dumps({"route_points": self.ROUTE_POINTS}),
                content_type="application/json",
            )
        names = [e["location_name"] for e in json.loads(resp.data)["weather_along_route"]]
        assert "Preston" in names
        assert "Blackpool" in names

    def test_service_called_once_per_point(self, client, auth_user):
        """get_weather is called exactly once for each route point."""
        with patch("app.transport_service.get_weather", return_value=MOCK_WEATHER_RESPONSE) as mock_get:
            client.post(
                "/api/weather/route",
                headers=_auth(auth_user["token"]),
                data=json.dumps({"route_points": self.ROUTE_POINTS}),
                content_type="application/json",
            )
        assert mock_get.call_count == 2

    def test_no_auth_returns_401(self, client):
        """Request without a token returns 401."""
        resp = client.post(
            "/api/weather/route",
            data=json.dumps({"route_points": self.ROUTE_POINTS}),
            content_type="application/json",
        )
        assert resp.status_code == 401

    def test_missing_route_points_key_returns_400(self, client, auth_user):
        """Omitting route_points entirely returns 400."""
        resp = client.post(
            "/api/weather/route",
            headers=_auth(auth_user["token"]),
            data=json.dumps({}),
            content_type="application/json",
        )
        assert resp.status_code == 400

    def test_empty_route_points_list_returns_400(self, client, auth_user):
        """An empty route_points array returns 400."""
        resp = client.post(
            "/api/weather/route",
            headers=_auth(auth_user["token"]),
            data=json.dumps({"route_points": []}),
            content_type="application/json",
        )
        assert resp.status_code == 400

    def test_point_missing_coords_gets_error_entry(self, client, auth_user):
        """A route point without lat/lon produces an error entry rather than crashing."""
        with patch("app.transport_service.get_weather", return_value=MOCK_WEATHER_RESPONSE):
            resp = client.post(
                "/api/weather/route",
                headers=_auth(auth_user["token"]),
                data=json.dumps({"route_points": [{"name": "Nowhere"}]}),
                content_type="application/json",
            )
        assert resp.status_code == 200
        entry = json.loads(resp.data)["weather_along_route"][0]
        assert "error" in entry

    def test_point_without_name_uses_coords_as_fallback(self, client, auth_user):
        """A route point with no name field falls back to coordinate-based naming."""
        with patch("app.transport_service.get_weather", return_value=MOCK_WEATHER_RESPONSE):
            resp = client.post(
                "/api/weather/route",
                headers=_auth(auth_user["token"]),
                data=json.dumps({"route_points": [{"latitude": 53.76, "longitude": -2.70}]}),
                content_type="application/json",
            )
        entry = json.loads(resp.data)["weather_along_route"][0]
        assert "53.76" in entry["location_name"]

    def test_service_exception_returns_500(self, client, auth_user):
        """An unhandled exception from the weather service returns 500."""
        with patch("app.transport_service.get_weather", side_effect=Exception("service down")):
            resp = client.post(
                "/api/weather/route",
                headers=_auth(auth_user["token"]),
                data=json.dumps({"route_points": self.ROUTE_POINTS}),
                content_type="application/json",
            )
        assert resp.status_code == 500

    def test_response_includes_authenticated_user_id(self, client, auth_user):
        """The response body includes the authenticated user's ID."""
        with patch("app.transport_service.get_weather", return_value=MOCK_WEATHER_RESPONSE):
            resp = client.post(
                "/api/weather/route",
                headers=_auth(auth_user["token"]),
                data=json.dumps({"route_points": self.ROUTE_POINTS}),
                content_type="application/json",
            )
        data = json.loads(resp.data)
        assert "user_id" in data
        assert data["user_id"] == auth_user["user"]["id"]


# =============================================================================
# 3. GET /api/weather/icon/<icon_code>
# =============================================================================


class TestWeatherIcon:
    """Tests for GET /api/weather/icon/<icon_code>"""

    def test_valid_icon_code_returns_200(self, client):
        """A recognised icon code returns 200 with PNG bytes."""
        with patch("app.transport_service.weather.get_weather_icon", return_value=FAKE_PNG):
            resp = client.get("/api/weather/icon/04d")
        assert resp.status_code == 200
        assert resp.data == FAKE_PNG

    def test_response_content_type_is_png(self, client):
        """The Content-Type header is image/png."""
        with patch("app.transport_service.weather.get_weather_icon", return_value=FAKE_PNG):
            resp = client.get("/api/weather/icon/04d")
        assert resp.content_type == "image/png"

    def test_unknown_icon_code_returns_404(self, client):
        """When the adapter returns None, the endpoint returns 404."""
        with patch("app.transport_service.weather.get_weather_icon", return_value=None):
            resp = client.get("/api/weather/icon/99z")
        assert resp.status_code == 404
        assert "error" in json.loads(resp.data)

    def test_service_exception_returns_500(self, client):
        """An exception from the icon adapter returns 500."""
        with patch("app.transport_service.weather.get_weather_icon", side_effect=Exception("timeout")):
            resp = client.get("/api/weather/icon/04d")
        assert resp.status_code == 500

    def test_icon_code_forwarded_to_adapter(self, client):
        """The icon code from the URL path is passed directly to the adapter."""
        with patch("app.transport_service.weather.get_weather_icon", return_value=FAKE_PNG) as mock_icon:
            client.get("/api/weather/icon/01d")
        mock_icon.assert_called_once_with("01d")

    def test_endpoint_is_public(self, client):
        """No authentication token is required."""
        with patch("app.transport_service.weather.get_weather_icon", return_value=FAKE_PNG):
            resp = client.get("/api/weather/icon/01d")
        assert resp.status_code == 200


# =============================================================================
# 4. /api/account/weather-locations  (GET / POST / DELETE)
# =============================================================================


class TestWeatherLocations:
    """Tests for the user weather-location tracking endpoints."""

    # -------------------------------------------------------------------------
    # GET
    # -------------------------------------------------------------------------

    def test_new_user_has_no_locations(self, client, auth_user):
        """A freshly registered user has an empty locations list."""
        resp = client.get("/api/account/weather-locations", headers=_auth(auth_user["token"]))
        assert resp.status_code == 200
        assert json.loads(resp.data)["locations"] == []

    def test_get_returns_added_location(self, client, auth_user):
        """A location added via POST appears in the GET response."""
        client.post(
            "/api/account/weather-locations",
            headers=_auth(auth_user["token"]),
            data=json.dumps({"location": "Preston"}),
            content_type="application/json",
        )
        resp = client.get("/api/account/weather-locations", headers=_auth(auth_user["token"]))
        assert "Preston" in json.loads(resp.data)["locations"]

    def test_get_returns_all_added_locations(self, client, auth_user):
        """All added locations are returned, not just the most recent."""
        for loc in ["Preston", "Blackpool", "Lancaster"]:
            client.post(
                "/api/account/weather-locations",
                headers=_auth(auth_user["token"]),
                data=json.dumps({"location": loc}),
                content_type="application/json",
            )
        resp = client.get("/api/account/weather-locations", headers=_auth(auth_user["token"]))
        assert set(json.loads(resp.data)["locations"]) == {"Preston", "Blackpool", "Lancaster"}

    def test_get_no_auth_returns_401(self, client):
        """GET without a token returns 401."""
        resp = client.get("/api/account/weather-locations")
        assert resp.status_code == 401

    # -------------------------------------------------------------------------
    # POST
    # -------------------------------------------------------------------------

    def test_add_location_returns_201(self, client, auth_user):
        """Adding a new location returns 201 with the location in the body."""
        resp = client.post(
            "/api/account/weather-locations",
            headers=_auth(auth_user["token"]),
            data=json.dumps({"location": "Blackpool"}),
            content_type="application/json",
        )
        assert resp.status_code == 201
        assert json.loads(resp.data)["location"] == "Blackpool"

    def test_add_duplicate_location_is_idempotent(self, client, auth_user):
        """Adding the same location twice does not create a duplicate entry."""
        for _ in range(2):
            client.post(
                "/api/account/weather-locations",
                headers=_auth(auth_user["token"]),
                data=json.dumps({"location": "Blackpool"}),
                content_type="application/json",
            )
        resp = client.get("/api/account/weather-locations", headers=_auth(auth_user["token"]))
        assert json.loads(resp.data)["locations"].count("Blackpool") == 1

    def test_add_missing_location_field_returns_400(self, client, auth_user):
        """POST without a location field returns 400."""
        resp = client.post(
            "/api/account/weather-locations",
            headers=_auth(auth_user["token"]),
            data=json.dumps({}),
            content_type="application/json",
        )
        assert resp.status_code == 400
        assert "error" in json.loads(resp.data)

    def test_add_empty_string_location_returns_400(self, client, auth_user):
        """POST with an empty string location returns 400."""
        resp = client.post(
            "/api/account/weather-locations",
            headers=_auth(auth_user["token"]),
            data=json.dumps({"location": ""}),
            content_type="application/json",
        )
        assert resp.status_code == 400

    def test_add_whitespace_only_location_returns_400(self, client, auth_user):
        """POST with a whitespace-only string is treated as empty and returns 400."""
        resp = client.post(
            "/api/account/weather-locations",
            headers=_auth(auth_user["token"]),
            data=json.dumps({"location": "   "}),
            content_type="application/json",
        )
        assert resp.status_code == 400

    def test_add_location_no_auth_returns_401(self, client):
        """POST without a token returns 401."""
        resp = client.post(
            "/api/account/weather-locations",
            data=json.dumps({"location": "Preston"}),
            content_type="application/json",
        )
        assert resp.status_code == 401

    # -------------------------------------------------------------------------
    # DELETE
    # -------------------------------------------------------------------------

    def test_delete_existing_location_returns_200(self, client, auth_user):
        """Deleting a tracked location returns 200."""
        client.post(
            "/api/account/weather-locations",
            headers=_auth(auth_user["token"]),
            data=json.dumps({"location": "Blackpool"}),
            content_type="application/json",
        )
        resp = client.delete(
            "/api/account/weather-locations/Blackpool",
            headers=_auth(auth_user["token"]),
        )
        assert resp.status_code == 200

    def test_delete_removes_location_from_list(self, client, auth_user):
        """After deletion the location no longer appears in the GET response."""
        client.post(
            "/api/account/weather-locations",
            headers=_auth(auth_user["token"]),
            data=json.dumps({"location": "Blackpool"}),
            content_type="application/json",
        )
        client.delete(
            "/api/account/weather-locations/Blackpool",
            headers=_auth(auth_user["token"]),
        )
        resp = client.get("/api/account/weather-locations", headers=_auth(auth_user["token"]))
        assert "Blackpool" not in json.loads(resp.data)["locations"]

    def test_delete_nonexistent_location_returns_404(self, client, auth_user):
        """Deleting a location that was never added returns 404."""
        resp = client.delete(
            "/api/account/weather-locations/Nowhere",
            headers=_auth(auth_user["token"]),
        )
        assert resp.status_code == 404

    def test_delete_only_removes_target_location(self, client, auth_user):
        """Deleting one location leaves the others intact."""
        for loc in ["Preston", "Blackpool", "Lancaster"]:
            client.post(
                "/api/account/weather-locations",
                headers=_auth(auth_user["token"]),
                data=json.dumps({"location": loc}),
                content_type="application/json",
            )
        client.delete(
            "/api/account/weather-locations/Blackpool",
            headers=_auth(auth_user["token"]),
        )
        resp = client.get("/api/account/weather-locations", headers=_auth(auth_user["token"]))
        locs = json.loads(resp.data)["locations"]
        assert "Blackpool" not in locs
        assert "Preston" in locs
        assert "Lancaster" in locs

    def test_delete_location_no_auth_returns_401(self, client):
        """DELETE without a token returns 401."""
        resp = client.delete("/api/account/weather-locations/Preston")
        assert resp.status_code == 401

    # -------------------------------------------------------------------------
    # Cross-user isolation
    # -------------------------------------------------------------------------

    def test_locations_not_visible_to_other_users(self, client, auth_user, second_user):
        """A user's tracked locations are not visible to other users."""
        client.post(
            "/api/account/weather-locations",
            headers=_auth(auth_user["token"]),
            data=json.dumps({"location": "Preston"}),
            content_type="application/json",
        )
        resp = client.get("/api/account/weather-locations", headers=_auth(second_user["token"]))
        assert "Preston" not in json.loads(resp.data)["locations"]

    def test_users_can_track_same_location_independently(self, client, auth_user, second_user):
        """Two users may independently track the same location without conflict."""
        for token in (auth_user["token"], second_user["token"]):
            resp = client.post(
                "/api/account/weather-locations",
                headers=_auth(token),
                data=json.dumps({"location": "Blackpool"}),
                content_type="application/json",
            )
            assert resp.status_code == 201
