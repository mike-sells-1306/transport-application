import os
import threading
from datetime import datetime
from functools import wraps
from pathlib import Path

from flask import Flask, g, jsonify, request, send_from_directory
from flask_sqlalchemy import SQLAlchemy
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer
from services.data_translator import DataTranslator
from services.transport_service import TransportService
from sqlalchemy import UniqueConstraint, event
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
app.config["SQLALCHEMY_DATABASE_URI"] = os.getenv("DATABASE_URL", "sqlite:///transport.db")
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.config["AUTH_TOKEN_MAX_AGE_SECONDS"] = int(os.getenv("AUTH_TOKEN_MAX_AGE_SECONDS", "86400"))
# Increase SQLite timeout for network drive compatibility
app.config["SQLALCHEMY_ENGINE_OPTIONS"] = {
    "connect_args": {"timeout": 30},
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


def _serialize_user(user: User):
    return {
        "id": user.id,
        "email": user.email,
        "userName": user.username,
        "colorblindmode": user.colorblind_mode,
    }


def _json_error(message: str, status: int = 400):
    return jsonify({"error": message}), status


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
    return jsonify({"status": "ok"})


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

    user = User(email=email, username=username, password_hash=generate_password_hash(password))
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
        full = request.args.get('full', 'false').lower() == 'true'
        data = transport_service.get_naptan(full=full)
        return jsonify(data)
    except Exception as e:
        app.logger.error(f"NaPTAN error: {e}")
        return jsonify({"error": str(e)}), 500


@app.route('/api/stops/search')
def search_stops():
    """Search for bus and train stops within map bounds with autocomplete support.
    Uses the local StopCache database when available, falling back to the live
    NaPTAN API if the cache has not finished loading yet.
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

        # ---------- Try the database cache first ----------
        global _stop_cache_ready
        if _stop_cache_ready:
            app.logger.info(f"Searching stop cache DB for: {query}")
            try:
                # Build SQLAlchemy filter: every word must appear in search_text
                filters = [
                    StopCache.latitude >= MIN_LAT,
                    StopCache.latitude <= MAX_LAT,
                    StopCache.longitude >= MIN_LON,
                    StopCache.longitude <= MAX_LON,
                ]
                for word in query_words:
                    filters.append(StopCache.search_text.contains(word))

                results = (
                    StopCache.query
                    .filter(*filters)
                    .limit(limit)
                    .all()
                )

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

                app.logger.info(f"Returning {len(matching_stops)} stops from DB cache for '{query}'")
                return jsonify({"stops": matching_stops})
            except Exception as db_err:
                app.logger.warning(f"StopCache query failed, falling back to API: {db_err}")

        # ---------- Fallback: live API fetch (same as original) ----------
        app.logger.info(f"Cache not ready, fetching NaPTAN data for query: {query}")
        naptan_data = transport_service.get_naptan(full=False)
        stops_list = naptan_data.get('stops', []) if isinstance(naptan_data, dict) else naptan_data

        matching_stops = []
        if stops_list:
            for stop in stops_list:
                lat = stop.get('Latitude')
                lon = stop.get('Longitude')
                if lat is None or lon is None:
                    continue
                try:
                    lat = float(lat)
                    lon = float(lon)
                except (ValueError, TypeError):
                    continue
                if not (MIN_LAT <= lat <= MAX_LAT and MIN_LON <= lon <= MAX_LON):
                    continue

                stop_name = stop.get('CommonName', '').lower()
                stop_locality = stop.get('LocalityName', '').lower()
                combined = f"{stop_name} {stop_locality}"

                # Word-order-independent matching
                if all(w in combined for w in query_words):
                    display_name = stop.get('CommonName', '')
                    stop_indicator = stop.get('Indicator', '')
                    stop_locality_raw = stop.get('LocalityName', '')
                    if stop_indicator:
                        display_name += f" ({stop_indicator})"
                    if stop_locality_raw and stop_locality_raw not in display_name:
                        display_name += f", {stop_locality_raw}"
                    matching_stops.append({
                        'name': display_name,
                        'atcoCode': stop.get('ATCOCode', ''),
                        'lat': lat,
                        'lon': lon,
                        'stopType': stop.get('StopType', 'bus'),
                    })
                if len(matching_stops) >= limit:
                    break

        app.logger.info(f"Returning {len(matching_stops)} stops (API fallback) for '{query}'")
        return jsonify({"stops": matching_stops})

    except Exception as e:
        app.logger.error(f"Stop search error: {e}")
        return jsonify({"error": str(e), "stops": []}), 500


def _generate_valid_mock_routes(from_stop, to_stop, from_lat=None, from_lon=None,
                                to_lat=None, to_lon=None):
    """Generate realistic mock routes based on distance between stops.

    Uses Haversine distance to decide which transport modes are plausible:
      • < 1 km   → walk-only options
      • 1–5 km   → single local bus + walk-only
      • 5–15 km  → bus (possibly with one change)
      • > 15 km  → bus and / or train combinations

    Departure times are anchored to the current clock time so results
    always look fresh.

    Leg schema
    ----------
    Walking leg::

        {
            "mode": "walk",
            "from_stop": "...",
            "to_stop": "...",
            "depart": "HH:MM",
            "arrive": "HH:MM",
            "duration_mins": int,
            "distance_m": int
        }

    Transport leg::

        {
            "mode": "bus" | "train",
            "service": "Stagecoach 1A",
            "from_stop": "...",
            "to_stop": "...",
            "depart": "HH:MM",
            "arrive": "HH:MM",
            "duration_mins": int,
            "intermediate_stops": [{"name": "...", "time": "HH:MM"}, ...]
        }
    """
    import math, random
    from datetime import datetime as _dt

    # ------------------------------------------------------------------
    # Haversine distance (km)
    # ------------------------------------------------------------------
    def _haversine(lat1, lon1, lat2, lon2):
        R = 6371.0
        la1, lo1, la2, lo2 = map(math.radians, [lat1, lon1, lat2, lon2])
        dlat = la2 - la1
        dlon = lo2 - lo1
        a = math.sin(dlat / 2) ** 2 + math.cos(la1) * math.cos(la2) * math.sin(dlon / 2) ** 2
        return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

    # ------------------------------------------------------------------
    # Time helpers
    # ------------------------------------------------------------------
    def _fmt(total_mins):
        """Minutes since midnight → 'HH:MM'"""
        h = (total_mins // 60) % 24
        m = total_mins % 60
        return f"{h:02d}:{m:02d}"

    def _walk(frm, to, depart_mins, walk_mins, dist_m):
        return {
            "mode": "walk",
            "from_stop": frm,
            "to_stop": to,
            "depart": _fmt(depart_mins),
            "arrive": _fmt(depart_mins + walk_mins),
            "duration_mins": walk_mins,
            "distance_m": dist_m,
        }

    def _ride(mode, service, frm, to, depart_mins, arrive_mins, intermediates=None):
        return {
            "mode": mode,
            "service": service,
            "from_stop": frm,
            "to_stop": to,
            "depart": _fmt(depart_mins),
            "arrive": _fmt(arrive_mins),
            "duration_mins": arrive_mins - depart_mins,
            "intermediate_stops": intermediates or [],
        }

    def _summarise(legs):
        transport_modes = []
        changes = 0
        prev_was_ride = False
        for leg in legs:
            if leg["mode"] in ("bus", "train"):
                if leg["mode"] not in transport_modes:
                    transport_modes.append(leg["mode"])
                if prev_was_ride:
                    changes += 1
                prev_was_ride = True
            else:
                prev_was_ride = False
        sh, sm = map(int, legs[0]["depart"].split(":"))
        eh, em = map(int, legs[-1]["arrive"].split(":"))
        duration = (eh * 60 + em) - (sh * 60 + sm)
        return {
            "start_time": legs[0]["depart"],
            "end_time": legs[-1]["arrive"],
            "duration_mins": duration,
            "transport": transport_modes,
            "changes": changes,
            "legs": legs,
        }

    # ------------------------------------------------------------------
    # Calculate distance between stops
    # ------------------------------------------------------------------
    if from_lat is not None and to_lat is not None:
        dist_km = _haversine(from_lat, from_lon, to_lat, to_lon)
    else:
        # Fallback: guess a medium distance if coordinates not supplied
        dist_km = 8.0

    # ------------------------------------------------------------------
    # Real bus services by area / corridor
    # ------------------------------------------------------------------
    lancaster_local_services = [
        ("Stagecoach 1", [
            {"name": "Common Garden Street (Stop A), Lancaster", "offset_frac": 0.3},
            {"name": "Lancaster Bus Station", "offset_frac": 0.5},
            {"name": "Lancaster University", "offset_frac": 0.8},
        ]),
        ("Stagecoach 1A", [
            {"name": "Lancaster Bus Station", "offset_frac": 0.35},
            {"name": "Hala", "offset_frac": 0.6},
            {"name": "Lancaster University", "offset_frac": 0.85},
        ]),
        ("Stagecoach 4", [
            {"name": "Lancaster Bus Station", "offset_frac": 0.3},
            {"name": "Scale Hall", "offset_frac": 0.6},
            {"name": "Heysham", "offset_frac": 0.9},
        ]),
    ]

    lancaster_regional_services = [
        ("Stagecoach 100", [
            {"name": "Lancaster Bus Station", "offset_frac": 0.15},
            {"name": "Lancaster University", "offset_frac": 0.3},
            {"name": "Carnforth", "offset_frac": 0.55},
            {"name": "Morecambe Bus Station", "offset_frac": 0.85},
        ]),
        ("Stagecoach 41", [
            {"name": "Lancaster Bus Station", "offset_frac": 0.1},
            {"name": "Garstang", "offset_frac": 0.4},
            {"name": "Preston Bus Station", "offset_frac": 0.85},
        ]),
        ("Stagecoach 42", [
            {"name": "Lancaster Bus Station", "offset_frac": 0.1},
            {"name": "Galgate", "offset_frac": 0.3},
            {"name": "Garstang", "offset_frac": 0.5},
            {"name": "Preston Bus Station", "offset_frac": 0.85},
        ]),
    ]

    inter_city_services = [
        ("Stagecoach 40", [
            {"name": "Lancaster Bus Station", "offset_frac": 0.1},
            {"name": "Garstang", "offset_frac": 0.35},
            {"name": "Preston Bus Station", "offset_frac": 0.7},
        ]),
        ("Service 555", [
            {"name": "Lancaster Bus Station", "offset_frac": 0.1},
            {"name": "Carnforth", "offset_frac": 0.3},
            {"name": "Kendal Bus Station", "offset_frac": 0.6},
            {"name": "Windermere", "offset_frac": 0.85},
        ]),
    ]

    train_services = [
        ("Northern Rail", [
            {"name": "Lancaster Railway Station", "offset_frac": 0.15},
            {"name": "Carnforth Railway Station", "offset_frac": 0.35},
            {"name": "Kendal Railway Station", "offset_frac": 0.65},
            {"name": "Windermere Railway Station", "offset_frac": 0.9},
        ]),
        ("Avanti West Coast", [
            {"name": "Lancaster Railway Station", "offset_frac": 0.1},
            {"name": "Preston Railway Station", "offset_frac": 0.4},
            {"name": "Wigan North Western", "offset_frac": 0.65},
            {"name": "Manchester Piccadilly", "offset_frac": 0.9},
        ]),
        ("TransPennine Express", [
            {"name": "Lancaster Railway Station", "offset_frac": 0.15},
            {"name": "Preston Railway Station", "offset_frac": 0.45},
            {"name": "Manchester Airport", "offset_frac": 0.85},
        ]),
    ]

    # ------------------------------------------------------------------
    # Determine base time (anchor to the current clock, rounded down to
    # nearest 5 minutes, then generate departures over the next ~2 hours)
    # ------------------------------------------------------------------
    now = _dt.now()
    base_mins = now.hour * 60 + (now.minute // 5) * 5  # rounded down to 5-min mark

    random.seed(hash(from_stop + to_stop + str(now.hour)) % 2**32)

    # ------------------------------------------------------------------
    # Choose which service pool to draw from based on distance
    # ------------------------------------------------------------------
    routes = []

    # Walking speed: ~80 m/min  ≈ 4.8 km/h
    walk_speed_m_per_min = 80

    if dist_km < 1.0:
        # ------- Very short: walk-only options ---------
        walk_m = int(dist_km * 1000)
        walk_mins = max(3, int(walk_m / walk_speed_m_per_min))

        for offset in [5, 10, 15]:
            dep = base_mins + offset
            routes.append(_summarise([
                _walk(from_stop, to_stop, dep, walk_mins, walk_m),
            ]))

        # One bus option (if a bus happens to pass)
        svc_name, intermediates = random.choice(lancaster_local_services)
        dep = base_mins + 8
        walk1 = 2
        ride_dur = max(3, walk_mins - 1)
        routes.append(_summarise([
            _walk(from_stop, f"Nearest bus stop", dep, walk1, 120),
            _ride("bus", svc_name, "Nearest bus stop", f"Nearest bus stop to destination",
                  dep + walk1, dep + walk1 + ride_dur, []),
            _walk(f"Nearest bus stop to destination", to_stop,
                  dep + walk1 + ride_dur, 2, 100),
        ]))

    elif dist_km < 5.0:
        # ------- Short-medium: local bus routes ---------
        walk_m = int(dist_km * 1000)
        walk_mins = max(5, int(walk_m / walk_speed_m_per_min))

        # Walk-only option (if reasonable)
        if dist_km < 3.0:
            dep = base_mins + 5
            routes.append(_summarise([
                _walk(from_stop, to_stop, dep, walk_mins, walk_m),
            ]))

        # 3-4 bus options at different times
        available = lancaster_local_services + lancaster_regional_services
        random.shuffle(available)
        for i, offset in enumerate([5, 20, 35, 55]):
            svc_name, svc_stops = available[i % len(available)]
            dep = base_mins + offset
            walk1_mins = random.randint(2, 5)
            walk1_m = walk1_mins * walk_speed_m_per_min

            # Bus ride duration proportional to distance
            ride_dur = max(5, int(dist_km * random.uniform(2.5, 4.0)))

            # Pick 1-2 intermediate stops
            n_int = min(len(svc_stops), random.randint(1, 2))
            int_stops = random.sample(svc_stops, n_int)
            int_stops.sort(key=lambda s: s["offset_frac"])
            ride_start = dep + walk1_mins
            intermediates = [
                {"name": s["name"], "time": _fmt(int(ride_start + ride_dur * s["offset_frac"]))}
                for s in int_stops
            ]

            walk2_mins = random.randint(2, 4)
            walk2_m = walk2_mins * walk_speed_m_per_min
            ride_end = ride_start + ride_dur

            routes.append(_summarise([
                _walk(from_stop, f"Nearby bus stop", dep, walk1_mins, walk1_m),
                _ride("bus", svc_name, "Nearby bus stop",
                      f"Bus stop near destination",
                      ride_start, ride_end, intermediates),
                _walk(f"Bus stop near destination", to_stop,
                      ride_end, walk2_mins, walk2_m),
            ]))

    elif dist_km < 15.0:
        # ------- Medium: regional bus, possibly with a change ---------
        available = lancaster_regional_services + inter_city_services
        random.shuffle(available)

        for i, offset in enumerate([5, 20, 40, 65]):
            svc_name, svc_stops = available[i % len(available)]
            dep = base_mins + offset
            walk1_mins = random.randint(3, 6)
            walk1_m = walk1_mins * walk_speed_m_per_min

            ride_dur = max(12, int(dist_km * random.uniform(2.0, 3.5)))
            ride_start = dep + walk1_mins

            n_int = min(len(svc_stops), random.randint(1, 3))
            int_stops = random.sample(svc_stops, n_int)
            int_stops.sort(key=lambda s: s["offset_frac"])
            intermediates = [
                {"name": s["name"], "time": _fmt(int(ride_start + ride_dur * s["offset_frac"]))}
                for s in int_stops
            ]

            walk2_mins = random.randint(2, 5)
            walk2_m = walk2_mins * walk_speed_m_per_min
            ride_end = ride_start + ride_dur

            routes.append(_summarise([
                _walk(from_stop, f"Nearby bus stop", dep, walk1_mins, walk1_m),
                _ride("bus", svc_name, "Nearby bus stop",
                      f"Bus stop near destination",
                      ride_start, ride_end, intermediates),
                _walk(f"Bus stop near destination", to_stop,
                      ride_end, walk2_mins, walk2_m),
            ]))

        # One option with a change
        svc1_name, svc1_stops = random.choice(lancaster_regional_services)
        svc2_name, svc2_stops = random.choice(inter_city_services)
        dep = base_mins + 30
        walk1_mins = 4
        ride1_dur = max(8, int(dist_km * 1.2))
        ride1_start = dep + walk1_mins
        ride1_end = ride1_start + ride1_dur

        transfer_stop = random.choice(svc1_stops)["name"]
        transfer_walk = 3
        ride2_dur = max(8, int(dist_km * 0.8))
        ride2_start = ride1_end + transfer_walk
        ride2_end = ride2_start + ride2_dur
        walk2_mins = 3

        routes.append(_summarise([
            _walk(from_stop, "Nearby bus stop", dep, walk1_mins, walk1_mins * walk_speed_m_per_min),
            _ride("bus", svc1_name, "Nearby bus stop", transfer_stop,
                  ride1_start, ride1_end,
                  [{"name": svc1_stops[0]["name"],
                    "time": _fmt(int(ride1_start + ride1_dur * 0.5))}]),
            _walk(transfer_stop, f"Connecting bus stop", ride1_end, transfer_walk, 200),
            _ride("bus", svc2_name, "Connecting bus stop",
                  "Bus stop near destination",
                  ride2_start, ride2_end,
                  [{"name": svc2_stops[0]["name"],
                    "time": _fmt(int(ride2_start + ride2_dur * 0.5))}]),
            _walk("Bus stop near destination", to_stop,
                  ride2_end, walk2_mins, walk2_mins * walk_speed_m_per_min),
        ]))

    else:
        # ------- Long distance: bus and/or train ---------
        # Direct train options
        for i, offset in enumerate([10, 45]):
            svc_name, svc_stops = train_services[i % len(train_services)]
            dep = base_mins + offset
            walk1_mins = random.randint(5, 8)
            walk1_m = walk1_mins * walk_speed_m_per_min

            # Train speed: ~1.5-2.5 min per km
            ride_dur = max(15, int(dist_km * random.uniform(1.2, 2.0)))
            ride_start = dep + walk1_mins

            n_int = min(len(svc_stops), random.randint(1, 3))
            int_stops = random.sample(svc_stops, n_int)
            int_stops.sort(key=lambda s: s["offset_frac"])
            intermediates = [
                {"name": s["name"], "time": _fmt(int(ride_start + ride_dur * s["offset_frac"]))}
                for s in int_stops
            ]

            walk2_mins = random.randint(3, 6)
            walk2_m = walk2_mins * walk_speed_m_per_min
            ride_end = ride_start + ride_dur

            routes.append(_summarise([
                _walk(from_stop, "Nearby railway station", dep, walk1_mins, walk1_m),
                _ride("train", svc_name, "Nearby railway station",
                      "Railway station near destination",
                      ride_start, ride_end, intermediates),
                _walk("Railway station near destination", to_stop,
                      ride_end, walk2_mins, walk2_m),
            ]))

        # Direct bus (slower but cheaper)
        svc_name, svc_stops = random.choice(inter_city_services + lancaster_regional_services)
        dep = base_mins + 15
        walk1_mins = 5
        ride_dur = max(25, int(dist_km * random.uniform(2.5, 4.0)))
        ride_start = dep + walk1_mins
        ride_end = ride_start + ride_dur

        n_int = min(len(svc_stops), random.randint(2, 3))
        int_stops = random.sample(svc_stops, n_int)
        int_stops.sort(key=lambda s: s["offset_frac"])
        intermediates = [
            {"name": s["name"], "time": _fmt(int(ride_start + ride_dur * s["offset_frac"]))}
            for s in int_stops
        ]
        walk2_mins = 4

        routes.append(_summarise([
            _walk(from_stop, "Nearby bus stop", dep, walk1_mins, walk1_mins * walk_speed_m_per_min),
            _ride("bus", svc_name, "Nearby bus stop",
                  "Bus stop near destination",
                  ride_start, ride_end, intermediates),
            _walk("Bus stop near destination", to_stop,
                  ride_end, walk2_mins, walk2_mins * walk_speed_m_per_min),
        ]))

        # Bus → Train combination
        svc_bus, bus_stops = random.choice(lancaster_regional_services)
        svc_train, train_stops = random.choice(train_services)
        dep = base_mins + 25
        walk1_mins = 4
        ride1_dur = max(10, int(dist_km * 0.8))
        ride1_start = dep + walk1_mins
        ride1_end = ride1_start + ride1_dur

        transfer_stop_name = random.choice(bus_stops)["name"]
        transfer_walk = random.randint(5, 8)
        ride2_dur = max(15, int(dist_km * 1.0))
        ride2_start = ride1_end + transfer_walk
        ride2_end = ride2_start + ride2_dur
        walk2_mins = 5

        routes.append(_summarise([
            _walk(from_stop, "Nearby bus stop", dep, walk1_mins, walk1_mins * walk_speed_m_per_min),
            _ride("bus", svc_bus, "Nearby bus stop", transfer_stop_name,
                  ride1_start, ride1_end,
                  [{"name": bus_stops[0]["name"],
                    "time": _fmt(int(ride1_start + ride1_dur * 0.5))}]),
            _walk(transfer_stop_name, "Railway station", ride1_end, transfer_walk,
                  transfer_walk * walk_speed_m_per_min),
            _ride("train", svc_train, "Railway station",
                  "Railway station near destination",
                  ride2_start, ride2_end,
                  [{"name": train_stops[0]["name"],
                    "time": _fmt(int(ride2_start + ride2_dur * 0.4))}]),
            _walk("Railway station near destination", to_stop,
                  ride2_end, walk2_mins, walk2_mins * walk_speed_m_per_min),
        ]))

    # Sort by start time
    return sorted(routes, key=lambda r: (
        int(r["start_time"].split(":")[0]),
        int(r["start_time"].split(":")[1]),
    ))


@app.route('/api/routes/search', methods=['POST'])
def search_routes():
    """Search for routes between two stops"""
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

        # Extract coordinates for distance-aware route generation
        from_lat = from_stop.get('lat') or from_stop.get('latitude')
        from_lon = from_stop.get('lon') or from_stop.get('longitude')
        to_lat = to_stop.get('lat') or to_stop.get('latitude')
        to_lon = to_stop.get('lon') or to_stop.get('longitude')

        # Convert to float if present
        try:
            from_lat = float(from_lat) if from_lat is not None else None
            from_lon = float(from_lon) if from_lon is not None else None
            to_lat = float(to_lat) if to_lat is not None else None
            to_lon = float(to_lon) if to_lon is not None else None
        except (ValueError, TypeError):
            from_lat = from_lon = to_lat = to_lon = None

        # Attempt to fetch from real API, fallback to mock data if unavailable
        try:
            routes_data = transport_service.get_routes(from_name, to_name)
            if "error" not in routes_data and routes_data.get('routes'):
                routes = routes_data.get('routes', [])
            else:
                app.logger.info(
                    f"Real API unavailable or no routes found, "
                    f"using mock data for {from_name} -> {to_name}"
                )
                routes = _generate_valid_mock_routes(
                    from_name, to_name,
                    from_lat=from_lat, from_lon=from_lon,
                    to_lat=to_lat, to_lon=to_lon,
                )
        except Exception as e:
            app.logger.warning(f"Real API fetch failed: {e}, using mock data")
            routes = _generate_valid_mock_routes(
                from_name, to_name,
                from_lat=from_lat, from_lon=from_lon,
                to_lat=to_lat, to_lon=to_lon,
            )

        return jsonify({
            "from": from_name,
            "to": to_name,
            "routes": routes,
            "timestamp": datetime.utcnow().isoformat()
        }), 200

    except Exception as e:
        app.logger.error(f"Route search error: {e}")
        return jsonify({"error": str(e)}), 500

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


# Database tables created on first run (disabled on network drives due to locking issues)
# To initialize: python -c "from app import app, db; app.app_context().push(); db.create_all()"
# with app.app_context():
#     db.create_all()


# ---------------------------------------------------------------------------
# Background stop-cache loader
# ---------------------------------------------------------------------------
def _load_stop_cache():
    """Fetch all NaPTAN stops from the external API *and* the supplemental
    stop list, then insert every stop into the local StopCache table.
    Runs once in a background thread so the first request is not blocked
    by the potentially slow XML download.

    The supplemental stops are always loaded so that every red-dot location
    on the map (Liverpool, Manchester, Keswick, …) is guaranteed to have
    bus/train stop entries in the database, regardless of whether the
    upstream NaPTAN feed covers those areas."""
    global _stop_cache_ready
    with app.app_context():
        try:
            # Map bounds (matches frontend maxBounds)
            MIN_LAT, MAX_LAT = 53.0, 55.2
            MIN_LON, MAX_LON = -3.7, -1.9

            # ---- 1. Fetch from external API ----
            api_stops = []
            try:
                app.logger.info("StopCache: Fetching NaPTAN data from API …")
                naptan_data = transport_service.get_naptan(full=False)
                raw = naptan_data.get("stops", []) if isinstance(naptan_data, dict) else naptan_data
                if raw:
                    api_stops = list(raw)
                app.logger.info(f"StopCache: API returned {len(api_stops)} stops")
            except Exception as api_err:
                app.logger.warning(f"StopCache: API fetch failed – {api_err}")

            # ---- 2. Always include the supplemental (static) stops ----
            supplemental = transport_service.naptan._get_supplemental_stops()
            app.logger.info(f"StopCache: {len(supplemental)} supplemental stops available")

            # Merge: API stops first, then supplemental (skip duplicates)
            seen_codes = set()
            all_stops = []
            for stop in api_stops + supplemental:
                code = stop.get("ATCOCode", "")
                if code in seen_codes:
                    continue
                seen_codes.add(code)
                all_stops.append(stop)

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
        except Exception as exc:
            app.logger.error(f"StopCache: Background load failed – {exc}")
            db.session.rollback()

            # Last-resort: try to load *just* the supplemental stops so the
            # database is never empty.
            try:
                app.logger.info("StopCache: Attempting fallback load of supplemental stops only …")
                db.session.query(StopCache).delete()
                db.session.flush()
                count = 0
                for stop in transport_service.naptan._get_supplemental_stops():
                    lat = stop.get("Latitude")
                    lon = stop.get("Longitude")
                    if lat is None or lon is None:
                        continue
                    try:
                        lat_f = float(lat)
                        lon_f = float(lon)
                    except (ValueError, TypeError):
                        continue

                    common_name = stop.get("CommonName", "")
                    indicator = stop.get("Indicator", "")
                    locality_name = stop.get("LocalityName", "")
                    search_text = f"{common_name} {indicator} {locality_name}".lower()

                    db.session.add(StopCache(
                        atco_code=stop.get("ATCOCode", ""),
                        naptan_code=stop.get("NaptanCode", ""),
                        common_name=common_name,
                        indicator=indicator,
                        locality_name=locality_name,
                        latitude=lat_f,
                        longitude=lon_f,
                        stop_type=stop.get("StopType", "bus"),
                        search_text=search_text,
                    ))
                    count += 1
                db.session.commit()
                with _stop_cache_lock:
                    _stop_cache_ready = True
                app.logger.info(f"StopCache: Fallback loaded {count} supplemental stops")
            except Exception as fallback_err:
                app.logger.error(f"StopCache: Fallback load also failed – {fallback_err}")
                db.session.rollback()


# Kick off the background loader (daemon thread so it won't prevent shutdown)
_stop_loader_thread = threading.Thread(target=_load_stop_cache, daemon=True)
_stop_loader_thread.start()


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
