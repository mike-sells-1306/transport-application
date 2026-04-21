from __future__ import annotations

from typing import List

from routing.models import InternalRoute, RoutingQuery
from routing.providers.base import RoutingProvider


class ActiveTravelProvider(RoutingProvider):
    provider_id = "active-travel"

    def __init__(self, enabled: bool = False):
        self.enabled = bool(enabled)

    def get_routes(self, query: RoutingQuery) -> List[InternalRoute]:
        if not self.enabled:
            return []
        # Placeholder for cycle/drive API integration.
        return []
