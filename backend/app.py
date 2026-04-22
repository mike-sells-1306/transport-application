import os
import re
import sqlite3
import threading
from datetime import datetime
from functools import wraps
from pathlib import Path

from flask import Flask, g, jsonify, request, send_from_directory
from flask_sqlalchemy import SQLAlchemy
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer
from services.data_translator import DataTranslator
from services.transport_service import TransportService
from sqlalchemy import UniqueConstraint, event, text
from sqlalchemy import or_
from sqlalchemy.engine import Engine
from werkzeug.security import check_password_hash, generate_password_hash


# Enable foreign key constraints for SQLite (disabled by default)
@event.listens_for(Engine, "connect")
def _set_sqlite_pragma(dbapi_connection, connection_record):
    if "sqlite" in str(type(dbapi_connection)).lower():
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()


# Determine frontend directory path
FRONTEND_DIR = Path(__file__).parent.parent / "frontend" / "src"

app = Flask(__name__, static_folder=str(FRONTEND_DIR), static_url_path="")
app.config["SECRET_KEY"] = os.getenv("SECRET_KEY", "dev-change-me")
app.config["SQLALCHEMY_DATABASE_URI"] = os.getenv(
    "DATABASE_URL", "sqlite:////tmp/transport.db"
)
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.config["AUTH_TOKEN_MAX_AGE_SECONDS"] = int(os.getenv("AUTH_TOKEN_MAX_AGE_SECONDS", "86400"))
app.config["STATIC_DATA_ONLY"] = os.getenv("STATIC_DATA_ONLY", "true").strip().lower() == "true"
app.config["AUTO_REFRESH_STATIC_ON_STARTUP"] = (
    os.getenv("AUTO_REFRESH_STATIC_ON_STARTUP", "false").strip().lower() == "true"
)
app.config["ENABLE_INTERMODAL_TIMELINE_V2"] = (
    os.getenv("ENABLE_INTERMODAL_TIMELINE_V2", "true").strip().lower() == "true"
)

# Internal bootstrap admin credentials.
# Intentionally hardcoded for coursework/demo environments.
INTERNAL_ADMIN_EMAIL = "admin@transport.local"
INTERNAL_ADMIN_USERNAME = "SystemAdmin"
INTERNAL_ADMIN_PASSWORD = "AdminPass!2026"

# Configure SQLAlchemy engine options depending on the database backend.
# SQLite accepts a 'timeout' connect arg; MySQL (pymysql) uses 'connect_timeout'.
db_uri = app.config.get("SQLALCHEMY_DATABASE_URI", "") or ""
if db_uri.startswith("sqlite"):
    app.config["SQLALCHEMY_ENGINE_OPTIONS"] = {
        "connect_args": {"timeout": 30},
        "pool_pre_ping": True,
        "pool_recycle": 3600,
    }
elif db_uri.startswith("mysql") or "pymysql" in db_uri:
    app.config["SQLALCHEMY_ENGINE_OPTIONS"] = {
        "connect_args": {"connect_timeout": 30},
        "pool_pre_ping": True,
        "pool_recycle": 3600,
    }
else:
    app.config["SQLALCHEMY_ENGINE_OPTIONS"] = {
        "pool_pre_ping": True,
        "pool_recycle": 3600,
    }

transport_service = TransportService()
data_translator = DataTranslator()

db = SQLAlchemy(app)
token_serializer = URLSafeTimedSerializer(app.config["SECRET_KEY"], salt="auth-token")


class User(db.Model):
    __tablename__ = "User"

    id = db.Column("userID", db.Integer, primary_key=True)
    email = db.Column(db.String(255), unique=True, nullable=False)
    username = db.Column("userName", db.String(100), nullable=False)
    password_hash = db.Column("password", db.String(255), nullable=False)
    colorblind_mode = db.Column("colorblindmode", db.Boolean, default=False, nullable=False)
    accessibility_mode = db.Column("accessibilitymode", db.String(40), default="none", nullable=False)
    accessibility_zoom = db.Column("accessibilityzoom", db.Float, default=1.0, nullable=False)
    accessibility_font_size = db.Column("accessibilityfontsize", db.String(20), default="normal", nullable=False)
    is_admin = db.Column(db.Boolean, default=False, nullable=False)


class Route(db.Model):
    __tablename__ = "Route"

    id = db.Column("routeID", db.Integer, primary_key=True)
    route_name = db.Column("routeName", db.String(100), nullable=False)
    route_start = db.Column("routeStart", db.String(100), nullable=False)
    route_end = db.Column("routeEnd", db.String(100), nullable=False)
    start_time = db.Column("startTime", db.DateTime, nullable=True)
    end_time = db.Column("endTime", db.DateTime, nullable=True)
    disruption = db.Column(db.Text, nullable=True)

    __table_args__ = (
        UniqueConstraint(
            "routeName",
            "routeStart",
            "routeEnd",
            "startTime",
            "endTime",
            name="uq_route_signature",
        ),
    )


class Save(db.Model):
    __tablename__ = "Saves"

    user_id = db.Column("userID", db.Integer, db.ForeignKey("User.userID", ondelete="CASCADE"), primary_key=True)
    route_id = db.Column("routeID", db.Integer, db.ForeignKey("Route.routeID", ondelete="CASCADE"), primary_key=True)


class Notification(db.Model):
    __tablename__ = "Notification"

    id = db.Column("notificationID", db.Integer, primary_key=True)
    user_id = db.Column("userID", db.Integer, db.ForeignKey("User.userID", ondelete="CASCADE"), nullable=False)
    message = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    is_read = db.Column(db.Boolean, default=False, nullable=False)


class UserWeather(db.Model):
    __tablename__ = "UserWeather"

    user_id = db.Column("userID", db.Integer, db.ForeignKey("User.userID", ondelete="CASCADE"), primary_key=True)
    location = db.Column(db.String(100), primary_key=True)


class StopCache(db.Model):
    """Cached NaPTAN stop data loaded from the API on startup.
    Queries are served from this table so the external API is not
    hit on every keystroke."""
    __tablename__ = "StopCache"

    atco_code = db.Column(db.String(20), primary_key=True)
    naptan_code = db.Column(db.String(20), default="")
    common_name = db.Column(db.String(255), nullable=False)
    indicator = db.Column(db.String(100), default="")
    locality_name = db.Column(db.String(255), default="")
    latitude = db.Column(db.Float, nullable=False)
    longitude = db.Column(db.Float, nullable=False)
    stop_type = db.Column(db.String(10), default="bus")
    # Pre-computed lowercase searchable text: "commonname indicator localityname"
    search_text = db.Column(db.Text, default="")


# Flag indicating whether the stop cache has finished loading
_stop_cache_ready = False
_stop_cache_lock = threading.Lock()
_stop_services_index_checked = False
_stop_services_index_lock = threading.Lock()


def _serialize_user(user: User):
    return {
        "id": user.id,
        "email": user.email,
        "userName": user.username,
        "colorblindmode": user.colorblind_mode,
        "accessibilitymode": user.accessibility_mode or "none",
        "accessibilityzoom": float(user.accessibility_zoom or 1.0),
        "accessibilityfontsize": (user.accessibility_font_size or "normal"),
        "isAdmin": bool(getattr(user, "is_admin", False)),
    }


def _admin_emails():
    raw = os.getenv("ADMIN_EMAILS", "") or os.getenv("ADMIN_EMAIL", "")
    return {email.strip().lower() for email in raw.split(",") if email.strip()}


def _is_admin_email(email: str):
    return (email or "").strip().lower() in _admin_emails()


def _ensure_internal_admin_account():
    """Ensure a built-in admin account exists with known credentials."""
    with app.app_context():
        email = (os.getenv("INTERNAL_ADMIN_EMAIL", INTERNAL_ADMIN_EMAIL) or "").strip().lower()
        username = (os.getenv("INTERNAL_ADMIN_USERNAME", INTERNAL_ADMIN_USERNAME) or "").strip()
        password = os.getenv("INTERNAL_ADMIN_PASSWORD", INTERNAL_ADMIN_PASSWORD) or ""

        if "@" not in email or len(username) < 3 or len(password) < 8:
            app.logger.error("Internal admin credentials are invalid; skipping bootstrap")
            return

        try:
            existing = User.query.filter_by(email=email).first()
            hashed = generate_password_hash(password)

            if existing:
                existing.username = username
                existing.password_hash = hashed
                existing.is_admin = True
                db.session.commit()
                app.logger.info(f"Internal admin account ensured for {email}")
                return

            user = User(
                email=email,
                username=username,
                password_hash=hashed,
                is_admin=True,
            )
            db.session.add(user)
            db.session.flush()
            db.session.add(
                Notification(
                    user_id=user.id,
                    message="Internal admin account provisioned.",
                )
            )
            db.session.commit()
            app.logger.info(f"Internal admin account created for {email}")
        except Exception as exc:
            db.session.rollback()
            app.logger.warning(f"Could not bootstrap internal admin account: {exc}")


def _json_error(message: str, status: int = 400):
    return jsonify({"error": message}), status


def _route_time_key(route):
    return tuple(int(part) for part in route["start_time"].split(":"))


def _wants_rail(query_words):
    return any(w in {"rail", "railway", "train", "station", "stn"} for w in query_words)


def _wants_bus(query_words):
    return any(w in {"bus", "coach"} for w in query_words)


def _score_stop_match(query, query_words, common_name, locality_name, stop_type):
    """Higher score means a better autocomplete candidate."""
    common = (common_name or "").lower().strip()
    locality = (locality_name or "").lower().strip()
    q = (query or "").lower().strip()
    score = 0.0

    # Strong text match signals
    if common == q:
        score += 220
    if common.startswith(q):
        score += 160
    if q and q in common:
        score += 80
    if all(w in common for w in query_words):
        score += 55

    # Locality relevance (important for ambiguous district-wide names)
    if query_words:
        locality_hits = sum(1 for w in query_words if w in locality)
        score += locality_hits * 35
        if query_words[-1] and locality == query_words[-1]:
            score += 70

    # Mode-intent relevance
    if _wants_rail(query_words):
        if stop_type == 'rail':
            score += 120
        if 'railway station' in common or common.endswith('station'):
            score += 40
    if _wants_bus(query_words):
        if stop_type == 'bus':
            score += 80

    # Light penalty for very long/descriptive names
    score -= min(len(common), 120) / 40.0
    return score


