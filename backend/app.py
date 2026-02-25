import os
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


with app.app_context():
    db.create_all()


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
