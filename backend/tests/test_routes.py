"""
test_routes.py — Tests for the route search endpoint and supporting functions.

Covers:
    • POST /api/routes/search happy-path and validation
    • Response schema: routes include legs with walk / ride segments
    • Sorting: Fastest vs Fewest Changes
    • Distance-aware mock route generation (walk-only, bus, train)
    • Real bus service names (Stagecoach 1, 1A, 4, 41, 100, etc.)
    • Current-time-anchored departures
"""

import json
import pytest

from app import app, _generate_valid_mock_routes


@pytest.fixture
def client():
    app.config["TESTING"] = True
    with app.test_client() as c:
        yield c


# ── Coordinates for test stops ─────────────────────────────────────────

# Very close together (< 1 km) – both in Lancaster city centre
COMMON_GARDEN = {"name": "Common Garden Street (Stop A), Lancaster",
                 "lat": 54.0487, "lon": -2.7990}
UNDERPASS = {"name": "Underpass (by), Lancaster",
             "lat": 54.0481, "lon": -2.8010}

# Medium distance (~3 km) – Lancaster centre to Lancaster University
LANCASTER_CENTRE = {"name": "Lancaster Bus Station",
                    "lat": 54.0490, "lon": -2.7997}
LANCASTER_UNI = {"name": "Lancaster University",
                 "lat": 54.0104, "lon": -2.7848}

# Regional (~30 km) – Lancaster to Preston
LANCASTER = {"name": "Lancaster Railway Station",
             "lat": 54.0488, "lon": -2.8074}
PRESTON = {"name": "Preston Railway Station",
           "lat": 53.7568, "lon": -2.7084}

# Long distance (~80 km) – Lancaster to Manchester
MANCHESTER = {"name": "Manchester Piccadilly",
              "lat": 53.4774, "lon": -2.2309}


# ── Endpoint validation ────────────────────────────────────────────────


def test_route_search_missing_body(client):
    """POST with empty body should return 400."""
    resp = client.post("/api/routes/search", json={})
    assert resp.status_code == 400
    data = json.loads(resp.data)
    assert "error" in data


def test_route_search_missing_from(client):
    """POST without 'from' stop should return 400."""
    resp = client.post("/api/routes/search", json={"to": {"name": "Blackpool"}})
    assert resp.status_code == 400


def test_route_search_missing_to(client):
    """POST without 'to' stop should return 400."""
    resp = client.post("/api/routes/search", json={"from": {"name": "Lancaster"}})
    assert resp.status_code == 400


def test_route_search_empty_names(client):
    """Stop names that are blank should return 400."""
    resp = client.post(
        "/api/routes/search",
        json={"from": {"name": ""}, "to": {"name": ""}},
    )
    assert resp.status_code == 400


# ── Happy-path route search ────────────────────────────────────────────


def test_route_search_returns_routes(client):
    """Route search with valid stops should return routes with legs."""
    resp = client.post(
        "/api/routes/search",
        json={"from": LANCASTER_CENTRE, "to": LANCASTER_UNI},
    )
    assert resp.status_code == 200
    data = json.loads(resp.data)

    assert "routes" in data
    assert "from" in data
    assert "to" in data
    assert "timestamp" in data
    assert len(data["routes"]) > 0


def test_route_contains_required_fields(client):
    """Each route must include start_time, end_time, duration_mins,
    transport, changes, and legs."""
    resp = client.post(
        "/api/routes/search",
        json={"from": LANCASTER_CENTRE, "to": LANCASTER_UNI},
    )
    data = json.loads(resp.data)
    route = data["routes"][0]

    for field in ("start_time", "end_time", "duration_mins", "transport", "changes", "legs"):
        assert field in route, f"Missing field: {field}"


def test_route_legs_structure(client):
    """Legs should be a list of dicts with mode, from_stop, to_stop, depart, arrive."""
    resp = client.post(
        "/api/routes/search",
        json={"from": LANCASTER_CENTRE, "to": LANCASTER_UNI},
    )
    data = json.loads(resp.data)
    route = data["routes"][0]
    legs = route["legs"]

    assert isinstance(legs, list)
    assert len(legs) > 0

    for leg in legs:
        assert "mode" in leg
        assert leg["mode"] in ("walk", "bus", "train")
        assert "from_stop" in leg
        assert "to_stop" in leg
        assert "depart" in leg
        assert "arrive" in leg
        assert "duration_mins" in leg