def _resolve_stop_coordinates(stop_name: str):
    """Resolve a stop name to coordinates using StopCache.

    Returns ``(lat, lon)`` or ``(None, None)``.
    """
    if not stop_name:
        return None, None

    cleaned = stop_name.strip().lower()
    if not cleaned:
        return None, None

    query_words = [w for w in cleaned.split() if w]
    if not query_words:
        return None, None

    try:
        filters = [StopCache.search_text.contains(word) for word in query_words]
        candidates = StopCache.query.filter(*filters).limit(200).all()
        if not candidates:
            return None, None

        best = max(
            candidates,
            key=lambda s: _score_stop_match(
                cleaned,
                query_words,
                s.common_name,
                s.locality_name,
                s.stop_type,
            )
        )
        return float(best.latitude), float(best.longitude)
    except Exception:
        return None, None


def _virtual_rail_station_candidates(query: str, query_words):
    """Return virtual rail station suggestions from known CRS stations."""
    if not _wants_rail(query_words):
        return []

    out = []
    q = (query or '').lower().strip()
    for crs, st in transport_service.route_planner.STATIONS.items():
        base_name = st.get('name', '')
        if not base_name:
            continue
        display = f"{base_name} Railway Station"
        combined = display.lower()
        if query_words and not all(w in combined for w in query_words):
            continue
        score = _score_stop_match(q, query_words, display, base_name, 'rail') + 300
        out.append({
            'name': display,
            'atcoCode': f'CRS:{crs}',
            'lat': float(st['lat']),
            'lon': float(st['lon']),
            'stopType': 'rail',
            '_score': score,
        })
    out.sort(key=lambda x: x['_score'], reverse=True)
    return out


def _resolve_stop_by_atco(atco_code: str):
    """Resolve an exact ATCO code to canonical stop metadata from StopCache."""
    code = (atco_code or '').strip()
    if not code:
        return None
    if code.upper().startswith('CRS:'):
        crs = code.split(':', 1)[1].upper()
        st = transport_service.route_planner.STATIONS.get(crs)
        if st:
            return {
                'name': f"{st['name']} Railway Station",
                'lat': float(st['lat']),
                'lon': float(st['lon']),
                'stopType': 'rail',
            }
        return None
    try:
        stop = StopCache.query.filter_by(atco_code=code).first()
        if not stop:
            # Fallback when StopCache is not yet populated.
            try:
                meta = transport_service.route_planner._load_naptan_lookup().get(code)
            except Exception:
                meta = None
            if not meta:
                return None
            return {
                'name': meta.get('name', code),
                'lat': float(meta.get('lat')),
                'lon': float(meta.get('lon')),
                'stopType': 'bus',
            }
        display_name = stop.common_name
        if stop.indicator:
            display_name += f" ({stop.indicator})"
        if stop.locality_name and stop.locality_name not in display_name:
            display_name += f", {stop.locality_name}"
        return {
            'name': display_name,
            'lat': float(stop.latitude),
            'lon': float(stop.longitude),
            'stopType': stop.stop_type,
        }
    except Exception:
        return None


def _minutes_to_clock(total_minutes: int):
    mins = int(total_minutes) % (24 * 60)
    return f"{mins // 60:02d}:{mins % 60:02d}"


def _next_occurrence(raw_minutes: int, now_minutes: int):
    raw = int(raw_minutes) % (24 * 60)
    now = int(now_minutes)
    if raw < now:
        raw += 24 * 60
    return raw


def _align_at_or_after(raw_minutes: int, baseline_abs_minutes: int):
    """Align a time-of-day minute value so it is at/after an absolute baseline."""
    value = int(raw_minutes) % (24 * 60)
    baseline = int(baseline_abs_minutes)
    while value < baseline:
        value += 24 * 60
    return value


def _connection_index_stop_refs(atco_code: str):
    code = (atco_code or '').strip()
    refs = set()
    if not code:
        return refs

    refs.update({code, code.upper()})

    if code.upper().startswith('CRS:'):
        crs = code.split(':', 1)[1].strip().upper()
        if crs:
            refs.update({crs, f'CRS:{crs}', f'rail:{crs}', f'RAIL:{crs}'})

    return refs


def _connection_index_name_refs(stop_name: str):
    name = (stop_name or '').strip()
    if not name:
        return set()

    refs = {name}

    # Remove qualifiers commonly absent in raw connection refs.
    no_brackets = ' '.join(name.replace('(', ' ').replace(')', ' ').split())
    if no_brackets:
        refs.add(no_brackets)

    head = no_brackets.split(',')[0].strip()
    if head:
        refs.add(head)

    lower = {x.lower() for x in refs if x}
    refs.update(lower)
    return {x for x in refs if x}


def _ensure_stop_services_index_ready(planner):
    """Ensure stop-services has an index available on first use."""
    global _stop_services_index_checked

    store = getattr(planner, '_connection_index_store', None)
    if store is None:
        return False

    try:
        if store.has_connections():
            return True
    except Exception:
        pass

    with _stop_services_index_lock:
        store = getattr(planner, '_connection_index_store', None)
        if store is None:
            return False

        try:
            if store.has_connections():
                return True
        except Exception:
            pass

        if not _stop_services_index_checked:
            try:
                planner.build_connection_index(force_rebuild=False)
            except Exception as e:
                app.logger.warning(f"Stop-services first-run index build failed: {e}")
            finally:
                _stop_services_index_checked = True

        try:
            return bool(store.has_connections())
        except Exception:
            return False


def _parse_hhmm(value):
    txt = (value or '').strip()
    if not re.match(r'^\d{1,2}:\d{2}$', txt):
        return None
    hh, mm = txt.split(':', 1)
    try:
        h = int(hh)
        m = int(mm)
    except Exception:
        return None
    if h < 0 or h > 23 or m < 0 or m > 59:
        return None
    return h * 60 + m


def _candidate_rail_crs_codes(planner, atco_code: str, stop_meta: dict):
    candidates = []

    code = (atco_code or '').strip().upper()
    if code.startswith('CRS:') and len(code) >= 8:
        candidates.append(code.split(':', 1)[1])

    stop_name = (stop_meta or {}).get('name', '') or ''
    if stop_name:
        try:
            locality_codes = planner._crs_for_locality(stop_name) or []
            candidates.extend([str(c).upper() for c in locality_codes if c])
        except Exception:
            pass

    try:
        lat = float((stop_meta or {}).get('lat'))
        lon = float((stop_meta or {}).get('lon'))
        nearest = planner._find_nearest_stations(lat, lon, max_km=2.2, max_results=3) or []
        candidates.extend([str(crs).upper() for crs, _, _ in nearest if crs])
    except Exception:
        pass

    deduped = []
    seen = set()
    for crs in candidates:
        c = (crs or '').strip().upper()
        if len(c) != 3 or c in seen:
            continue
        seen.add(c)
        deduped.append(c)
    return deduped


def _generic_intermediate_stops(from_name, to_name, mode):
    name_pair = f"{from_name} {to_name}".lower()
    if mode == "train":
        if "lancaster" in name_pair and "manchester" in name_pair:
            return [
                {"name": "Preston", "time": None},
                {"name": "Wigan North Western", "time": None},
            ]
        if "lancaster" in name_pair and "preston" in name_pair:
            return [
                {"name": "Garstang", "time": None},
            ]
        return [{"name": "Preston", "time": None}]

    if "lancaster" in name_pair and "university" in name_pair:
        return [
            {"name": "Hala", "time": None},
            {"name": "Underpass", "time": None},
        ]
    if "lancaster" in name_pair and "preston" in name_pair:
        return [
            {"name": "Galgate", "time": None},
            {"name": "Garstang Cross", "time": None},
        ]
    return [{"name": "Intermediate Stop", "time": None}]


def _with_intermediate_times(planner, intermediates, depart_mins, arrive_mins):
    if not intermediates:
        return []

    timed = []
    total = max(1, arrive_mins - depart_mins)
    for idx, stop in enumerate(intermediates, start=1):
        frac = idx / (len(intermediates) + 1)
        timed.append({
            "name": stop["name"],
            "time": planner._fmt(depart_mins + int(total * frac)),
        })
    return timed


def _build_generic_bus_route(
    planner,
    from_name,
    to_name,
    now_mins,
    dist_km,
    depart_offset,
    ride_mins,
    service_name,
    walk_to_km=0.0,
    walk_from_km=0.0,
):
    depart_mins = now_mins + depart_offset
    legs = []
    bus_from = from_name
    bus_to = to_name

    if walk_to_km >= 0.05:
        origin_stop = f"{from_name} Stop"
        walk_mins = max(1, int(walk_to_km * 1000 * planner.WALK_FACTOR / planner.WALK_SPEED))
        legs.append(planner._walk_leg(from_name, origin_stop, depart_mins - walk_mins, walk_to_km))
        bus_from = origin_stop

    if walk_from_km >= 0.05:
        bus_to = f"{to_name} Stop"

    arrive_mins = depart_mins + ride_mins
    intermediates = _with_intermediate_times(
        planner,
        _generic_intermediate_stops(from_name, to_name, "bus"),
        depart_mins,
        arrive_mins,
    )
    legs.append({
        "mode": "bus",
        "service": service_name,
        "from_stop": bus_from,
        "to_stop": bus_to,
        "depart": planner._fmt(depart_mins),
        "arrive": planner._fmt(arrive_mins),
        "duration_mins": ride_mins,
        "intermediate_stops": intermediates,
    })

    if walk_from_km >= 0.05:
        legs.append(planner._walk_leg(bus_to, to_name, arrive_mins, walk_from_km))

    return planner._summarise(legs)


