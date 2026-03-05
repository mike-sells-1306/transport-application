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


def _generate_valid_mock_routes(from_stop, to_stop):
    """Generate realistic mock routes with detailed leg information.

    Each route now contains a ``legs`` list.  A *leg* describes one segment of
    the journey – either a *walking* segment between stops, or a *ride* on a
    bus / train.  The expanded detail view on the frontend consumes these legs
    to show intermediate stops, change-over timings, and walking distances.

    Leg schema
    ----------
    Walking leg::

        {
            "mode": "walk",
            "from_stop": "Preston Bus Station",
            "to_stop": "Preston Railway Station",
            "depart": "09:05",
            "arrive": "09:12",
            "duration_mins": 7,
            "distance_m": 450
        }

    Transport leg::

        {
            "mode": "bus" | "train",
            "service": "Service 42" | "Northern Rail",
            "from_stop": "Preston Bus Station (Stand 1)",
            "to_stop": "Blackpool North Bus Station",
            "depart": "09:15",
            "arrive": "10:02",
            "duration_mins": 47,
            "intermediate_stops": [
                {"name": "Kirkham Market Square", "time": "09:35"},
                {"name": "Poulton-le-Fylde Bus Stop", "time": "09:48"}
            ]
        }
    """
    import random

    # ------------------------------------------------------------------
    # Helper: build a walking leg
    # ------------------------------------------------------------------
    def _walk(from_stop_name, to_stop_name, depart, mins, distance_m):
        h, m = map(int, depart.split(":"))
        total = h * 60 + m + mins
        arrive = f"{total // 60:02d}:{total % 60:02d}"
        return {
            "mode": "walk",
            "from_stop": from_stop_name,
            "to_stop": to_stop_name,
            "depart": depart,
            "arrive": arrive,
            "duration_mins": mins,
            "distance_m": distance_m,
        }

    # ------------------------------------------------------------------
    # Helper: build a transport (bus / train) leg
    # ------------------------------------------------------------------
    def _ride(mode, service, from_stop_name, to_stop_name, depart, arrive, intermediate=None):
        dh, dm = map(int, depart.split(":"))
        ah, am = map(int, arrive.split(":"))
        dur = (ah * 60 + am) - (dh * 60 + dm)
        return {
            "mode": mode,
            "service": service,
            "from_stop": from_stop_name,
            "to_stop": to_stop_name,
            "depart": depart,
            "arrive": arrive,
            "duration_mins": dur,
            "intermediate_stops": intermediate or [],
        }

    # ------------------------------------------------------------------
    # Helper: derive summary fields from legs
    # ------------------------------------------------------------------
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
                prev_was_ride = False  # walking doesn't count as a change
        start_time = legs[0]["depart"]
        end_time = legs[-1]["arrive"]
        sh, sm = map(int, start_time.split(":"))
        eh, em = map(int, end_time.split(":"))
        duration_mins = (eh * 60 + em) - (sh * 60 + sm)
        return {
            "start_time": start_time,
            "end_time": end_time,
            "duration_mins": duration_mins,
            "transport": transport_modes,
            "changes": changes,
            "legs": legs,
        }

    # ------------------------------------------------------------------
    # Predefined realistic routes for common journeys (with legs)
    # ------------------------------------------------------------------
    route_patterns = {
        ("lancaster", "blackpool"): [
            # Direct bus – 42 service via A6 / M55
            _summarise([
                _walk("Selected stop", "Lancaster Bus Station (Bay 1)", "09:10", 5, 300),
                _ride("bus", "Service 42", "Lancaster Bus Station (Bay 1)", "Blackpool North Bus Station",
                      "09:15", "10:02",
                      [{"name": "Garstang Bus Stop", "time": "09:32"},
                       {"name": "Preston Bus Station (Stand 1)", "time": "09:48"}]),
                _walk("Blackpool North Bus Station", "Selected stop", "10:02", 3, 200),
            ]),
            # Direct train – Northern Rail
            _summarise([
                _walk("Selected stop", "Lancaster Railway Station", "09:20", 6, 400),
                _ride("train", "Northern Rail", "Lancaster Railway Station", "Blackpool North Railway Station",
                      "09:30", "10:24",
                      [{"name": "Preston Railway Station", "time": "09:52"},
                       {"name": "Kirkham and Wesham Railway Station", "time": "10:08"},
                       {"name": "Poulton-le-Fylde Railway Station", "time": "10:17"}]),
                _walk("Blackpool North Railway Station", "Selected stop", "10:24", 4, 250),
            ]),
            # Bus → Train via Preston
            _summarise([
                _walk("Selected stop", "Lancaster Bus Station (Bay 1)", "09:55", 5, 300),
                _ride("bus", "Service 40", "Lancaster Bus Station (Bay 1)", "Preston Bus Station (Stand 1)",
                      "10:00", "10:32",
                      [{"name": "Garstang Bus Stop", "time": "10:18"}]),
                _walk("Preston Bus Station (Stand 1)", "Preston Railway Station", "10:32", 7, 450),
                _ride("train", "Northern Rail", "Preston Railway Station", "Blackpool North Railway Station",
                      "10:42", "11:14",
                      [{"name": "Kirkham and Wesham Railway Station", "time": "10:56"},
                       {"name": "Poulton-le-Fylde Railway Station", "time": "11:06"}]),
                _walk("Blackpool North Railway Station", "Selected stop", "11:14", 4, 250),
            ]),
            # Later direct bus
            _summarise([
                _walk("Selected stop", "Lancaster Bus Station (Bay 2)", "10:55", 5, 300),
                _ride("bus", "Service 42", "Lancaster Bus Station (Bay 2)", "Blackpool North Bus Station",
                      "11:00", "12:15",
                      [{"name": "Garstang Cross", "time": "11:20"},
                       {"name": "Preston Bus Station (Stand 1)", "time": "11:42"},
                       {"name": "Kirkham Market Square", "time": "11:58"}]),
                _walk("Blackpool North Bus Station", "Selected stop", "12:15", 3, 200),
            ]),
            # Afternoon bus service
            _summarise([
                _walk("Selected stop", "Lancaster Bus Station (Bay 1)", "11:40", 5, 300),
                _ride("bus", "Service 41", "Lancaster Bus Station (Bay 1)", "Blackpool South",
                      "11:45", "13:30",
                      [{"name": "Garstang Bus Stop", "time": "12:05"},
                       {"name": "Preston Bus Station (Stand 1)", "time": "12:30"},
                       {"name": "Lytham Square", "time": "13:10"}]),
                _walk("Blackpool South", "Selected stop", "13:30", 5, 350),
            ]),
        ],
        ("blackpool", "preston"): [
            _summarise([
                _walk("Selected stop", "Blackpool North Bus Station", "08:15", 5, 300),
                _ride("bus", "Service 61", "Blackpool North Bus Station", "Preston Bus Station (Stand 1)",
                      "08:20", "09:15",
                      [{"name": "Poulton-le-Fylde Bus Stop", "time": "08:35"},
                       {"name": "Kirkham Market Square", "time": "08:52"}]),
                _walk("Preston Bus Station (Stand 1)", "Selected stop", "09:15", 3, 200),
            ]),
            _summarise([
                _walk("Selected stop", "Blackpool North Railway Station", "08:50", 6, 400),
                _ride("train", "Northern Rail", "Blackpool North Railway Station", "Preston Railway Station",
                      "09:00", "09:45",
                      [{"name": "Poulton-le-Fylde Railway Station", "time": "09:08"},
                       {"name": "Kirkham and Wesham Railway Station", "time": "09:22"}]),
                _walk("Preston Railway Station", "Selected stop", "09:45", 4, 250),
            ]),
            _summarise([
                _walk("Selected stop", "Blackpool North Bus Station", "10:25", 5, 300),
                _ride("bus", "Service 68", "Blackpool North Bus Station", "Kirkham and Wesham Railway Station",
                      "10:30", "10:58",
                      [{"name": "Poulton-le-Fylde Market Square", "time": "10:42"}]),
                _walk("Kirkham and Wesham Railway Station", "Kirkham and Wesham Railway Station", "10:58", 2, 100),
                _ride("train", "Northern Rail", "Kirkham and Wesham Railway Station", "Preston Railway Station",
                      "11:05", "11:25", []),
                _walk("Preston Railway Station", "Selected stop", "11:25", 4, 250),
            ]),
            _summarise([
                _walk("Selected stop", "Blackpool North Bus Station", "11:10", 5, 300),
                _ride("bus", "Service 61", "Blackpool North Bus Station", "Preston Bus Station (Stand 1)",
                      "11:15", "12:30",
                      [{"name": "Poulton-le-Fylde Bus Stop", "time": "11:30"},
                       {"name": "Kirkham Market Square", "time": "11:50"}]),
                _walk("Preston Bus Station (Stand 1)", "Selected stop", "12:30", 3, 200),
            ]),
            _summarise([
                _walk("Selected stop", "Blackpool North Railway Station", "12:50", 6, 400),
                _ride("train", "Avanti West Coast", "Blackpool North Railway Station", "Preston Railway Station",
                      "13:00", "13:30",
                      [{"name": "Poulton-le-Fylde Railway Station", "time": "13:08"}]),
                _walk("Preston Railway Station", "Selected stop", "13:30", 4, 250),
            ]),
        ],
        ("manchester", "liverpool"): [
            _summarise([
                _walk("Selected stop", "Manchester Piccadilly Railway Station", "07:35", 6, 400),
                _ride("train", "TransPennine Express", "Manchester Piccadilly Railway Station",
                      "Liverpool Lime Street Railway Station", "07:45", "08:45",
                      [{"name": "Manchester Oxford Road Railway Station", "time": "07:48"},
                       {"name": "Liverpool South Parkway", "time": "08:32"}]),
                _walk("Liverpool Lime Street Railway Station", "Selected stop", "08:45", 5, 350),
            ]),
            _summarise([
                _walk("Selected stop", "Shudehill Interchange", "08:25", 5, 300),
                _ride("bus", "Service X1", "Shudehill Interchange", "Liverpool ONE Bus Station",
                      "08:30", "09:45",
                      [{"name": "Warrington Bus Interchange", "time": "09:08"}]),
                _walk("Liverpool ONE Bus Station", "Selected stop", "09:45", 4, 250),
            ]),
            _summarise([
                _walk("Selected stop", "Piccadilly Bus Station", "08:55", 5, 300),
                _ride("bus", "Service 101", "Piccadilly Bus Station", "Liverpool ONE Bus Station",
                      "09:00", "10:15",
                      [{"name": "Warrington Bus Interchange", "time": "09:38"},
                       {"name": "Huyton Bus Station", "time": "09:55"}]),
                _walk("Liverpool ONE Bus Station", "Selected stop", "10:15", 4, 250),
            ]),
            _summarise([
                _walk("Selected stop", "Manchester Piccadilly Railway Station", "09:50", 6, 400),
                _ride("train", "Northern Rail", "Manchester Piccadilly Railway Station",
                      "Liverpool Lime Street Railway Station", "10:00", "11:00",
                      [{"name": "Manchester Oxford Road Railway Station", "time": "10:03"},
                       {"name": "Warrington Central", "time": "10:28"},
                       {"name": "Liverpool South Parkway", "time": "10:47"}]),
                _walk("Liverpool Lime Street Railway Station", "Selected stop", "11:00", 5, 350),
            ]),
            _summarise([
                _walk("Selected stop", "Piccadilly Bus Station", "14:25", 5, 300),
                _ride("bus", "Service X1", "Piccadilly Bus Station", "Warrington Bus Interchange",
                      "14:30", "15:08", []),
                _walk("Warrington Bus Interchange", "Warrington Central Railway Station", "15:08", 5, 320),
                _ride("train", "Northern Rail", "Warrington Central Railway Station",
                      "Liverpool Lime Street Railway Station", "15:18", "15:50",
                      [{"name": "Liverpool South Parkway", "time": "15:38"}]),
                _walk("Liverpool Lime Street Railway Station", "Selected stop", "15:50", 5, 350),
            ]),
        ],
        ("preston", "manchester"): [
            _summarise([
                _walk("Selected stop", "Preston Railway Station", "07:22", 5, 350),
                _ride("train", "Avanti West Coast", "Preston Railway Station",
                      "Manchester Piccadilly Railway Station", "07:30", "08:20",
                      [{"name": "Bolton Railway Station", "time": "08:00"}]),
                _walk("Manchester Piccadilly Railway Station", "Selected stop", "08:20", 5, 300),
            ]),
            _summarise([
                _walk("Selected stop", "Preston Bus Station (Stand 1)", "08:10", 5, 300),
                _ride("bus", "Service X2", "Preston Bus Station (Stand 1)", "Shudehill Interchange",
                      "08:15", "09:30",
                      [{"name": "Chorley Bus Station", "time": "08:42"},
                       {"name": "Bolton Bus Station", "time": "09:05"}]),
                _walk("Shudehill Interchange", "Selected stop", "09:30", 4, 250),
            ]),
            _summarise([
                _walk("Selected stop", "Preston Railway Station", "09:37", 5, 350),
                _ride("train", "Northern Rail", "Preston Railway Station",
                      "Manchester Victoria Railway Station", "09:45", "10:35",
                      [{"name": "Bolton Railway Station", "time": "10:12"}]),
                _walk("Manchester Victoria Railway Station", "Selected stop", "10:35", 5, 300),
            ]),
            _summarise([
                _walk("Selected stop", "Preston Bus Station (Stand 1)", "10:25", 5, 300),
                _ride("bus", "Service X2", "Preston Bus Station (Stand 1)", "Piccadilly Bus Station",
                      "10:30", "11:50",
                      [{"name": "Chorley Bus Station", "time": "10:58"},
                       {"name": "Bolton Bus Station", "time": "11:22"}]),
                _walk("Piccadilly Bus Station", "Selected stop", "11:50", 4, 250),
            ]),
        ],
        ("manchester", "leeds"): [
            _summarise([
                _walk("Selected stop", "Piccadilly Bus Station", "07:55", 5, 300),
                _ride("bus", "Service X62", "Piccadilly Bus Station", "Leeds Bus Station",
                      "08:00", "09:15",
                      [{"name": "Huddersfield Bus Station", "time": "08:38"}]),
                _walk("Leeds Bus Station", "Selected stop", "09:15", 4, 250),
            ]),
            _summarise([
                _walk("Selected stop", "Manchester Piccadilly Railway Station", "08:20", 6, 400),
                _ride("train", "TransPennine Express", "Manchester Piccadilly Railway Station",
                      "Leeds Railway Station", "08:30", "09:30",
                      [{"name": "Huddersfield Railway Station", "time": "09:02"}]),
                _walk("Leeds Railway Station", "Selected stop", "09:30", 5, 300),
            ]),
            _summarise([
                _walk("Selected stop", "Piccadilly Bus Station", "09:55", 5, 300),
                _ride("bus", "Service X62", "Piccadilly Bus Station", "Leeds Bus Station",
                      "10:00", "11:20",
                      [{"name": "Huddersfield Bus Station", "time": "10:42"}]),
                _walk("Leeds Bus Station", "Selected stop", "11:20", 4, 250),
            ]),
        ],
        # Reverse routes: Preston → Lancaster
        ("preston", "lancaster"): [
            _summarise([
                _walk("Selected stop", "Preston Bus Station (Stand 1)", "09:10", 5, 300),
                _ride("bus", "Service 40", "Preston Bus Station (Stand 1)", "Lancaster Bus Station (Bay 1)",
                      "09:15", "09:50",
                      [{"name": "Garstang Bus Stop", "time": "09:35"}]),
                _walk("Lancaster Bus Station (Bay 1)", "Selected stop", "09:50", 4, 250),
            ]),
            _summarise([
                _walk("Selected stop", "Preston Railway Station", "09:20", 5, 350),
                _ride("train", "Northern Rail", "Preston Railway Station", "Lancaster Railway Station",
                      "09:28", "09:52", []),
                _walk("Lancaster Railway Station", "Selected stop", "09:52", 5, 300),
            ]),
            _summarise([
                _walk("Selected stop", "Preston Bus Station (Stand 2)", "10:25", 5, 300),
                _ride("bus", "Service 42", "Preston Bus Station (Stand 2)", "Lancaster Bus Station (Bay 1)",
                      "10:30", "11:08",
                      [{"name": "Garstang Cross", "time": "10:52"}]),
                _walk("Lancaster Bus Station (Bay 1)", "Selected stop", "11:08", 4, 250),
            ]),
        ],
        # Kendal → Windermere
        ("kendal", "windermere"): [
            _summarise([
                _walk("Selected stop", "Kendal Bus Station (Stand A)", "09:10", 5, 300),
                _ride("bus", "Service 555", "Kendal Bus Station (Stand A)", "Windermere Bus Stop",
                      "09:15", "09:42",
                      [{"name": "Staveley Village", "time": "09:28"}]),
                _walk("Windermere Bus Stop", "Selected stop", "09:42", 3, 200),
            ]),
            _summarise([
                _walk("Selected stop", "Kendal Railway Station", "10:05", 6, 400),
                _ride("train", "Northern Rail", "Kendal Railway Station", "Windermere Railway Station",
                      "10:15", "10:38",
                      [{"name": "Burneside Railway Station", "time": "10:22"},
                       {"name": "Staveley Railway Station", "time": "10:28"}]),
                _walk("Windermere Railway Station", "Selected stop", "10:38", 4, 250),
            ]),
        ],
        # Lancaster → Kendal
        ("lancaster", "kendal"): [
            _summarise([
                _walk("Selected stop", "Lancaster Railway Station", "08:50", 6, 400),
                _ride("train", "Avanti West Coast", "Lancaster Railway Station", "Kendal Railway Station",
                      "09:00", "09:22",
                      [{"name": "Carnforth Railway Station", "time": "09:08"}]),
                _walk("Kendal Railway Station", "Selected stop", "09:22", 5, 300),
            ]),
            _summarise([
                _walk("Selected stop", "Lancaster Bus Station (Bay 1)", "09:25", 5, 300),
                _ride("bus", "Service 555", "Lancaster Bus Station (Bay 1)", "Kendal Bus Station (Stand A)",
                      "09:30", "10:25",
                      [{"name": "Carnforth Bus Stop", "time": "09:48"},
                       {"name": "Kirkby Lonsdale Market Square", "time": "10:05"}]),
                _walk("Kendal Bus Station (Stand A)", "Selected stop", "10:25", 4, 250),
            ]),
            _summarise([
                _walk("Selected stop", "Lancaster Railway Station", "10:50", 6, 400),
                _ride("train", "Northern Rail", "Lancaster Railway Station", "Kendal Railway Station",
                      "11:00", "11:25",
                      [{"name": "Carnforth Railway Station", "time": "11:10"}]),
                _walk("Kendal Railway Station", "Selected stop", "11:25", 5, 300),
            ]),
        ],
        # Lancaster → Preston
        ("lancaster", "preston"): [
            _summarise([
                _walk("Selected stop", "Lancaster Bus Station (Bay 1)", "08:55", 5, 300),
                _ride("bus", "Service 40", "Lancaster Bus Station (Bay 1)", "Preston Bus Station (Stand 1)",
                      "09:00", "09:38",
                      [{"name": "Garstang Bus Stop", "time": "09:20"}]),
                _walk("Preston Bus Station (Stand 1)", "Selected stop", "09:38", 4, 250),
            ]),
            _summarise([
                _walk("Selected stop", "Lancaster Railway Station", "09:15", 6, 400),
                _ride("train", "Avanti West Coast", "Lancaster Railway Station", "Preston Railway Station",
                      "09:25", "09:48", []),
                _walk("Preston Railway Station", "Selected stop", "09:48", 5, 300),
            ]),
            _summarise([
                _walk("Selected stop", "Lancaster Bus Station (Bay 2)", "10:25", 5, 300),
                _ride("bus", "Service 42", "Lancaster Bus Station (Bay 2)", "Preston Bus Station (Stand 1)",
                      "10:30", "11:10",
                      [{"name": "Garstang Cross", "time": "10:50"}]),
                _walk("Preston Bus Station (Stand 1)", "Selected stop", "11:10", 4, 250),
            ]),
        ],
    }

    # ------------------------------------------------------------------
    # Look up predefined routes
    # ------------------------------------------------------------------
    from_key = from_stop.lower().split()[0]
    to_key = to_stop.lower().split()[0]
    lookup_key = (from_key, to_key)

    if lookup_key in route_patterns:
        return route_patterns[lookup_key]

    # ------------------------------------------------------------------
    # Procedural route generation for unmapped pairs
    # ------------------------------------------------------------------
    random.seed(hash(from_stop + to_stop) % 2**32)

    # Known intermediate stops per area (used for realistic leg data)
    area_stops = {
        "bus": [
            "Garstang Bus Stop", "Preston Bus Station (Stand 1)",
            "Kirkham Market Square", "Poulton-le-Fylde Bus Stop",
            "Chorley Bus Station", "Bolton Bus Station",
            "Kendal Bus Station (Stand A)",
        ],
        "train": [
            "Preston Railway Station", "Lancaster Railway Station",
            "Carnforth Railway Station", "Kendal Railway Station",
            "Bolton Railway Station", "Kirkham and Wesham Railway Station",
        ],
    }

    routes = []
    for _ in range(random.randint(3, 5)):
        start_hour = random.randint(8, 17)
        start_min = random.choice([0, 15, 30, 45])

        duration = random.choice([30, 45, 50, 60, 75, 90, 105, 120])
        total_mins = start_hour * 60 + start_min + duration
        if total_mins // 60 > 23:
            continue

        transport_choice = random.choice([["bus"], ["train"], ["bus", "train"]])
        legs = []

        # Opening walk
        walk_start = f"{start_hour:02d}:{start_min:02d}"
        walk_dur = random.choice([3, 4, 5, 6, 7])
        wt = start_hour * 60 + start_min + walk_dur
        first_depart = f"{wt // 60:02d}:{wt % 60:02d}"
        legs.append(_walk("Selected stop", f"{from_stop} stop", walk_start, walk_dur, random.randint(150, 500)))

        cursor_mins = wt  # current time in total minutes

        if len(transport_choice) == 1:
            # Single mode ride
            mode = transport_choice[0]
            ride_dur = duration - walk_dur - random.choice([3, 4, 5])
            if ride_dur < 10:
                ride_dur = 15
            ride_arrive = cursor_mins + ride_dur
            # Pick 1-2 random intermediate stops
            intermediates = []
            num_int = random.randint(1, 2)
            for j in range(num_int):
                frac = (j + 1) / (num_int + 1)
                int_time = cursor_mins + int(ride_dur * frac)
                intermediates.append({
                    "name": random.choice(area_stops[mode]),
                    "time": f"{int_time // 60:02d}:{int_time % 60:02d}",
                })
            service = f"Service {random.randint(1, 99)}" if mode == "bus" else random.choice(["Northern Rail", "Avanti West Coast", "TransPennine Express"])
            legs.append(_ride(mode, service, f"{from_stop} stop", f"{to_stop} stop",
                              first_depart,
                              f"{ride_arrive // 60:02d}:{ride_arrive % 60:02d}",
                              intermediates))
            cursor_mins = ride_arrive
        else:
            # Two-mode: first ride, walk transfer, second ride
            mode1, mode2 = transport_choice
            ride1_dur = random.randint(15, duration // 2)
            ride1_arrive = cursor_mins + ride1_dur

            transfer_stop = random.choice(area_stops[mode1])
            service1 = f"Service {random.randint(1, 99)}" if mode1 == "bus" else random.choice(["Northern Rail", "Avanti West Coast"])
            legs.append(_ride(mode1, service1, f"{from_stop} stop", transfer_stop,
                              first_depart,
                              f"{ride1_arrive // 60:02d}:{ride1_arrive % 60:02d}",
                              []))
            cursor_mins = ride1_arrive

            # Walking transfer
            transfer_walk = random.choice([4, 5, 6, 7, 8])
            legs.append(_walk(transfer_stop, transfer_stop.replace("Bus", "Rail").replace("bus", "rail"),
                              f"{cursor_mins // 60:02d}:{cursor_mins % 60:02d}",
                              transfer_walk, random.randint(200, 500)))
            cursor_mins += transfer_walk

            # Second ride
            ride2_dur = max(10, duration - ride1_dur - walk_dur - transfer_walk - 5)
            ride2_arrive = cursor_mins + ride2_dur
            service2 = f"Service {random.randint(1, 99)}" if mode2 == "bus" else random.choice(["Northern Rail", "TransPennine Express"])
            legs.append(_ride(mode2, service2,
                              transfer_stop.replace("Bus", "Rail").replace("bus", "rail"),
                              f"{to_stop} stop",
                              f"{cursor_mins // 60:02d}:{cursor_mins % 60:02d}",
                              f"{ride2_arrive // 60:02d}:{ride2_arrive % 60:02d}",
                              []))
            cursor_mins = ride2_arrive

        # Closing walk
        close_walk = random.choice([3, 4, 5])
        legs.append(_walk(f"{to_stop} stop", "Selected stop",
                          f"{cursor_mins // 60:02d}:{cursor_mins % 60:02d}",
                          close_walk, random.randint(150, 400)))

        routes.append(_summarise(legs))

    # Sort by start time
    return sorted(routes, key=lambda r: (int(r["start_time"].split(":")[0]), int(r["start_time"].split(":")[1])))


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
        
        # Attempt to fetch from real API, fallback to mock data if unavailable
        try:
            routes_data = transport_service.get_routes(from_name, to_name)
            if "error" not in routes_data and routes_data.get('routes'):
                routes = routes_data.get('routes', [])
            else:
                # API returned error or empty, use mock data
                app.logger.info(f"Real API unavailable or no routes found, using mock data for {from_name} → {to_name}")
                routes = _generate_valid_mock_routes(from_name, to_name)
        except Exception as e:
            app.logger.warning(f"Real API fetch failed: {e}, using mock data")
            routes = _generate_valid_mock_routes(from_name, to_name)
        
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
