from __future__ import annotations

from abc import ABC, abstractmethod
from typing import List

from routing.models import InternalRoute, RoutingQuery


class RoutingProvider(ABC):
    provider_id = "base"

    @abstractmethod
    def get_routes(self, query: RoutingQuery) -> List[InternalRoute]:
        raise NotImplementedError