def _build_generic_train_route(
    planner,
    from_name,
    to_name,
    now_mins,
    dist_km,
    depart_offset,
    ride_mins,
    service_name,
    walk_to_km=0.0,
    walk_from_km=0.0,
):
    depart_mins = now_mins + depart_offset
    legs = []
    train_from = from_name
    train_to = to_name

    if walk_to_km >= 0.05:
        origin_station = f"{from_name} Railway Station"
        walk_mins = max(1, int(walk_to_km * 1000 * planner.WALK_FACTOR / planner.WALK_SPEED))
        legs.append(planner._walk_leg(from_name, origin_station, depart_mins - walk_mins, walk_to_km))
        train_from = origin_station

    if walk_from_km >= 0.05:
        train_to = f"{to_name} Railway Station"

    arrive_mins = depart_mins + ride_mins
    intermediates = _with_intermediate_times(
        planner,
        _generic_intermediate_stops(from_name, to_name, "train"),
        depart_mins,
        arrive_mins,
    )
    legs.append({
        "mode": "train",
        "service": service_name,
        "from_stop": train_from,
        "to_stop": train_to,
        "depart": planner._fmt(depart_mins),
        "arrive": planner._fmt(arrive_mins),
        "duration_mins": ride_mins,
        "intermediate_stops": intermediates,
    })

    if walk_from_km >= 0.05:
        legs.append(planner._walk_leg(train_to, to_name, arrive_mins, walk_from_km))

    return planner._summarise(legs)


def _generate_valid_mock_routes(
    from_name,
    to_name,
    from_lat=None,
    from_lon=None,
    to_lat=None,
    to_lon=None,
):
    """Return deterministic mock routes for tests and API fallback.

    The helper uses the current route-planner data structures so the output
    shape matches the frontend contract, while avoiding hard dependence on
    external APIs during tests.
    """
    planner = transport_service.route_planner
    if from_lat is None or from_lon is None or to_lat is None or to_lon is None:
        from_lat, from_lon = 54.0488, -2.8013
        to_lat, to_lon = 54.0104, -2.7856

    dist_km = planner._haversine(from_lat, from_lon, to_lat, to_lon)
    now = datetime.utcnow()
    now_mins = now.hour * 60 + now.minute
    routes = []

    def add_route(route):
        if route and route.get("legs"):
            routes.append(route)

    def add_walk_route(offset, distance_scale=1.0):
        walk_leg = planner._walk_leg(
            from_name,
            to_name,
            now_mins + offset,
            max(0.05, dist_km * distance_scale),
        )
        add_route(planner._summarise([walk_leg]))

    if dist_km < 1.0:
        add_walk_route(2, 1.00)
        add_walk_route(6, 1.18)
        add_route(_build_generic_bus_route(
            planner,
            from_name,
            to_name,
            now_mins,
            dist_km,
            12,
            max(4, int(dist_km * 18)),
            "Stagecoach 1",
            walk_to_km=0.08,
            walk_from_km=0.06,
        ))
    else:
        bus_matches = planner._find_bus_routes(from_lat, from_lon, to_lat, to_lon)
        for match in bus_matches[:2]:
            for route in planner._build_bus_routes(from_name, to_name, match, now_mins)[:2]:
                add_route(route)

        if dist_km < 5.0:
            if len([r for r in routes if "bus" in r["transport"]]) < 2:
                add_route(_build_generic_bus_route(
                    planner,
                    from_name,
                    to_name,
                    now_mins,
                    dist_km,
                    8,
                    max(10, int(dist_km * 7)),
                    "Stagecoach 1A",
                    walk_to_km=min(0.2, dist_km * 0.08),
                    walk_from_km=min(0.2, dist_km * 0.06),
                ))
                add_route(_build_generic_bus_route(
                    planner,
                    from_name,
                    to_name,
                    now_mins,
                    dist_km,
                    18,
                    max(12, int(dist_km * 8)),
                    "Stagecoach 100",
                    walk_to_km=min(0.25, dist_km * 0.10),
                    walk_from_km=min(0.2, dist_km * 0.07),
                ))
        elif dist_km < 15.0:
            if not any("bus" in r["transport"] for r in routes):
                add_route(_build_generic_bus_route(
                    planner,
                    from_name,
                    to_name,
                    now_mins,
                    dist_km,
                    10,
                    max(18, int(dist_km * 5)),
                    "Stagecoach 41",
                    walk_to_km=0.18,
                    walk_from_km=0.14,
                ))
            add_route(_build_generic_bus_route(
                planner,
                from_name,
                to_name,
                now_mins,
                dist_km,
                22,
                max(20, int(dist_km * 5.5)),
                "Stagecoach 40",
                walk_to_km=0.12,
                walk_from_km=0.10,
            ))
        else:
            add_route(_build_generic_train_route(
                planner,
                from_name,
                to_name,
                now_mins,
                dist_km,
                14,
                max(35, int(dist_km * 1.7)),
                "Northern",
                walk_to_km=0.10,
                walk_from_km=0.10,
            ))
            add_route(_build_generic_train_route(
                planner,
                from_name,
                to_name,
                now_mins,
                dist_km,
                34,
                max(32, int(dist_km * 1.55)),
                "Avanti West Coast",
                walk_to_km=0.08,
                walk_from_km=0.12,
            ))
            add_route(_build_generic_bus_route(
                planner,
                from_name,
                to_name,
                now_mins,
                dist_km,
                50,
                max(55, int(dist_km * 4.5)),
                "Stagecoach 555",
                walk_to_km=0.15,
                walk_from_km=0.15,
            ))

    if len(routes) < 2:
        add_route(_build_generic_bus_route(
            planner,
            from_name,
            to_name,
            now_mins,
            dist_km,
            10,
            max(12, int(max(1.0, dist_km) * 6)),
            "Stagecoach 1",
            walk_to_km=0.10,
            walk_from_km=0.10,
        ))
        add_walk_route(4, 1.05)

    seen = set()
    unique_routes = []
    for route in routes:
        key = (
            route["start_time"],
            route["end_time"],
            tuple(route["transport"]),
            route["changes"],
        )
        if key not in seen:
            seen.add(key)
            unique_routes.append(route)

    unique_routes.sort(key=_route_time_key)
    return unique_routes


def _create_token(user_id: int):
    return token_serializer.dumps({"uid": user_id})


def _parse_iso_datetime(value):
    if not value:
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None


def auth_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        auth_header = request.headers.get("Authorization", "")
        if not auth_header.startswith("Bearer "):
            return _json_error("Missing bearer token", 401)

        token = auth_header.split(" ", 1)[1].strip()
        try:
            payload = token_serializer.loads(token, max_age=app.config["AUTH_TOKEN_MAX_AGE_SECONDS"])
        except SignatureExpired:
            return _json_error("Token expired", 401)
        except BadSignature:
            return _json_error("Invalid token", 401)

        user = User.query.get(payload.get("uid"))
        if not user:
            return _json_error("User not found", 401)

        g.current_user = user
        return fn(*args, **kwargs)

    return wrapper


@app.route("/health")
def health():
    return jsonify({"status": "ok"})


@app.route("/api/health")
def api_health():
    diagnostics = {
        "status": "ok",
        "static_data_only": bool(app.config.get("STATIC_DATA_ONLY")),
    }
    try:
        diagnostics["stop_cache_ready"] = bool(_stop_cache_ready)
        diagnostics["stop_cache_rows"] = int(StopCache.query.count())
    except Exception:
        diagnostics["stop_cache_ready"] = False
        diagnostics["stop_cache_rows"] = 0

    try:
        planner = transport_service.route_planner
        diagnostics["route_index_db"] = str(getattr(planner._connection_index_store, "db_path", ""))
        diagnostics["route_index_has_connections"] = bool(
            planner._connection_index_store and planner._connection_index_store.has_connections()
        )
    except Exception:
        diagnostics["route_index_db"] = ""
        diagnostics["route_index_has_connections"] = False

    return jsonify(diagnostics)


@app.route("/api/hello")
def hello():
    return jsonify({"message": "Transport backend running"})


@app.route("/api/auth/register", methods=["POST"])
def register():
    data = request.get_json(silent=True) or {}
    email = (data.get("email") or "").strip().lower()
    username = (data.get("userName") or "").strip()
    password = data.get("password") or ""

    if "@" not in email:
        return _json_error("A valid email is required")
    if len(username) < 3:
        return _json_error("Username must be at least 3 characters")
    if len(password) < 8:
        return _json_error("Password must be at least 8 characters")

    existing_user = User.query.filter_by(email=email).first()
    if existing_user:
        return _json_error("Email already registered", 409)

    user = User(
        email=email,
        username=username,
        password_hash=generate_password_hash(password),
        is_admin=_is_admin_email(email),
    )
    db.session.add(user)
    db.session.flush()
    db.session.add(
        Notification(
            user_id=user.id,
            message="Welcome to Transport for North West. Your account is now active.",
        )
    )
    db.session.commit()

    token = _create_token(user.id)
    return jsonify({"token": token, "user": _serialize_user(user)}), 201


@app.route("/api/auth/login", methods=["POST"])
def login():
    data = request.get_json(silent=True) or {}
    email = (data.get("email") or "").strip().lower()
    password = data.get("password") or ""

    user = User.query.filter_by(email=email).first()
    if not user or not check_password_hash(user.password_hash, password):
        return _json_error("Invalid credentials", 401)

    token = _create_token(user.id)
    return jsonify({"token": token, "user": _serialize_user(user)})


@app.route("/api/auth/logout", methods=["POST"])
def logout():
    return jsonify({"message": "Logged out"})


