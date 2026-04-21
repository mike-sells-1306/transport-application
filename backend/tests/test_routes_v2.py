import pytest

from app import app
from routing.aggregator import RouteAggregator
from routing.models import InternalLeg, InternalRoute, ReliabilityMetadata, RoutingQuery
from routing.providers.base import RoutingProvider


@pytest.fixture
def client():
    app.config["TESTING"] = True
    with app.test_client() as c:
        yield c


def test_routes_search_v2_returns_timeline_payload(client):
    resp = client.post(
        "/api/routes/search-v2",
        json={
            "from": {"name": "Lancaster Railway Station", "atcoCode": "CRS:LAN"},
            "to": {"name": "Preston Railway Station", "atcoCode": "CRS:PRE"},
            "modes": ["walk", "bus", "rail"],
            "prefer_reliability": True,
        },
    )
    assert resp.status_code == 200
    data = resp.get_json()
    assert "routes" in data
    assert isinstance(data["routes"], list)
    assert "provider_metrics" in data
    if data["routes"]:
        route = data["routes"][0]
        assert "transfer_windows" in route
        assert "reliability" in route
        assert "score" in route
        assert isinstance(route["legs"], list)


class _ProviderA(RoutingProvider):
    provider_id = "a"

    def get_routes(self, query: RoutingQuery):
        return [
            InternalRoute(
                source_provider="a",
                start_time="09:00",
                end_time="09:45",
                duration_mins=45,
                changes=0,
                transport=["bus"],
                legs=[
                    InternalLeg(
                        mode="bus",
                        from_stop=query.from_name,
                        to_stop=query.to_name,
                        depart="09:00",
                        arrive="09:45",
                        duration_mins=45,
                        service="A1",
                    )
                ],
                reliability=ReliabilityMetadata(provider_id="a", score=0.8),
            )
        ]


class _ProviderB(RoutingProvider):
    provider_id = "b"

    def get_routes(self, query: RoutingQuery):
        # same signature as provider A but less reliable; aggregator should keep best score
        return [
            InternalRoute(
                source_provider="b",
                start_time="09:00",
                end_time="09:45",
                duration_mins=45,
                changes=0,
                transport=["bus"],
                legs=[
                    InternalLeg(
                        mode="bus",
                        from_stop=query.from_name,
                        to_stop=query.to_name,
                        depart="09:00",
                        arrive="09:45",
                        duration_mins=45,
                        service="B1",
                    )
                ],
                reliability=ReliabilityMetadata(provider_id="b", score=0.5),
            )
        ]


def test_aggregator_deduplicates_by_signature_prefers_higher_score():
    agg = RouteAggregator(providers=[_ProviderA(), _ProviderB()], enable_cache=False)
    payload = agg.search(
        RoutingQuery(
            from_name="From",
            to_name="To",
            from_lat=54.0,
            from_lon=-2.8,
            to_lat=53.7,
            to_lon=-2.7,
        )
    )
    routes = payload["routes"]
    assert len(routes) == 1
    assert routes[0]["source_provider"] == "a"