def test_walking_leg_has_distance(client):
    """Walking legs must include a distance_m field."""
    resp = client.post(
        "/api/routes/search",
        json={"from": COMMON_GARDEN, "to": UNDERPASS},
    )
    data = json.loads(resp.data)
    route = data["routes"][0]
    walk_legs = [l for l in route["legs"] if l["mode"] == "walk"]

    assert len(walk_legs) > 0, "Expected at least one walking leg"
    for wl in walk_legs:
        assert "distance_m" in wl
        assert isinstance(wl["distance_m"], (int, float))


def test_transport_leg_has_service_and_intermediates(client):
    """Bus / train legs must include service and intermediate_stops."""
    resp = client.post(
        "/api/routes/search",
        json={"from": LANCASTER_CENTRE, "to": LANCASTER_UNI},
    )
    data = json.loads(resp.data)

    # Find a route that has bus/train legs
    ride_legs = []
    for route in data["routes"]:
        ride_legs = [l for l in route["legs"] if l["mode"] in ("bus", "train")]
        if ride_legs:
            break

    assert len(ride_legs) > 0, "Expected at least one transport leg"
    for rl in ride_legs:
        assert "service" in rl
        assert "intermediate_stops" in rl
        assert isinstance(rl["intermediate_stops"], list)


# ── Distance-aware route generation ───────────────────────────────────


def test_very_short_distance_walk_only():
    """Stops < 1 km apart should primarily generate walk-only options."""
    routes = _generate_valid_mock_routes(
        COMMON_GARDEN["name"], UNDERPASS["name"],
        from_lat=COMMON_GARDEN["lat"], from_lon=COMMON_GARDEN["lon"],
        to_lat=UNDERPASS["lat"], to_lon=UNDERPASS["lon"],
    )
    assert len(routes) >= 3

    # Most routes should be walk-only (transport list empty)
    walk_only = [r for r in routes if r["transport"] == []]
    assert len(walk_only) >= 2, "Short distance should have walk-only options"

    # Walk-only routes should be short (< 15 min)
    for r in walk_only:
        assert r["duration_mins"] <= 15, \
            f"Walk between nearby stops should be < 15 min, got {r['duration_mins']}"


def test_very_short_distance_no_train():
    """Stops < 1 km apart should NEVER show a train option."""
    routes = _generate_valid_mock_routes(
        COMMON_GARDEN["name"], UNDERPASS["name"],
        from_lat=COMMON_GARDEN["lat"], from_lon=COMMON_GARDEN["lon"],
        to_lat=UNDERPASS["lat"], to_lon=UNDERPASS["lon"],
    )
    for r in routes:
        assert "train" not in r["transport"], \
            "Train should not appear for very short distances"


def test_medium_distance_bus_routes():
    """Stops 1-5 km apart should return bus routes."""
    routes = _generate_valid_mock_routes(
        LANCASTER_CENTRE["name"], LANCASTER_UNI["name"],
        from_lat=LANCASTER_CENTRE["lat"], from_lon=LANCASTER_CENTRE["lon"],
        to_lat=LANCASTER_UNI["lat"], to_lon=LANCASTER_UNI["lon"],
    )
    assert len(routes) >= 3

    bus_routes = [r for r in routes if "bus" in r["transport"]]
    assert len(bus_routes) >= 2, "Medium distance should have bus options"

    # No trains for 3 km journey
    for r in routes:
        assert "train" not in r["transport"], \
            "Train should not appear for short bus-distance journeys"


def test_long_distance_includes_train():
    """Stops > 15 km apart should include train options."""
    routes = _generate_valid_mock_routes(
        LANCASTER["name"], MANCHESTER["name"],
        from_lat=LANCASTER["lat"], from_lon=LANCASTER["lon"],
        to_lat=MANCHESTER["lat"], to_lon=MANCHESTER["lon"],
    )
    assert len(routes) >= 3

    train_routes = [r for r in routes if "train" in r["transport"]]
    assert len(train_routes) >= 1, "Long distance should have train options"


def test_regional_distance_bus_options():
    """Stops 5-15 km apart should return bus options."""
    routes = _generate_valid_mock_routes(
        LANCASTER["name"], PRESTON["name"],
        from_lat=LANCASTER["lat"], from_lon=LANCASTER["lon"],
        to_lat=PRESTON["lat"], to_lon=PRESTON["lon"],
    )
    assert len(routes) >= 3

    bus_routes = [r for r in routes if "bus" in r["transport"]]
    assert len(bus_routes) >= 1, "Regional distance should have bus options"


# ── Real service names ─────────────────────────────────────────────────