@app.route("/api/account/me", methods=["GET"])
@auth_required
def me():
    return jsonify({"user": _serialize_user(g.current_user)})


@app.route("/api/account/profile", methods=["PATCH"])
@auth_required
def update_profile():
    data = request.get_json(silent=True) or {}
    user = g.current_user

    if "userName" in data:
        username = (data.get("userName") or "").strip()
        if len(username) < 3:
            return _json_error("Username must be at least 3 characters")
        user.username = username

    if "colorblindmode" in data:
        user.colorblind_mode = bool(data.get("colorblindmode"))
        if not user.colorblind_mode:
            user.accessibility_mode = "none"
        elif (user.accessibility_mode or "none") == "none":
            user.accessibility_mode = "deuteranopia"

    if "accessibilitymode" in data:
        allowed_modes = {"none", "deuteranopia", "protanopia", "tritanopia", "achromatopsia"}
        mode = str(data.get("accessibilitymode") or "none").strip().lower()
        if mode not in allowed_modes:
            return _json_error("Unsupported accessibility mode")
        user.accessibility_mode = mode
        user.colorblind_mode = mode != "none"

    if "accessibilityfontsize" in data:
        allowed_sizes = {"small", "normal", "large"}
        size = str(data.get("accessibilityfontsize") or "normal").strip().lower()
        if size not in allowed_sizes:
            return _json_error("Unsupported accessibility font size")
        user.accessibility_font_size = size

    if "accessibilityzoom" in data:
        try:
            zoom = float(data.get("accessibilityzoom"))
        except (TypeError, ValueError):
            return _json_error("Accessibility zoom must be a number")

        if zoom < 0.85 or zoom > 1.4:
            return _json_error("Accessibility zoom must be between 0.85 and 1.4")
        user.accessibility_zoom = round(zoom, 2)

    db.session.commit()
    return jsonify({"user": _serialize_user(user)})


@app.route("/api/account/password", methods=["PATCH"])
@auth_required
def update_password():
    data = request.get_json(silent=True) or {}
    current_password = data.get("currentPassword") or ""
    new_password = data.get("newPassword") or ""

    user = g.current_user
    if not check_password_hash(user.password_hash, current_password):
        return _json_error("Current password is incorrect", 401)
    if len(new_password) < 8:
        return _json_error("New password must be at least 8 characters")

    user.password_hash = generate_password_hash(new_password)
    db.session.commit()

    return jsonify({"message": "Password updated"})


@app.route("/api/account", methods=["DELETE"])
@auth_required
def delete_account():
    data = request.get_json(silent=True) or {}
    password = data.get("password") or ""
    user = g.current_user

    if bool(getattr(user, "is_admin", False)):
        return _json_error("Admin accounts cannot be deleted", 403)

    if not check_password_hash(user.password_hash, password):
        return _json_error("Password is incorrect", 401)

    db.session.delete(user)
    db.session.commit()

    return jsonify({"message": "Account deleted"})


@app.route("/api/account/saved-routes", methods=["GET"])
@auth_required
def get_saved_routes():
    rows = (
        db.session.query(Route)
        .join(Save, Save.route_id == Route.id)
        .filter(Save.user_id == g.current_user.id)
        .all()
    )

    routes = [
        {
            "routeID": route.id,
            "routeName": route.route_name,
            "routeStart": route.route_start,
            "routeEnd": route.route_end,
            "startTime": route.start_time.isoformat() if route.start_time else None,
            "endTime": route.end_time.isoformat() if route.end_time else None,
            "disruption": route.disruption,
        }
        for route in rows
    ]
    return jsonify({"savedRoutes": routes})


@app.route("/api/account/saved-routes", methods=["POST"])
@auth_required
def save_route():
    data = request.get_json(silent=True) or {}

    route_name = (data.get("routeName") or "").strip()
    route_start = (data.get("routeStart") or "").strip()
    route_end = (data.get("routeEnd") or "").strip()
    start_time = _parse_iso_datetime(data.get("startTime"))
    end_time = _parse_iso_datetime(data.get("endTime"))
    disruption = data.get("disruption")

    if not route_name or not route_start or not route_end:
        return _json_error("routeName, routeStart and routeEnd are required")

    route = (
        Route.query.filter_by(
            route_name=route_name,
            route_start=route_start,
            route_end=route_end,
            start_time=start_time,
            end_time=end_time,
        ).first()
    )

    if not route:
        route = Route(
            route_name=route_name,
            route_start=route_start,
            route_end=route_end,
            start_time=start_time,
            end_time=end_time,
            disruption=disruption,
        )
        db.session.add(route)
        db.session.flush()

    existing_save = Save.query.filter_by(user_id=g.current_user.id, route_id=route.id).first()
    if not existing_save:
        db.session.add(Save(user_id=g.current_user.id, route_id=route.id))
        db.session.add(
            Notification(
                user_id=g.current_user.id,
                message=f"Route saved: {route.route_start} → {route.route_end}",
            )
        )

    db.session.commit()

    return jsonify({"message": "Route saved", "routeID": route.id}), 201


@app.route("/api/account/saved-routes/<int:route_id>", methods=["DELETE"])
@auth_required
def unsave_route(route_id: int):
    save = Save.query.filter_by(user_id=g.current_user.id, route_id=route_id).first()
    if not save:
        return _json_error("Saved route not found", 404)

    db.session.delete(save)
    db.session.commit()
    return jsonify({"message": "Saved route removed"})


@app.route("/api/account/notifications", methods=["GET"])
@auth_required
def get_notifications():
    notifications = (
        Notification.query.filter_by(user_id=g.current_user.id)
        .order_by(Notification.created_at.desc())
        .limit(30)
        .all()
    )

    return jsonify(
        {
            "notifications": [
                {
                    "notificationID": item.id,
                    "message": item.message,
                    "createdAt": item.created_at.isoformat(),
                    "isRead": item.is_read,
                }
                for item in notifications
            ]
        }
    )


@app.route("/api/account/notifications/<int:notification_id>/read", methods=["PATCH"])
@auth_required
def mark_notification_read(notification_id: int):
    notification = Notification.query.filter_by(id=notification_id, user_id=g.current_user.id).first()
    if not notification:
        return _json_error("Notification not found", 404)

    notification.is_read = True
    db.session.commit()
    return jsonify({"message": "Notification marked as read"})


@app.route("/api/admin/notifications", methods=["POST"])
@auth_required
def create_admin_notification():
    if not getattr(g.current_user, "is_admin", False):
        return _json_error("Admin access required", 403)

    data = request.get_json(silent=True) or {}
    message = str(data.get("message") or "").strip()
    if not message:
        return _json_error("Message is required")
    if len(message) > 500:
        return _json_error("Message must be 500 characters or fewer")

    target_user_id = data.get("targetUserId")
    if target_user_id in (None, ""):
        recipients = User.query.all()
    else:
        try:
            target_user_id = int(target_user_id)
        except (TypeError, ValueError):
            return _json_error("targetUserId must be an integer")

        target_user = User.query.get(target_user_id)
        if not target_user:
            return _json_error("Target user not found", 404)
        recipients = [target_user]

    notifications = [Notification(user_id=user.id, message=message) for user in recipients]
    if notifications:
        db.session.add_all(notifications)
    db.session.commit()

    return jsonify({"message": "Notification created", "count": len(notifications)}), 201


@app.route("/api/account/weather-locations", methods=["GET"])
@auth_required
def get_weather_locations():
    items = UserWeather.query.filter_by(user_id=g.current_user.id).all()
    return jsonify({"locations": [item.location for item in items]})


@app.route("/api/account/weather-locations", methods=["POST"])
@auth_required
def add_weather_location():
    data = request.get_json(silent=True) or {}
    location = (data.get("location") or "").strip()

    if not location:
        return _json_error("location is required")

    existing = UserWeather.query.filter_by(user_id=g.current_user.id, location=location).first()
    if not existing:
        db.session.add(UserWeather(user_id=g.current_user.id, location=location))
        db.session.commit()

    return jsonify({"message": "Location tracked", "location": location}), 201


@app.route("/api/account/weather-locations/<string:location>", methods=["DELETE"])
@auth_required
def remove_weather_location(location: str):
    item = UserWeather.query.filter_by(user_id=g.current_user.id, location=location).first()
    if not item:
        return _json_error("Location not found", 404)

    db.session.delete(item)
    db.session.commit()
    return jsonify({"message": "Location removed"})


@app.route('/api/gazetteer')
def gazetteer():
    try:
        data = transport_service.get_gazetteer()
        return jsonify(data)
    except Exception as e:
        app.logger.error(f"Gazetteer error: {e}")
        return jsonify({"error": str(e)}), 500


@app.route('/api/naptan')
def naptan():
    try:
        if app.config.get("STATIC_DATA_ONLY"):
            stops = StopCache.query.all()
            return jsonify({
                "stops": [
                    {
                        "ATCOCode": s.atco_code,
                        "NaptanCode": s.naptan_code,
                        "CommonName": s.common_name,
                        "Indicator": s.indicator,
                        "LocalityName": s.locality_name,
                        "Latitude": s.latitude,
                        "Longitude": s.longitude,
                        "StopType": s.stop_type,
                    }
                    for s in stops
                ]
            })

        full = request.args.get('full', 'false').lower() == 'true'
        dataset = (request.args.get('dataset', 'lancashire') or 'lancashire').strip().lower()
        if dataset in {'nw', 'northwest', 'north-west', 'north_west'}:
            dataset = 'north_west_rail'
        data = transport_service.get_naptan(dataset=dataset, full=full)
        return jsonify(data)
    except Exception as e:
        app.logger.error(f"NaPTAN error: {e}")
        return jsonify({"error": str(e)}), 500


