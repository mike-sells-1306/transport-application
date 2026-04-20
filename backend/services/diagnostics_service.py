from datetime import datetime
from pathlib import Path


def _safe_bool(value):
    try:
        return bool(value)
    except Exception:
        return False


def _safe_int(value, default=0):
    try:
        return int(value)
    except Exception:
        return default


def _build_route_index_snapshot(planner, include_sensitive=False):
    db_path = ""
    has_connections = False
    try:
        store = getattr(planner, "_connection_index_store", None)
        db_path = str(getattr(store, "db_path", "")) if store else ""
        has_connections = bool(store and store.has_connections())
    except Exception:
        db_path = ""
        has_connections = False

    if include_sensitive:
        visible_path = db_path
    else:
        # Keep path utility while avoiding full host-path leakage.
        visible_path = Path(db_path).name if db_path else ""

    return {
        "route_index_db": visible_path,
        "route_index_has_connections": has_connections,
    }


def build_diagnostics_snapshot(
    *,
    app,
    stop_cache_ready,
    stop_cache_model,
    transport_service,
    include_sensitive=False,
):
    diagnostics = {
        "status": "ok",
        "snapshot_utc": datetime.utcnow().isoformat(),
        "static_data_only": _safe_bool(app.config.get("STATIC_DATA_ONLY")),
    }

    try:
        diagnostics["stop_cache_ready"] = _safe_bool(stop_cache_ready())
    except Exception:
        diagnostics["stop_cache_ready"] = False

    try:
        diagnostics["stop_cache_rows"] = _safe_int(stop_cache_model.query.count())
    except Exception:
        diagnostics["stop_cache_rows"] = 0

    planner = getattr(transport_service, "route_planner", None)
    diagnostics.update(
        _build_route_index_snapshot(
            planner,
            include_sensitive=include_sensitive,
        )
    )

    try:
        metrics = transport_service.get_route_processing_metrics()
    except Exception:
        metrics = {}

    diagnostics["route_processing_metrics"] = {
        "bus_stops_processed": _safe_int(metrics.get("bus_stops_processed", 0)),
        "train_stations_processed": _safe_int(metrics.get("train_stations_processed", 0)),
        "planner_stage": str(metrics.get("planner_stage", "unknown")),
    }
    return diagnostics
