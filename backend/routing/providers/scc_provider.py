from __future__ import annotations

from typing import List

from routing.models import InternalRoute, RoutingQuery
from routing.normalization import normalize_scc_route
from routing.providers.base import RoutingProvider


class SCCRoutingProvider(RoutingProvider):
    provider_id = "scc"

    def __init__(self, route_planner):
        self.route_planner = route_planner

    def get_routes(self, query: RoutingQuery) -> List[InternalRoute]:
        raw_routes = self.route_planner.plan_routes(
            query.from_name,
            query.to_name,
            from_lat=query.from_lat,
            from_lon=query.from_lon,
            to_lat=query.to_lat,
            to_lon=query.to_lon,
            from_stop_code=query.from_stop_code,
            to_stop_code=query.to_stop_code,
            depart_time=query.depart_time,
            sort_by=query.sort_by,
        ) or []
        return [normalize_scc_route(r, provider_id=self.provider_id) for r in raw_routes]