@app.route('/api/stops/search')
def search_stops():
    """Search for bus and train stops within map bounds with autocomplete support.
    Uses the local StopCache database only (no live NaPTAN fallback).
    Matching is word-order-independent: every word in the query must appear
    somewhere in the stop name or locality, but not necessarily in order.
    For example, 'Lancaster Under' will match 'underpass (by) Lancaster'."""
    try:
        query = request.args.get('q', '').strip().lower()
        limit = min(int(request.args.get('limit', 10)), 50)

        # Map bounds (matches frontend maxBounds)
        MIN_LAT, MAX_LAT = 53.0, 55.2
        MIN_LON, MAX_LON = -3.7, -1.9

        if not query or len(query) < 2:
            return jsonify({"stops": []})

        # Split query into individual words for order-independent matching
        query_words = query.split()

        app.logger.info(f"Searching stop cache DB for: {query}")

        # Build SQLAlchemy filter: every word must appear in search_text
        filters = [
            StopCache.latitude >= MIN_LAT,
            StopCache.latitude <= MAX_LAT,
            StopCache.longitude >= MIN_LON,
            StopCache.longitude <= MAX_LON,
        ]

        # Candidate prefilter: at least one query word present.
        if query_words:
            filters.append(or_(*[StopCache.search_text.contains(word) for word in query_words]))

        candidates = (
            StopCache.query
            .filter(*filters)
            .limit(500)
            .all()
        )

        min_coverage = len(query_words)
        if len(query_words) >= 3 and not (_wants_bus(query_words) or _wants_rail(query_words)):
            min_coverage = len(query_words) - 1

        scored = []
        require_bus = _wants_bus(query_words)
        require_rail = _wants_rail(query_words)
        for s in candidates:
            if require_bus and s.stop_type != 'bus':
                continue
            if require_rail and not require_bus and s.stop_type != 'rail':
                continue
            search_text = (s.search_text or '').lower()
            coverage = sum(1 for w in query_words if w in search_text)
            if coverage < min_coverage:
                continue
            score = _score_stop_match(
                query,
                query_words,
                s.common_name,
                s.locality_name,
                s.stop_type,
            ) + (coverage * 25)
            scored.append((score, s))

        ranked = [s for _, s in sorted(scored, key=lambda x: x[0], reverse=True)]
        results = ranked[:limit]

        matching_stops = []
        for stop in results:
            display_name = stop.common_name
            if stop.indicator:
                display_name += f" ({stop.indicator})"
            if stop.locality_name and stop.locality_name not in display_name:
                display_name += f", {stop.locality_name}"
            matching_stops.append({
                'name': display_name,
                'atcoCode': stop.atco_code,
                'lat': stop.latitude,
                'lon': stop.longitude,
                'stopType': stop.stop_type,
            })

        virtual = _virtual_rail_station_candidates(query, query_words)
        if virtual:
            dedup = set(s.get('atcoCode') for s in matching_stops)
            merged = []
            for v in virtual:
                code = v.get('atcoCode')
                if code in dedup:
                    continue
                vv = dict(v)
                vv.pop('_score', None)
                merged.append(vv)
            matching_stops = (merged + matching_stops)[:limit]

        app.logger.info(f"Returning {len(matching_stops)} stops from DB cache for '{query}'")
        return jsonify({"stops": matching_stops})

    except Exception as e:
        app.logger.error(f"Stop search error: {e}")
        return jsonify({"error": str(e), "stops": []}), 500


@app.route('/api/stops/in-bounds')
def stops_in_bounds():
    """Return stops within a map bounding box for map overlays."""
    try:
        min_lat = float(request.args.get('minLat', 53.0))
        max_lat = float(request.args.get('maxLat', 55.2))
        min_lon = float(request.args.get('minLon', -3.7))
        max_lon = float(request.args.get('maxLon', -1.9))
        limit = min(max(int(request.args.get('limit', 400)), 1), 1000)

        # Clamp to the application map envelope.
        map_min_lat, map_max_lat = 53.0, 55.2
        map_min_lon, map_max_lon = -3.7, -1.9

        min_lat = max(min(min_lat, max_lat), map_min_lat)
        max_lat = min(max(min_lat, max_lat), map_max_lat)
        min_lon = max(min(min_lon, max_lon), map_min_lon)
        max_lon = min(max(min_lon, max_lon), map_max_lon)

        rows = (
            StopCache.query
            .filter(
                StopCache.latitude >= min_lat,
                StopCache.latitude <= max_lat,
                StopCache.longitude >= min_lon,
                StopCache.longitude <= max_lon,
            )
            .order_by(StopCache.locality_name.asc(), StopCache.common_name.asc())
            .limit(limit)
            .all()
        )

        stops = []
        for stop in rows:
            display_name = stop.common_name
            if stop.indicator:
                display_name += f" ({stop.indicator})"
            if stop.locality_name and stop.locality_name not in display_name:
                display_name += f", {stop.locality_name}"
            stops.append({
                'name': display_name,
                'atcoCode': stop.atco_code,
                'lat': float(stop.latitude),
                'lon': float(stop.longitude),
                'stopType': stop.stop_type,
            })

        return jsonify({'stops': stops})
    except Exception as e:
        app.logger.error(f"Stops in bounds error: {e}")
        return jsonify({'error': str(e), 'stops': []}), 500


@app.route('/api/stops/<string:atco_code>/services')
def stop_services(atco_code):
    """Return upcoming services for a specific stop and each service's final destination ETA."""
    stop_meta = _resolve_stop_by_atco(atco_code)
    if not stop_meta:
        return jsonify({'error': 'Stop not found', 'services': []}), 404

    try:
        limit = min(max(int(request.args.get('limit', 8)), 1), 30)
    except (TypeError, ValueError):
        limit = 8
    try:
        horizon_mins = min(max(int(request.args.get('horizonMins', 240)), 30), 24 * 60)
    except (TypeError, ValueError):
        horizon_mins = 240

    planner = transport_service.route_planner

    # Rail stops: prefer live rail departure boards for accuracy.
    is_rail_stop = str(stop_meta.get('stopType', '')).strip().lower() == 'rail' or str(atco_code).upper().startswith('CRS:')
    if is_rail_stop:
        now_mins = datetime.now().hour * 60 + datetime.now().minute
        rail_candidates = []
        for crs in _candidate_rail_crs_codes(planner, atco_code, stop_meta):
            try:
                board = planner._fetch_rail_departures_cached(crs)
            except Exception:
                continue

            for svc in board.get('services', []) or []:
                std = (svc.get('std') or '').strip()
                dep_raw = _parse_hhmm(std)
                if dep_raw is None:
                    continue
                dep_abs = _next_occurrence(dep_raw, now_mins)
                if dep_abs > (now_mins + horizon_mins):
                    continue

                cps = svc.get('calling_points') or []
                final_cp = None
                for cp in reversed(cps):
                    sched = (cp.get('scheduled') or '').strip()
                    est = (cp.get('estimated') or '').strip()
                    if _parse_hhmm(sched) is not None or _parse_hhmm(est) is not None:
                        final_cp = cp
                        break

                if final_cp:
                    final_dest = (final_cp.get('name') or '').strip()
                    final_time_str = (final_cp.get('scheduled') or '').strip() or (final_cp.get('estimated') or '').strip()
                else:
                    final_dest = (svc.get('destination') or {}).get('name', '')
                    final_time_str = ''

                final_raw = _parse_hhmm(final_time_str)
                if not final_dest or final_raw is None:
                    continue

                final_abs = _align_at_or_after(final_raw, dep_abs)
                mode = 'train'
                service_type = str(svc.get('service_type', '')).strip().lower()
                if service_type == 'bus':
                    mode = 'bus'

                service_name = (svc.get('operator') or '').strip()
                if not service_name:
                    service_name = (svc.get('service_id') or '').strip()
                if not service_name:
                    service_name = 'Rail service'

                rail_candidates.append({
                    'service': service_name,
                    'mode': mode,
                    'arrivalAtStop': _minutes_to_clock(dep_abs),
                    'arrivalAtFinalDestination': _minutes_to_clock(final_abs),
                    'finalDestination': final_dest,
                    '_sort': dep_abs,
                })

            if rail_candidates:
                break

        if rail_candidates:
            deduped = []
            seen = set()
            for item in sorted(rail_candidates, key=lambda x: (x['_sort'], x['service'], x['finalDestination'])):
                key = (item['service'], item['mode'], item['arrivalAtStop'], item['finalDestination'])
                if key in seen:
                    continue
                seen.add(key)
                payload = dict(item)
                payload.pop('_sort', None)
                deduped.append(payload)
                if len(deduped) >= limit:
                    break
            return jsonify({'stop': stop_meta, 'services': deduped})

    store = getattr(planner, '_connection_index_store', None)
    if store is None:
        return jsonify({'stop': stop_meta, 'services': []})

    if not _ensure_stop_services_index_ready(planner):
        return jsonify({'stop': stop_meta, 'services': []})

    exact_refs = set(_connection_index_stop_refs(atco_code))
    fallback_refs = set(exact_refs)
    fallback_refs.update(_connection_index_name_refs(stop_meta.get('name', '')))

    search_refs = list(exact_refs if exact_refs else fallback_refs)
    if not search_refs:
        return jsonify({'stop': stop_meta, 'services': []})

    placeholders = ','.join(['?'] * len(search_refs))
    now_mins = datetime.now().hour * 60 + datetime.now().minute

    candidates = []
    try:
        with sqlite3.connect(str(store.db_path), timeout=30) as con:
            con.row_factory = sqlite3.Row

            rows = con.execute(
                f"""
                SELECT dataset_id, trip_id, service, mode, from_ref, to_ref, dep_raw, arr_raw
                FROM connections
                WHERE from_ref IN ({placeholders}) OR to_ref IN ({placeholders})
                ORDER BY dep_raw ASC, arr_raw ASC
                LIMIT 600
                """,
                search_refs + search_refs,
            ).fetchall()

            # If exact stop-code refs did not yield rows, fall back to name refs.
            if not rows and fallback_refs and fallback_refs != set(search_refs):
                search_refs = list(fallback_refs)
                placeholders = ','.join(['?'] * len(search_refs))
                rows = con.execute(
                    f"""
                    SELECT dataset_id, trip_id, service, mode, from_ref, to_ref, dep_raw, arr_raw
                    FROM connections
                    WHERE from_ref IN ({placeholders}) OR to_ref IN ({placeholders})
                    ORDER BY dep_raw ASC, arr_raw ASC
                    LIMIT 600
                    """,
                    search_refs + search_refs,
                ).fetchall()

            MAX_TRIP_PROGRESS_MINS = 12 * 60

            for row in rows:
                is_boarding_point = row['from_ref'] in search_refs
                event_raw = int(row['dep_raw'] if is_boarding_point else row['arr_raw'])
                event_abs = _next_occurrence(event_raw, now_mins)
                if event_abs > (now_mins + horizon_mins):
                    continue

                trip_id = (row['trip_id'] or '').strip()
                dataset_id = (row['dataset_id'] or '').strip()

                final_stop_name = None
                final_arrival_abs = None

                if trip_id and dataset_id:
                    trip_rows = con.execute(
                        """
                        SELECT from_ref, to_ref, dep_raw, arr_raw
                        FROM connections
                        WHERE dataset_id = ? AND trip_id = ?
                        ORDER BY dep_raw ASC, arr_raw ASC
                        """,
                        (dataset_id, trip_id),
                    ).fetchall()

                    for trip_row in trip_rows:
                        # Compute progress from selected-stop event within one service day.
                        # This avoids selecting artefacts where times wrap to "almost 24h later"
                        # and appear as one minute earlier when formatted as HH:MM.
                        arr_raw_trip = int(trip_row['arr_raw']) % (24 * 60)
                        progress = (arr_raw_trip - event_raw) % (24 * 60)
                        if progress < 0 or progress > MAX_TRIP_PROGRESS_MINS:
                            continue

                        arr_abs = event_abs + progress
                        if final_arrival_abs is None or arr_abs >= final_arrival_abs:
                            final_arrival_abs = arr_abs
                            final_stop_name = trip_row['to_ref']

                if final_arrival_abs is None:
                    fallback_arr_raw = int(row['arr_raw']) % (24 * 60)
                    fallback_progress = (fallback_arr_raw - event_raw) % (24 * 60)
                    if fallback_progress > MAX_TRIP_PROGRESS_MINS:
                        continue
                    final_arrival_abs = event_abs + fallback_progress
                    final_stop_name = row['to_ref']

                final_name_row = None
                if final_stop_name:
                    final_name_row = con.execute(
                        "SELECT name FROM stops WHERE ref = ? LIMIT 1",
                        (final_stop_name,),
                    ).fetchone()

                mode = (row['mode'] or '').strip().lower()
                if mode == 'rail':
                    mode = 'train'

                candidates.append({
                    'service': (row['service'] or '').strip(),
                    'mode': mode or 'bus',
                    'arrivalAtStop': _minutes_to_clock(event_abs),
                    'arrivalAtFinalDestination': _minutes_to_clock(final_arrival_abs),
                    'finalDestination': (final_name_row['name'] if final_name_row and final_name_row['name'] else str(final_stop_name or '')),
                    '_sort': event_abs,
                })
    except Exception as e:
        app.logger.error(f"Stop services error for {atco_code}: {e}")
        return jsonify({'stop': stop_meta, 'services': []})

    deduped = []
    seen = set()
    for item in sorted(candidates, key=lambda x: (x['_sort'], x['service'], x['finalDestination'])):
        key = (item['service'], item['mode'], item['arrivalAtStop'], item['finalDestination'])
        if key in seen:
            continue
        seen.add(key)
        payload = dict(item)
        payload.pop('_sort', None)
        deduped.append(payload)
        if len(deduped) >= limit:
            break

    return jsonify({'stop': stop_meta, 'services': deduped})


