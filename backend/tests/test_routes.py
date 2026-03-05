"""
test_routes.py — Tests for the route search endpoint and supporting functions.

Covers:
    • POST /api/routes/search happy-path and validation
    • Response schema: routes include legs with walk / ride segments
    • Sorting: Fastest vs Fewest Changes
    • Mock route generation for known and unknown stop pairs
"""

import json
import pytest

from app import app, _generate_valid_mock_routes


@pytest.fixture
def client():
    app.config["TESTING"] = True
    with app.test_client() as c:
        yield c


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
    """Known pair Lancaster → Blackpool should return routes with legs."""
    resp = client.post(
        "/api/routes/search",
        json={
            "from": {"name": "Lancaster Bus Station"},
            "to": {"name": "Blackpool North Bus Station"},
        },
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
        json={
            "from": {"name": "Lancaster"},
            "to": {"name": "Blackpool"},
        },
    )
    data = json.loads(resp.data)
    route = data["routes"][0]

    for field in ("start_time", "end_time", "duration_mins", "transport", "changes", "legs"):
        assert field in route, f"Missing field: {field}"


def test_route_legs_structure(client):
    """Legs should be a list of dicts with mode, from_stop, to_stop, depart, arrive."""
    resp = client.post(
        "/api/routes/search",
        json={
            "from": {"name": "Lancaster"},
            "to": {"name": "Blackpool"},
        },
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
        json={
            "from": {"name": "Lancaster"},
            "to": {"name": "Blackpool"},
        },
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
        json={
            "from": {"name": "Lancaster"},
            "to": {"name": "Blackpool"},
        },
    )
    data = json.loads(resp.data)
    route = data["routes"][0]
    ride_legs = [l for l in route["legs"] if l["mode"] in ("bus", "train")]

    assert len(ride_legs) > 0, "Expected at least one transport leg"
    for rl in ride_legs:
        assert "service" in rl
        assert "intermediate_stops" in rl
        assert isinstance(rl["intermediate_stops"], list)


# ── Mock route generator ───────────────────────────────────────────────


def test_mock_routes_known_pair():
    """Lancaster → Blackpool should return predefined routes with legs."""
    routes = _generate_valid_mock_routes("Lancaster Bus Station", "Blackpool North")
    assert len(routes) >= 3
    for r in routes:
        assert "legs" in r
        assert len(r["legs"]) > 0


def test_mock_routes_unknown_pair():
    """An unmapped pair should still produce valid routes."""
    routes = _generate_valid_mock_routes("Ambleside Waterhead", "Cartmel Village")
    assert len(routes) >= 2
    for r in routes:
        assert "start_time" in r
        assert "end_time" in r
        assert "duration_mins" in r
        assert "legs" in r


def test_mock_routes_deterministic():
    """The same inputs should always produce the same output (seeded random)."""
    r1 = _generate_valid_mock_routes("FooStop", "BarStop")
    r2 = _generate_valid_mock_routes("FooStop", "BarStop")
    assert r1 == r2


def test_mock_routes_sorted_by_start_time():
    """Routes should be sorted by start time ascending."""
    routes = _generate_valid_mock_routes("Kendal", "Windermere")
    times = [r["start_time"] for r in routes]
    assert times == sorted(times)


def test_mock_routes_duration_consistency():
    """duration_mins should equal end_time minus start_time."""
    routes = _generate_valid_mock_routes("Preston", "Manchester")
    for r in routes:
        sh, sm = map(int, r["start_time"].split(":"))
        eh, em = map(int, r["end_time"].split(":"))
        expected = (eh * 60 + em) - (sh * 60 + sm)
        assert r["duration_mins"] == expected, (
            f"duration_mins={r['duration_mins']} but time span={expected}"
        )


# ── Sorting logic ──────────────────────────────────────────────────────


def _sort_fastest(routes):
    return sorted(routes, key=lambda r: (r["duration_mins"], r["start_time"]))


def _sort_fewest_changes(routes):
    return sorted(routes, key=lambda r: (r["changes"], r["duration_mins"]))


def test_sort_fastest():
    """Fastest sort should order by duration ascending, then start_time."""
    routes = _generate_valid_mock_routes("Lancaster", "Blackpool")
    sorted_routes = _sort_fastest(routes)
    for i in range(len(sorted_routes) - 1):
        a, b = sorted_routes[i], sorted_routes[i + 1]
        assert (a["duration_mins"], a["start_time"]) <= (
            b["duration_mins"],
            b["start_time"],
        )


def test_sort_fewest_changes():
    """Fewest-changes sort should order by changes ascending, then duration."""
    routes = _generate_valid_mock_routes("Lancaster", "Blackpool")
    sorted_routes = _sort_fewest_changes(routes)
    for i in range(len(sorted_routes) - 1):
        a, b = sorted_routes[i], sorted_routes[i + 1]
        assert (a["changes"], a["duration_mins"]) <= (
            b["changes"],
            b["duration_mins"],
        )


# ── Reverse route coverage ─────────────────────────────────────────────


def test_reverse_route_pair():
    """Predefined routes should exist for both directions of a pair."""
    forward = _generate_valid_mock_routes("Lancaster", "Preston")
    reverse = _generate_valid_mock_routes("Preston", "Lancaster")
    assert len(forward) >= 2
    assert len(reverse) >= 2
    # They should be different sets of routes
    assert forward[0]["start_time"] != reverse[0]["start_time"] or \
           forward[0]["transport"] != reverse[0]["transport"]
