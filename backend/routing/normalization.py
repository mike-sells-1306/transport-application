from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List

from routing.models import InternalLeg, InternalRoute, ReliabilityMetadata, TransferWindow


def _hhmm_to_mins(value: str) -> int:
    try:
        hh, mm = value.split(":")
        return int(hh) * 60 + int(mm)
    except Exception:
        return 0


def normalize_scc_route(raw_route: Dict[str, Any], provider_id: str = "scc") -> InternalRoute:
    legs: List[InternalLeg] = []
    for leg in raw_route.get("legs", []) or []:
        mode = str(leg.get("mode", "walk"))
        legs.append(
            InternalLeg(
                mode=mode,
                from_stop=leg.get("from_stop", ""),
                to_stop=leg.get("to_stop", ""),
                depart=leg.get("depart", "00:00"),
                arrive=leg.get("arrive", "00:00"),
                duration_mins=int(leg.get("duration_mins", 0) or 0),
                service=str(leg.get("service", "") or ""),
                distance_m=leg.get("distance_m"),
                intermediate_stops=list(leg.get("intermediate_stops", []) or []),
                provider_id=provider_id,
                reliability=0.65 if mode in {"bus", "train", "rail", "tram"} else 0.9,
            )
        )

    reliability = ReliabilityMetadata(
        provider_id=provider_id,
        score=0.7 if any(l.mode in {"bus", "rail", "tram"} for l in legs) else 0.9,
        realtime=False,
        stale=False,
        warnings=[],
    )

    route = InternalRoute(
        source_provider=provider_id,
        start_time=raw_route.get("start_time", "00:00"),
        end_time=raw_route.get("end_time", "00:00"),
        duration_mins=int(raw_route.get("duration_mins", 0) or 0),
        changes=int(raw_route.get("changes", 0) or 0),
        transport=list(raw_route.get("transport", []) or []),
        legs=legs,
        reliability=reliability,
    )
    route.transfer_windows = compute_transfer_windows(route)
    return route


def compute_transfer_windows(route: InternalRoute) -> List[TransferWindow]:
    windows: List[TransferWindow] = []
    legs = route.legs or []
    for idx in range(len(legs) - 1):
        a = legs[idx]
        b = legs[idx + 1]
        arr = _hhmm_to_mins(a.arrive)
        dep = _hhmm_to_mins(b.depart)
        buffer_mins = dep - arr
        if buffer_mins < 0:
            buffer_mins += 24 * 60
        min_required = minimum_transfer_mins(a.mode, b.mode)
        windows.append(
            TransferWindow(
                index_from_leg=idx,
                index_to_leg=idx + 1,
                at_stop=b.from_stop or a.to_stop,
                buffer_mins=int(buffer_mins),
                minimum_required_mins=int(min_required),
                feasible=buffer_mins >= min_required,
            )
        )
    return windows


def minimum_transfer_mins(from_mode: str, to_mode: str) -> int:
    fm = (from_mode or "").lower()
    tm = (to_mode or "").lower()
    if fm == tm and fm in {"bus", "rail", "tram"}:
        return 2
    if "walk" in {fm, tm}:
        return 1
    if "rail" in {fm, tm} or "train" in {fm, tm}:
        return 4
    if "tram" in {fm, tm}:
        return 3
    return 3


def route_similarity_signature(route: InternalRoute) -> str:
    # coarse signature for deduplication
    transport = ",".join(route.transport)
    legs = []
    for leg in route.legs:
        legs.append(f"{leg.mode}:{leg.from_stop}->{leg.to_stop}:{leg.depart}-{leg.arrive}")
    body = "|".join(legs[:4])
    return f"{route.start_time}|{route.end_time}|{transport}|{route.changes}|{body}"


def score_route(route: InternalRoute, prefer_reliability: bool = False) -> float:
    duration_penalty = float(route.duration_mins)
    change_penalty = float(route.changes) * 8.0
    walking_penalty = 0.0
    risky_transfer_penalty = 0.0

    for leg in route.legs:
        if leg.mode == "walk":
            walking_penalty += leg.duration_mins * 1.2
    for tw in route.transfer_windows:
        if not tw.feasible:
            risky_transfer_penalty += 20.0
        elif tw.buffer_mins <= tw.minimum_required_mins + 1:
            risky_transfer_penalty += 6.0

    reliability_bonus = float(route.reliability.score) * (12.0 if prefer_reliability else 6.0)
    raw = 1000.0 - duration_penalty - change_penalty - walking_penalty - risky_transfer_penalty + reliability_bonus
    return round(raw, 3)


def iso_utc_now() -> str:
    return datetime.utcnow().isoformat()