@app.route('/api/routes/search', methods=['POST'])
def search_routes():
    """Search for routes between two stops using SCC transport API data.

    Bus legs are timetable-derived from SCC /bus/times datasets and rail
    legs are derived from SCC /rail/departures scheduled calling points.
    """
    try:
        data = request.get_json(silent=True) or {}
        from_stop = data.get('from', {})
        to_stop = data.get('to', {})

        # Validate both stops are provided
        if not from_stop or not to_stop:
            return jsonify({"error": "Both 'from' and 'to' stops are required"}), 400

        from_name = from_stop.get('name', '').strip()
        to_name = to_stop.get('name', '').strip()
        if not from_name or not to_name:
            return jsonify({"error": "Stop names are required"}), 400

        from_stop_code = (from_stop.get('atcoCode') or from_stop.get('ATCOCode') or '').strip()
        to_stop_code = (to_stop.get('atcoCode') or to_stop.get('ATCOCode') or '').strip()

        sort_by = (data.get('sort_by') or 'soonest_arrival').strip().lower()
        if sort_by not in {'soonest_arrival', 'fewest_changes'}:
            return jsonify({"error": "Invalid sort_by. Use 'soonest_arrival' or 'fewest_changes'."}), 400
        depart_time = (data.get('departTime') or data.get('depart_time') or '').strip() or None

        # Extract coordinates for distance-aware route generation
        from_lat = from_stop.get('lat') or from_stop.get('latitude')
        from_lon = from_stop.get('lon') or from_stop.get('longitude')
        to_lat = to_stop.get('lat') or to_stop.get('latitude')
        to_lon = to_stop.get('lon') or to_stop.get('longitude')

        # Prefer exact coordinates from selected ATCO codes when available.
        exact_from = _resolve_stop_by_atco(from_stop_code) if from_stop_code else None
        exact_to = _resolve_stop_by_atco(to_stop_code) if to_stop_code else None
        if from_stop_code and exact_from is None:
            return jsonify({
                "error": "Selected origin stop code could not be resolved. Please re-select origin."
            }), 422
        if to_stop_code and exact_to is None:
            return jsonify({
                "error": "Selected destination stop code could not be resolved. Please re-select destination."
            }), 422

        if exact_from:
            from_lat, from_lon = exact_from['lat'], exact_from['lon']
            from_name = exact_from['name']
        if exact_to:
            to_lat, to_lon = exact_to['lat'], exact_to['lon']
            to_name = exact_to['name']

        # Convert to float if present
        try:
            from_lat = float(from_lat) if from_lat is not None else None
            from_lon = float(from_lon) if from_lon is not None else None
            to_lat = float(to_lat) if to_lat is not None else None
            to_lon = float(to_lon) if to_lon is not None else None
        except (ValueError, TypeError):
            from_lat = from_lon = to_lat = to_lon = None

        # If coordinates are missing (e.g. saved route names), try resolving
        # from the local stop cache.
        if from_lat is None or from_lon is None:
            from_lat, from_lon = _resolve_stop_coordinates(from_name)
        if to_lat is None or to_lon is None:
            to_lat, to_lon = _resolve_stop_coordinates(to_name)

        if from_lat is None or from_lon is None or to_lat is None or to_lon is None:
            return jsonify({
                "error": "Could not resolve stop coordinates. Please select both stops from autocomplete suggestions."
            }), 422

        app.logger.info(
            f"Route search: {from_name} → {to_name}  "
            f"({from_lat},{from_lon}) → ({to_lat},{to_lon})"
        )

        routes_data = transport_service.get_routes(
            from_name, to_name,
            from_lat=from_lat, from_lon=from_lon,
            to_lat=to_lat, to_lon=to_lon,
            from_stop_code=from_stop_code or None,
            to_stop_code=to_stop_code or None,
            depart_time=depart_time,
            sort_by=sort_by,
        )
        routes = routes_data.get('routes', [])
        metrics = routes_data.get('metrics', {})

        app.logger.info(f"Bus stops processed: {int(metrics.get('bus_stops_processed', 0))}")
        app.logger.info(f"Train stations processed: {int(metrics.get('train_stations_processed', 0))}")

        if not routes:
            routes = _generate_valid_mock_routes(
                from_name,
                to_name,
                from_lat=from_lat,
                from_lon=from_lon,
                to_lat=to_lat,
                to_lon=to_lon,
            )

        if not routes:
            return jsonify({
                "error": "No valid public transport routes found for this journey right now. Try different stops or time."
            }), 404

        app.logger.info(f"Route planner returned {len(routes)} routes")

        return jsonify({
            "from": from_name,
            "to": to_name,
            "sort_by": sort_by,
            "routes": routes,
            "timestamp": datetime.utcnow().isoformat()
        }), 200

    except Exception as e:
        app.logger.error(f"Route search error: {e}")
        return jsonify({"error": str(e)}), 500