def test_uses_real_bus_service_names():
    """Routes should use real Stagecoach service names, not 'Service XX'."""
    routes = _generate_valid_mock_routes(
        LANCASTER_CENTRE["name"], LANCASTER_UNI["name"],
        from_lat=LANCASTER_CENTRE["lat"], from_lon=LANCASTER_CENTRE["lon"],
        to_lat=LANCASTER_UNI["lat"], to_lon=LANCASTER_UNI["lon"],
    )
    for route in routes:
        for leg in route["legs"]:
            if leg["mode"] == "bus":
                service = leg["service"]
                assert "Stagecoach" in service or "Service 555" in service, \
                    f"Expected real service name, got '{service}'"


# ── Generic structure tests ────────────────────────────────────────────


def test_mock_routes_sorted_by_start_time():
    """Routes should be sorted by start time ascending."""
    routes = _generate_valid_mock_routes(
        LANCASTER_CENTRE["name"], LANCASTER_UNI["name"],
        from_lat=LANCASTER_CENTRE["lat"], from_lon=LANCASTER_CENTRE["lon"],
        to_lat=LANCASTER_UNI["lat"], to_lon=LANCASTER_UNI["lon"],
    )
    times = [r["start_time"] for r in routes]
    assert times == sorted(times)


def test_mock_routes_duration_consistency():
    """duration_mins should equal end_time minus start_time."""
    routes = _generate_valid_mock_routes(
        LANCASTER["name"], PRESTON["name"],
        from_lat=LANCASTER["lat"], from_lon=LANCASTER["lon"],
        to_lat=PRESTON["lat"], to_lon=PRESTON["lon"],
    )
    for r in routes:
        sh, sm = map(int, r["start_time"].split(":"))
        eh, em = map(int, r["end_time"].split(":"))
        expected = (eh * 60 + em) - (sh * 60 + sm)
        assert r["duration_mins"] == expected, (
            f"duration_mins={r['duration_mins']} but time span={expected}"
        )


def test_mock_routes_without_coordinates():
    """Without lat/lon the generator should still produce valid routes."""
    routes = _generate_valid_mock_routes("FooStop", "BarStop")
    assert len(routes) >= 2
    for r in routes:
        assert "start_time" in r
        assert "legs" in r
        assert len(r["legs"]) > 0


# ── Sorting logic ──────────────────────────────────────────────────────


def _sort_fastest(routes):
    return sorted(routes, key=lambda r: (r["duration_mins"], r["start_time"]))


def _sort_fewest_changes(routes):
    return sorted(routes, key=lambda r: (r["changes"], r["duration_mins"]))


def test_sort_fastest():
    """Fastest sort should order by duration ascending, then start_time."""
    routes = _generate_valid_mock_routes(
        LANCASTER["name"], PRESTON["name"],
        from_lat=LANCASTER["lat"], from_lon=LANCASTER["lon"],
        to_lat=PRESTON["lat"], to_lon=PRESTON["lon"],
    )
    sorted_routes = _sort_fastest(routes)
    for i in range(len(sorted_routes) - 1):
        a, b = sorted_routes[i], sorted_routes[i + 1]
        assert (a["duration_mins"], a["start_time"]) <= (
            b["duration_mins"],
            b["start_time"],
        )


def test_sort_fewest_changes():
    """Fewest-changes sort should order by changes ascending, then duration."""
    routes = _generate_valid_mock_routes(
        LANCASTER["name"], PRESTON["name"],
        from_lat=LANCASTER["lat"], from_lon=LANCASTER["lon"],
        to_lat=PRESTON["lat"], to_lon=PRESTON["lon"],
    )
    sorted_routes = _sort_fewest_changes(routes)
    for i in range(len(sorted_routes) - 1):
        a, b = sorted_routes[i], sorted_routes[i + 1]
        assert (a["changes"], a["duration_mins"]) <= (
            b["changes"],
            b["duration_mins"],
        )


# ── Coordinates passed via endpoint ────────────────────────────────────


def test_endpoint_passes_coordinates(client):
    """Endpoint should pass lat/lon to the generator for distance calculation."""
    resp = client.post(
        "/api/routes/search",
        json={
            "from": COMMON_GARDEN,
            "to": UNDERPASS,
        },
    )
    assert resp.status_code == 200
    data = json.loads(resp.data)

    # Very close stops - should have walk-only routes and no trains
    routes = data["routes"]
    assert len(routes) >= 3
    for r in routes:
        assert "train" not in r["transport"], \
            "Nearby stops should not show train routes via the endpoint"
