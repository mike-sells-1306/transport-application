from __future__ import annotations

import logging
import time
from typing import Any, Dict, List

from routing.models import InternalRoute, RoutingQuery
from routing.normalization import compute_transfer_windows, iso_utc_now, route_similarity_signature, score_route
from routing.providers.base import RoutingProvider

logger = logging.getLogger(__name__)


class RouteAggregator:
    def __init__(
        self,
        providers: List[RoutingProvider],
        enable_cache: bool = True,
        cache_ttl_seconds: int = 90,
        cache_time_bucket_mins: int = 5,
    ):
        self.providers = list(providers or [])
        self.enable_cache = bool(enable_cache)
        self.cache_ttl_seconds = max(5, int(cache_ttl_seconds))
        self.cache_time_bucket_mins = max(1, int(cache_time_bucket_mins))
        self._cache: Dict[str, Dict[str, Any]] = {}

    def search(self, query: RoutingQuery) -> Dict[str, Any]:
        cache_key = query.cache_key(time_bucket_mins=self.cache_time_bucket_mins)
        now_ts = time.time()
        if self.enable_cache:
            cached = self._cache.get(cache_key)
            if cached and (now_ts - cached["ts"]) <= self.cache_ttl_seconds:
                return dict(cached["payload"])

        provider_results: List[InternalRoute] = []
        provider_metrics: List[Dict[str, Any]] = []
        for provider in self.providers:
            start = time.perf_counter()
            try:
                routes = provider.get_routes(query)
                latency_ms = int((time.perf_counter() - start) * 1000)
                provider_results.extend(routes or [])
                provider_metrics.append(
                    {
                        "provider_id": provider.provider_id,
                        "latency_ms": latency_ms,
                        "route_count": len(routes or []),
                        "status": "ok",
                    }
                )
            except Exception as exc:
                latency_ms = int((time.perf_counter() - start) * 1000)
                provider_metrics.append(
                    {
                        "provider_id": provider.provider_id,
                        "latency_ms": latency_ms,
                        "route_count": 0,
                        "status": "error",
                        "error": str(exc),
                    }
                )
                logger.warning("Route provider failed: %s (%s)", provider.provider_id, exc)

        merged = self._merge_routes(provider_results, prefer_reliability=query.prefer_reliability)
        payload = {
            "from": query.from_name,
            "to": query.to_name,
            "sort_by": query.sort_by,
            "timestamp": iso_utc_now(),
            "provider_metrics": provider_metrics,
            "routes": [route.to_dict() for route in merged],
        }
        if self.enable_cache:
            self._cache[cache_key] = {"ts": now_ts, "payload": dict(payload)}
        return payload

    def _merge_routes(self, routes: List[InternalRoute], prefer_reliability: bool) -> List[InternalRoute]:
        deduped: Dict[str, InternalRoute] = {}
        for route in routes:
            route.transfer_windows = compute_transfer_windows(route)
            route.score = score_route(route, prefer_reliability=prefer_reliability)
            key = route_similarity_signature(route)
            existing = deduped.get(key)
            if existing is None or route.score > existing.score:
                deduped[key] = route

        out = list(deduped.values())
        out.sort(key=lambda r: (-r.score, r.duration_mins, r.changes, r.start_time))
        return out