@app.route('/api/routes/search-v2', methods=['POST'])
def search_routes_v2():
    """Search routes via provider-agnostic RouteAggregator with timeline metadata."""
    if not app.config.get("ENABLE_INTERMODAL_TIMELINE_V2", True):
        return jsonify({"error": "Route timeline v2 is disabled"}), 404
    try:
        data = request.get_json(silent=True) or {}
        from_stop = data.get('from', {})
        to_stop = data.get('to', {})
        if not from_stop or not to_stop:
            return jsonify({"error": "Both 'from' and 'to' stops are required"}), 400

        from_name = from_stop.get('name', '').strip()
        to_name = to_stop.get('name', '').strip()
        if not from_name or not to_name:
            return jsonify({"error": "Stop names are required"}), 400

        from_stop_code = (from_stop.get('atcoCode') or from_stop.get('ATCOCode') or '').strip()
        to_stop_code = (to_stop.get('atcoCode') or to_stop.get('ATCOCode') or '').strip()

        sort_by = (data.get('sort_by') or 'soonest_arrival').strip().lower()
        if sort_by not in {'soonest_arrival', 'fewest_changes'}:
            return jsonify({"error": "Invalid sort_by. Use 'soonest_arrival' or 'fewest_changes'."}), 400
        depart_time = (data.get('departTime') or data.get('depart_time') or '').strip() or None

        from_lat = from_stop.get('lat') or from_stop.get('latitude')
        from_lon = from_stop.get('lon') or from_stop.get('longitude')
        to_lat = to_stop.get('lat') or to_stop.get('latitude')
        to_lon = to_stop.get('lon') or to_stop.get('longitude')

        exact_from = _resolve_stop_by_atco(from_stop_code) if from_stop_code else None
        exact_to = _resolve_stop_by_atco(to_stop_code) if to_stop_code else None
        if from_stop_code and exact_from is None:
            return jsonify({
                "error": "Selected origin stop code could not be resolved. Please re-select origin."
            }), 422
        if to_stop_code and exact_to is None:
            return jsonify({
                "error": "Selected destination stop code could not be resolved. Please re-select destination."
            }), 422

        if exact_from:
            from_lat, from_lon = exact_from['lat'], exact_from['lon']
            from_name = exact_from['name']
        if exact_to:
            to_lat, to_lon = exact_to['lat'], exact_to['lon']
            to_name = exact_to['name']

        try:
            from_lat = float(from_lat) if from_lat is not None else None
            from_lon = float(from_lon) if from_lon is not None else None
            to_lat = float(to_lat) if to_lat is not None else None
            to_lon = float(to_lon) if to_lon is not None else None
        except (ValueError, TypeError):
            from_lat = from_lon = to_lat = to_lon = None

        if from_lat is None or from_lon is None:
            from_lat, from_lon = _resolve_stop_coordinates(from_name)
        if to_lat is None or to_lon is None:
            to_lat, to_lon = _resolve_stop_coordinates(to_name)

        if from_lat is None or from_lon is None or to_lat is None or to_lon is None:
            return jsonify({
                "error": "Could not resolve stop coordinates. Please select both stops from autocomplete suggestions."
            }), 422

        modes = data.get("modes") or []
        if not isinstance(modes, list):
            modes = []
        prefer_reliability = bool(data.get("prefer_reliability") or False)
        max_walk_meters = data.get("max_walk_meters")
        try:
            max_walk_meters = int(max_walk_meters) if max_walk_meters is not None else None
        except (ValueError, TypeError):
            max_walk_meters = None

        payload = transport_service.get_routes_v2(
            from_name, to_name,
            from_lat=from_lat, from_lon=from_lon,
            to_lat=to_lat, to_lon=to_lon,
            from_stop_code=from_stop_code or None,
            to_stop_code=to_stop_code or None,
            depart_time=depart_time,
            sort_by=sort_by,
            modes=modes,
            prefer_reliability=prefer_reliability,
            max_walk_meters=max_walk_meters,
        )
        return jsonify(payload), 200
    except Exception:
        app.logger.exception("Route search v2 error")
        return jsonify({"error": "Unable to complete route search right now."}), 500


@app.route('/api/routes/metrics', methods=['GET'])
def route_processing_metrics():
    """Return latest backend route-planning stop/station processing metrics."""
    try:
        return jsonify(transport_service.get_route_processing_metrics())
    except Exception as e:
        app.logger.error(f"Route metrics error: {e}")
        return jsonify({"error": "Unable to fetch route processing metrics"}), 500

@app.route('/api/bus/timetable/<bus_code>')
def bus_timetable(bus_code):
    try:
        data = transport_service.get_bus_timetable(bus_code)
        return jsonify(data)
    except Exception as e:
        app.logger.error(f"Bus timetable error: {e}")
        return jsonify({"error": str(e)}), 500


@app.route('/api/bus/live/<bus_code>')
def bus_live(bus_code):
    try:
        data = transport_service.get_bus_live(bus_code)
        return jsonify(data)
    except Exception as e:
        app.logger.error(f"Bus live error: {e}")
        return jsonify({"error": str(e)}), 500


@app.route('/api/rail/corpus')
def rail_corpus():
    try:
        data = transport_service.get_rail_corpus()
        return jsonify(data)
    except Exception as e:
        app.logger.error(f"Rail corpus error: {e}")
        return jsonify({"error": str(e)}), 500


@app.route('/api/rail/departures/<crs_code>')
def rail_departures(crs_code):
    """Get real-time rail departures for a station by CRS code."""
    try:
        data = transport_service.get_rail_departures(crs_code.upper())
        return jsonify(data)
    except Exception as e:
        app.logger.error(f"Rail departures error: {e}")
        return jsonify({"error": str(e)}), 500


@app.route('/api/translate/train_event', methods=['POST'])
def translate_train_event():
    try:
        event = request.json
        translated = data_translator.translate_train_event(event)
        return jsonify(translated)
    except Exception as e:
        app.logger.error(f"Translate train event error: {e}")
        return jsonify({"error": str(e)}), 500


@app.route('/api/weather/search')
def weather_search():
    """
    Search for locations by name within the map bounds and return weather data.
    Uses the NPTG gazetteer for location lookup.
    Query params:
        q: search string (min 2 chars)
        limit: max results (default 10, max 20)
    """
    try:
        query = request.args.get('q', '').strip().lower()
        limit = min(int(request.args.get('limit', 10)), 20)

        if not query or len(query) < 2:
            return jsonify({"results": []})

        # Map bounds (matches frontend maxBounds)
        MIN_LAT, MAX_LAT = 53.0, 55.2
        MIN_LON, MAX_LON = -3.7, -1.9

        # Fetch gazetteer data (NPTG locality list)
        gazetteer = transport_service.get_gazetteer()

        # Filter locations within bounds whose name starts with or contains the query
        matching = []
        seen_names = set()
        for entry in gazetteer:
            name = entry.get('LocalityName', '')
            lat = entry.get('Latitude')
            lon = entry.get('Longitude')
            if not name or lat is None or lon is None:
                continue
            try:
                lat = float(lat)
                lon = float(lon)
            except (ValueError, TypeError):
                continue
            if not (MIN_LAT <= lat <= MAX_LAT and MIN_LON <= lon <= MAX_LON):
                continue

            # Check if location name matches (case-insensitive)
            name_lower = name.lower()
            if query not in name_lower:
                continue

            # Deduplicate by name (some localities appear multiple times)
            if name_lower in seen_names:
                continue
            seen_names.add(name_lower)

            matching.append({
                'name': name,
                'lat': lat,
                'lon': lon,
            })

            if len(matching) >= limit:
                break

        # Sort: names starting with query first, then alphabetical
        matching.sort(key=lambda m: (0 if m['name'].lower().startswith(query) else 1, m['name']))

        # Fetch weather for each matching location
        results = []
        for loc in matching:
            weather_data = transport_service.get_weather(loc['lat'], loc['lon'])
            results.append({
                'name': loc['name'],
                'lat': loc['lat'],
                'lon': loc['lon'],
                'weather': weather_data,
            })

        return jsonify({"results": results})
    except Exception as e:
        app.logger.error(f"Weather search error: {e}")
        return jsonify({"error": str(e)}), 500


@app.route('/api/weather')
def weather():
    try:
        lat = request.args.get('lat', type=float)
        lon = request.args.get('lon', type=float)
        
        if lat is None or lon is None:
            return jsonify({"error": "Missing latitude and/or longitude parameters"}), 400
        
        data = transport_service.get_weather(lat, lon)
        return jsonify(data)
    except ValueError:
        return jsonify({"error": "Invalid latitude or longitude format"}), 400
    except Exception as e:
        app.logger.error(f"Weather error: {e}")
        return jsonify({"error": str(e)}), 500


@app.route('/api/weather/route', methods=['POST'])
@auth_required
def weather_for_route():
    """
    Get weather data for multiple locations along a route.
    
    Input: {
        "route_points": [
            {"latitude": 54.05, "longitude": -2.80, "name": "Lancaster"},
            {"latitude": 53.48, "longitude": -2.24, "name": "Manchester"},
            ...
        ]
    }
    
    Returns: Array of weather data for each point
    """
    try:
        data = request.get_json(silent=True) or {}
        route_points = data.get("route_points", [])
        
        if not route_points or not isinstance(route_points, list):
            return jsonify({"error": "Missing or invalid route_points array"}), 400
        
        weather_for_route = []
        for point in route_points:
            lat = point.get("latitude")
            lon = point.get("longitude")
            name = point.get("name", f"({lat}, {lon})")
            
            if lat is None or lon is None:
                weather_for_route.append({
                    "name": name,
                    "error": "Missing latitude/longitude"
                })
                continue
            
            weather_data = transport_service.get_weather(lat, lon)
            weather_for_route.append({
                "location_name": name,
                "weather": weather_data
            })
        
        return jsonify({
            "user_id": g.current_user.id,
            "weather_along_route": weather_for_route,
            "note": "Weather data is binned by area due to API rate limits. Multiple nearby points may return identical data."
        }), 200
    except ValueError:
        return jsonify({"error": "Invalid latitude or longitude format"}), 400
    except Exception as e:
        app.logger.error(f"Weather for route error: {e}")
        return jsonify({"error": str(e)}), 500


@app.route('/api/weather/icon/<icon_code>')
def weather_icon(icon_code: str):
    try:
        icon_data = transport_service.weather.get_weather_icon(icon_code)
        if not icon_data:
            return jsonify({"error": "Icon not found"}), 404
        return icon_data, 200, {"Content-Type": "image/png"}
    except Exception as e:
        app.logger.error(f"Weather icon error: {e}")
        return jsonify({"error": str(e)}), 500


# Serve frontend index.html at root
@app.route("/")
def serve_index():
    return send_from_directory(app.static_folder, "index.html")


# Catch-all for frontend routes (SPA support)
@app.route("/<path:path>")
def serve_static(path):
    # Don't intercept API routes
    if path.startswith("api/"):
        return jsonify({"error": "Not found"}), 404
    # Try to serve the file, fallback to index.html
    file_path = Path(app.static_folder) / path
    if file_path.exists():
        return send_from_directory(app.static_folder, path)
    return send_from_directory(app.static_folder, "index.html")


