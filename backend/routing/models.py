from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional


ALLOWED_MODES = {"walk", "cycle", "drive", "bus", "tram", "rail", "wait"}


def _normalize_mode(mode: Optional[str]) -> str:
    raw = (mode or "").strip().lower()
    if raw == "train":
        raw = "rail"
    if raw in ALLOWED_MODES:
        return raw
    return "walk"


@dataclass
class ReliabilityMetadata:
    provider_id: str
    score: float = 0.5
    realtime: bool = False
    stale: bool = False
    warnings: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "provider_id": self.provider_id,
            "score": float(self.score),
            "realtime": bool(self.realtime),
            "stale": bool(self.stale),
            "warnings": list(self.warnings),
        }


@dataclass
class TransferWindow:
    index_from_leg: int
    index_to_leg: int
    at_stop: str
    buffer_mins: int
    minimum_required_mins: int
    feasible: bool

    def to_dict(self) -> Dict[str, Any]:
        return {
            "index_from_leg": int(self.index_from_leg),
            "index_to_leg": int(self.index_to_leg),
            "at_stop": self.at_stop,
            "buffer_mins": int(self.buffer_mins),
            "minimum_required_mins": int(self.minimum_required_mins),
            "feasible": bool(self.feasible),
        }


@dataclass
class InternalLeg:
    mode: str
    from_stop: str
    to_stop: str
    depart: str
    arrive: str
    duration_mins: int
    service: str = ""
    distance_m: Optional[int] = None
    intermediate_stops: List[Dict[str, Any]] = field(default_factory=list)
    geometry: Optional[List[List[float]]] = None
    provider_id: str = "scc"
    reliability: float = 0.5

    def __post_init__(self) -> None:
        self.mode = _normalize_mode(self.mode)
        self.duration_mins = max(0, int(self.duration_mins or 0))
        if self.distance_m is not None:
            self.distance_m = max(0, int(self.distance_m))

    def to_dict(self) -> Dict[str, Any]:
        payload: Dict[str, Any] = {
            "mode": self.mode,
            "from_stop": self.from_stop,
            "to_stop": self.to_stop,
            "depart": self.depart,
            "arrive": self.arrive,
            "duration_mins": int(self.duration_mins),
            "service": self.service,
            "intermediate_stops": list(self.intermediate_stops),
            "provider_id": self.provider_id,
            "reliability": float(self.reliability),
        }
        if self.distance_m is not None:
            payload["distance_m"] = int(self.distance_m)
        if self.geometry is not None:
            payload["geometry"] = self.geometry
        return payload


@dataclass
class InternalRoute:
    source_provider: str
    start_time: str
    end_time: str
    duration_mins: int
    changes: int
    transport: List[str]
    legs: List[InternalLeg]
    reliability: ReliabilityMetadata
    transfer_windows: List[TransferWindow] = field(default_factory=list)
    score: float = 0.0
    warnings: List[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        self.duration_mins = max(0, int(self.duration_mins or 0))
        self.changes = max(0, int(self.changes or 0))
        self.transport = [_normalize_mode(m) for m in (self.transport or [])]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "source_provider": self.source_provider,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "duration_mins": int(self.duration_mins),
            "changes": int(self.changes),
            "transport": list(self.transport),
            "legs": [l.to_dict() for l in self.legs],
            "transfer_windows": [tw.to_dict() for tw in self.transfer_windows],
            "reliability": self.reliability.to_dict(),
            "score": float(self.score),
            "warnings": list(self.warnings),
        }


@dataclass
class RoutingQuery:
    from_name: str
    to_name: str
    from_lat: float
    from_lon: float
    to_lat: float
    to_lon: float
    from_stop_code: Optional[str] = None
    to_stop_code: Optional[str] = None
    depart_time: Optional[str] = None
    sort_by: str = "soonest_arrival"
    modes: List[str] = field(default_factory=list)
    prefer_reliability: bool = False
    max_walk_meters: Optional[int] = None

    def cache_key(self, time_bucket_mins: int = 5) -> str:
        try:
            dt = datetime.fromisoformat((self.depart_time or "").replace("Z", "+00:00"))
            bucket = int((dt.hour * 60 + dt.minute) / max(1, time_bucket_mins))
        except Exception:
            bucket = -1
        modes = ",".join(sorted({_normalize_mode(m) for m in (self.modes or [])}))
        return (
            f"{self.from_name}|{self.to_name}|"
            f"{round(float(self.from_lat), 4)}|{round(float(self.from_lon), 4)}|"
            f"{round(float(self.to_lat), 4)}|{round(float(self.to_lon), 4)}|"
            f"{self.from_stop_code or ''}|{self.to_stop_code or ''}|"
            f"{self.sort_by}|{bucket}|{modes}|{int(bool(self.prefer_reliability))}|"
            f"{self.max_walk_meters or ''}"
        )