def _ensure_sqlite_user_accessibility_columns():
    """Add new user profile columns for existing SQLite databases.
    db.create_all() does not alter existing tables, so we perform a lightweight
    schema check and issue ALTER TABLE for any missing columns."""
    db_uri = app.config.get("SQLALCHEMY_DATABASE_URI", "") or ""
    if not db_uri.startswith("sqlite"):
        return

    with db.engine.begin() as connection:
        rows = connection.execute(text('PRAGMA table_info("User")')).fetchall()
        existing = {row[1] for row in rows}

        if "accessibilitymode" not in existing:
            connection.execute(
                text('ALTER TABLE "User" ADD COLUMN accessibilitymode VARCHAR(40) NOT NULL DEFAULT "none"')
            )
            app.logger.info("Added User.accessibilitymode column")

        if "accessibilityzoom" not in existing:
            connection.execute(
                text('ALTER TABLE "User" ADD COLUMN accessibilityzoom FLOAT NOT NULL DEFAULT 1.0')
            )
            app.logger.info("Added User.accessibilityzoom column")
        if "accessibilityfontsize" not in existing:
            connection.execute(
                text('ALTER TABLE "User" ADD COLUMN accessibilityfontsize VARCHAR(20) NOT NULL DEFAULT "normal"')
            )
            app.logger.info("Added User.accessibilityfontsize column")


def _ensure_sqlite_user_admin_column():
    """Add the admin flag column for existing SQLite databases."""
    db_uri = app.config.get("SQLALCHEMY_DATABASE_URI", "") or ""
    if not db_uri.startswith("sqlite"):
        return

    with db.engine.begin() as connection:
        rows = connection.execute(text('PRAGMA table_info("User")')).fetchall()
        existing = {row[1] for row in rows}

        if "is_admin" not in existing:
            connection.execute(
                text('ALTER TABLE "User" ADD COLUMN is_admin BOOLEAN NOT NULL DEFAULT 0')
            )
            app.logger.info("Added User.is_admin column")


# Database tables – created on first run.
# Using /tmp for SQLite to avoid network-drive locking issues.
with app.app_context():
    db_uri_for_startup = app.config.get("SQLALCHEMY_DATABASE_URI", "") or ""
    if db_uri_for_startup.startswith("sqlite"):
        try:
            app.logger.info("Creating database tables (sqlite)")
            db.create_all()
            _ensure_sqlite_user_accessibility_columns()
            _ensure_sqlite_user_admin_column()
            _ensure_internal_admin_account()
        except Exception as e:
            app.logger.exception(f"db.create_all (sqlite) failed: {e}")
    else:
        app.logger.info("Skipping automatic db.create_all for non-sqlite database at startup")
        _ensure_internal_admin_account()


# ---------------------------------------------------------------------------
# Background stop-cache loader
# ---------------------------------------------------------------------------
def _load_stop_cache():
    """Fetch NaPTAN stops from SCC datasets and insert them into StopCache.
    Intended for explicit/manual refresh flows.
    """
    global _stop_cache_ready
    with app.app_context():
        try:
            with _stop_cache_lock:
                _stop_cache_ready = False

            # Map bounds (matches frontend maxBounds)
            MIN_LAT, MAX_LAT = 53.0, 55.2
            MIN_LON, MAX_LON = -3.7, -1.9

            # ---- 1. Fetch from SCC NaPTAN datasets ----
            datasets = ['lancashire', 'north_west_rail']
            all_stops = []
            seen_codes = set()
            for dataset in datasets:
                try:
                    app.logger.info(f"StopCache: Fetching NaPTAN dataset '{dataset}' …")
                    naptan_data = transport_service.get_naptan(dataset=dataset)
                    raw = naptan_data.get("stops", []) if isinstance(naptan_data, dict) else naptan_data
                    for stop in (raw or []):
                        code = stop.get("ATCOCode", "")
                        if code and code in seen_codes:
                            continue
                        if code:
                            seen_codes.add(code)
                        all_stops.append(stop)
                    app.logger.info(f"StopCache: dataset '{dataset}' cumulative unique stops = {len(all_stops)}")
                except Exception as api_err:
                    app.logger.warning(f"StopCache: dataset '{dataset}' fetch failed – {api_err}")

            # Use full UK dataset only when the smaller datasets produced very
            # limited results, keeping startup faster in normal operation.
            if len(all_stops) < 1000:
                try:
                    app.logger.info("StopCache: supplementing with dataset 'full' …")
                    naptan_data = transport_service.get_naptan(dataset='full')
                    raw = naptan_data.get("stops", []) if isinstance(naptan_data, dict) else naptan_data
                    for stop in (raw or []):
                        code = stop.get("ATCOCode", "")
                        if code and code in seen_codes:
                            continue
                        if code:
                            seen_codes.add(code)
                        all_stops.append(stop)
                    app.logger.info(f"StopCache: after 'full' dataset unique stops = {len(all_stops)}")
                except Exception as api_err:
                    app.logger.warning(f"StopCache: dataset 'full' fetch failed – {api_err}")

            # Always merge packaged supplemental stops so local DB still has
            # a useful baseline even when upstream API feeds are unavailable.
            try:
                supplemental = transport_service.naptan._get_supplemental_stops()
                for stop in supplemental:
                    code = stop.get("ATCOCode", "")
                    if code and code in seen_codes:
                        continue
                    if code:
                        seen_codes.add(code)
                    all_stops.append(stop)
                app.logger.info(
                    f"StopCache: after supplemental merge unique stops = {len(all_stops)}"
                )
            except Exception as supp_err:
                app.logger.warning(f"StopCache: supplemental stop merge failed – {supp_err}")

            app.logger.info(f"StopCache: {len(all_stops)} unique stops after merge")

            # ---- 3. Wipe previous cache and bulk-insert ----
            db.session.query(StopCache).delete()
            db.session.flush()

            inserted = 0
            for stop in all_stops:
                lat = stop.get("Latitude")
                lon = stop.get("Longitude")
                if lat is None or lon is None:
                    continue
                try:
                    lat = float(lat)
                    lon = float(lon)
                except (ValueError, TypeError):
                    continue
                if not (MIN_LAT <= lat <= MAX_LAT and MIN_LON <= lon <= MAX_LON):
                    continue

                common_name = stop.get("CommonName", "")
                indicator = stop.get("Indicator", "")
                locality_name = stop.get("LocalityName", "")

                # Build a searchable text blob (lowercase) used by the query
                search_text = f"{common_name} {indicator} {locality_name}".lower()

                db.session.add(StopCache(
                    atco_code=stop.get("ATCOCode", ""),
                    naptan_code=stop.get("NaptanCode", ""),
                    common_name=common_name,
                    indicator=indicator,
                    locality_name=locality_name,
                    latitude=lat,
                    longitude=lon,
                    stop_type=stop.get("StopType", "bus"),
                    search_text=search_text,
                ))
                inserted += 1

            db.session.commit()

            with _stop_cache_lock:
                _stop_cache_ready = True

            app.logger.info(f"StopCache: Successfully loaded {inserted} stops into database")
            return {"inserted": inserted, "ready": True}
        except Exception as exc:
            app.logger.error(f"StopCache: Background load failed – {exc}")
            db.session.rollback()
            with _stop_cache_lock:
                _stop_cache_ready = False
            return {"inserted": 0, "ready": False, "error": str(exc)}


def _warm_route_planner_cache():
    """Warm expensive SCC-backed route planner caches in background."""
    try:
        planner = transport_service.route_planner
        planner._fetch_bus_times_index()
        planner._load_naptan_lookup()
        # Warm a small set of representative timetable datasets so the first
        # user route query is not blocked on full TransXChange parsing.
        now_utc = datetime.utcnow()
        warm_pairs = [
            ("Lancaster", "Preston"),
            ("Lancaster", "Manchester"),
        ]
        seen = set()
        for frm, to in warm_pairs:
            for ds in planner._select_bus_timetable_datasets(frm, to, now_utc)[:2]:
                ds_id = ds.get('id')
                if not ds_id or ds_id in seen:
                    continue
                seen.add(ds_id)
                planner._parse_timetable_dataset(ds)
        app.logger.info("RoutePlanner: cache warm-up completed")
    except Exception as exc:
        app.logger.warning(f"RoutePlanner: cache warm-up skipped ({exc})")


def _set_stop_cache_ready_from_db():
    """Set in-memory cache-ready flag from current DB table contents."""
    global _stop_cache_ready
    with app.app_context():
        try:
            count = StopCache.query.count()
        except Exception:
            count = 0
    with _stop_cache_lock:
        _stop_cache_ready = count > 0
    app.logger.info(f"StopCache: ready={_stop_cache_ready} rows={count}")


def refresh_static_data(force_rebuild_index=False, warm_route_cache=False):
    """Refresh static transport datasets (stops + timetable index) on demand."""
    stop_result = _load_stop_cache()
    index_result = transport_service.route_planner.build_connection_index(
        force_rebuild=force_rebuild_index
    )
    if warm_route_cache:
        _warm_route_planner_cache()
    return {
        "stops": stop_result,
        "index": index_result,
    }


# Static data is command-driven by default. Startup auto-refresh is optional.
_set_stop_cache_ready_from_db()
if app.config.get("AUTO_REFRESH_STATIC_ON_STARTUP"):
    _stop_loader_thread = threading.Thread(target=_load_stop_cache, daemon=True)
    _stop_loader_thread.start()
    _route_warm_thread = threading.Thread(target=_warm_route_planner_cache, daemon=True)
    _route_warm_thread.start()
else:
    app.logger.info(
        "Static transport data auto-refresh disabled on startup; use terminal refresh commands."
    )


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
