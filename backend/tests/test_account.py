"""
Account Management API Tests

Comprehensive test suite for authentication and account management endpoints.
Run with: pytest backend/tests/test_account.py -v
"""

import json

import pytest

from app import app, db


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture(autouse=True)
def setup_database():
    """Reset database before each test."""
    app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite://"
    app.config["TESTING"] = True
    with app.app_context():
        db.drop_all()
        db.create_all()
    yield
    with app.app_context():
        db.drop_all()


@pytest.fixture
def client():
    """Provide a test client."""
    return app.test_client()


@pytest.fixture
def registered_user(client):
    """Create and return a registered user with token."""
    resp = client.post(
        "/api/auth/register",
        data=json.dumps({
            "email": "fixture@example.com",
            "userName": "FixtureUser",
            "password": "password123",
        }),
        content_type="application/json",
    )
    data = json.loads(resp.data)
    return {"token": data["token"], "user": data["user"]}


def _auth_header(token):
    """Helper to create authorization header."""
    return {"Authorization": f"Bearer {token}"}


# Legacy setup for backwards compatibility
def setup_function():
    app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite://"
    app.config["TESTING"] = True
    with app.app_context():
        db.drop_all()
        db.create_all()


# =============================================================================
# Health Check Tests
# =============================================================================


class TestHealthEndpoints:
    """Test health check endpoints."""

    def test_health_endpoint(self, client):
        """GET /health returns ok status."""
        resp = client.get("/health")
        assert resp.status_code == 200
        assert json.loads(resp.data)["status"] == "ok"

    def test_api_health_endpoint(self, client):
        """GET /api/health returns ok status."""
        resp = client.get("/api/health")
        assert resp.status_code == 200
        assert json.loads(resp.data)["status"] == "ok"


# =============================================================================
# Registration Tests
# =============================================================================


class TestRegistration:
    """Test user registration endpoint."""

    def test_register_success(self, client):
        """POST /api/auth/register creates new account."""
        resp = client.post(
            "/api/auth/register",
            data=json.dumps({
                "email": "newuser@example.com",
                "userName": "NewUser",
                "password": "password123",
            }),
            content_type="application/json",
        )
        assert resp.status_code == 201
        data = json.loads(resp.data)
        assert "token" in data
        assert data["user"]["email"] == "newuser@example.com"
        assert data["user"]["userName"] == "NewUser"

    def test_register_duplicate_email(self, client, registered_user):
        """POST /api/auth/register rejects duplicate email."""
        resp = client.post(
            "/api/auth/register",
            data=json.dumps({
                "email": "fixture@example.com",
                "userName": "AnotherUser",
                "password": "password123",
            }),
            content_type="application/json",
        )
        assert resp.status_code == 409
        assert "already registered" in json.loads(resp.data)["error"].lower()

    def test_register_invalid_email(self, client):
        """POST /api/auth/register rejects invalid email."""
        resp = client.post(
            "/api/auth/register",
            data=json.dumps({
                "email": "not-an-email",
                "userName": "TestUser",
                "password": "password123",
            }),
            content_type="application/json",
        )
        assert resp.status_code == 400
        assert "email" in json.loads(resp.data)["error"].lower()

    def test_register_short_username(self, client):
        """POST /api/auth/register rejects short username."""
        resp = client.post(
            "/api/auth/register",
            data=json.dumps({
                "email": "test@example.com",
                "userName": "AB",
                "password": "password123",
            }),
            content_type="application/json",
        )
        assert resp.status_code == 400
        assert "username" in json.loads(resp.data)["error"].lower()

    def test_register_short_password(self, client):
        """POST /api/auth/register rejects short password."""
        resp = client.post(
            "/api/auth/register",
            data=json.dumps({
                "email": "test@example.com",
                "userName": "TestUser",
                "password": "short",
            }),
            content_type="application/json",
        )
        assert resp.status_code == 400
        assert "password" in json.loads(resp.data)["error"].lower()

    def test_register_missing_fields(self, client):
        """POST /api/auth/register rejects missing fields."""
        resp = client.post(
            "/api/auth/register",
            data=json.dumps({"email": "test@example.com"}),
            content_type="application/json",
        )
        assert resp.status_code == 400


# =============================================================================
# Login Tests
# =============================================================================


class TestLogin:
    """Test user login endpoint."""

    def test_login_success(self, client, registered_user):
        """POST /api/auth/login returns token for valid credentials."""
        resp = client.post(
            "/api/auth/login",
            data=json.dumps({
                "email": "fixture@example.com",
                "password": "password123",
            }),
            content_type="application/json",
        )
        assert resp.status_code == 200
        data = json.loads(resp.data)
        assert "token" in data
        assert data["user"]["email"] == "fixture@example.com"

    def test_login_wrong_password(self, client, registered_user):
        """POST /api/auth/login rejects wrong password."""
        resp = client.post(
            "/api/auth/login",
            data=json.dumps({
                "email": "fixture@example.com",
                "password": "wrongpassword",
            }),
            content_type="application/json",
        )
        assert resp.status_code == 401
        assert "invalid" in json.loads(resp.data)["error"].lower()

    def test_login_nonexistent_user(self, client):
        """POST /api/auth/login rejects nonexistent user."""
        resp = client.post(
            "/api/auth/login",
            data=json.dumps({
                "email": "noone@example.com",
                "password": "password123",
            }),
            content_type="application/json",
        )
        assert resp.status_code == 401

    def test_login_case_insensitive_email(self, client, registered_user):
        """POST /api/auth/login handles email case insensitively."""
        resp = client.post(
            "/api/auth/login",
            data=json.dumps({
                "email": "FIXTURE@EXAMPLE.COM",
                "password": "password123",
            }),
            content_type="application/json",
        )
        assert resp.status_code == 200


# =============================================================================
# Logout Tests
# =============================================================================


class TestLogout:
    """Test user logout endpoint."""

    def test_logout_success(self, client):
        """POST /api/auth/logout returns success."""
        resp = client.post("/api/auth/logout")
        assert resp.status_code == 200
        assert "logged out" in json.loads(resp.data)["message"].lower()


# =============================================================================
# Profile Tests
# =============================================================================


class TestProfile:
    """Test user profile endpoints."""

    def test_get_profile_authenticated(self, client, registered_user):
        """GET /api/account/me returns user profile with valid token."""
        resp = client.get(
            "/api/account/me",
            headers=_auth_header(registered_user["token"]),
        )
        assert resp.status_code == 200
        data = json.loads(resp.data)
        assert data["user"]["email"] == "fixture@example.com"

    def test_get_profile_no_token(self, client):
        """GET /api/account/me rejects request without token."""
        resp = client.get("/api/account/me")
        assert resp.status_code == 401

    def test_get_profile_invalid_token(self, client):
        """GET /api/account/me rejects invalid token."""
        resp = client.get(
            "/api/account/me",
            headers=_auth_header("invalid-token-here"),
        )
        assert resp.status_code == 401

    def test_update_profile_username(self, client, registered_user):
        """PATCH /api/account/profile updates username."""
        resp = client.patch(
            "/api/account/profile",
            headers=_auth_header(registered_user["token"]),
            data=json.dumps({"userName": "UpdatedName"}),
            content_type="application/json",
        )
        assert resp.status_code == 200
        data = json.loads(resp.data)
        assert data["user"]["userName"] == "UpdatedName"

    def test_update_profile_colorblind_mode(self, client, registered_user):
        """PATCH /api/account/profile updates colorblind mode."""
        resp = client.patch(
            "/api/account/profile",
            headers=_auth_header(registered_user["token"]),
            data=json.dumps({"colorblindmode": True}),
            content_type="application/json",
        )
        assert resp.status_code == 200
        data = json.loads(resp.data)
        assert data["user"]["colorblindmode"] is True

    def test_update_profile_accessibility_preferences(self, client, registered_user):
        """PATCH /api/account/profile updates accessibility mode and zoom."""
        resp = client.patch(
            "/api/account/profile",
            headers=_auth_header(registered_user["token"]),
            data=json.dumps({"accessibilitymode": "tritanopia", "accessibilityzoom": 1.15}),
            content_type="application/json",
        )
        assert resp.status_code == 200
        data = json.loads(resp.data)
        assert data["user"]["accessibilitymode"] == "tritanopia"
        assert data["user"]["accessibilityzoom"] == 1.15
        assert data["user"]["colorblindmode"] is True

    def test_update_profile_short_username(self, client, registered_user):
        """PATCH /api/account/profile rejects short username."""
        resp = client.patch(
            "/api/account/profile",
            headers=_auth_header(registered_user["token"]),
            data=json.dumps({"userName": "AB"}),
            content_type="application/json",
        )
        assert resp.status_code == 400


# =============================================================================
# Password Change Tests
# =============================================================================


class TestPasswordChange:
    """Test password change endpoint."""

    def test_change_password_success(self, client, registered_user):
        """PATCH /api/account/password updates password."""
        resp = client.patch(
            "/api/account/password",
            headers=_auth_header(registered_user["token"]),
            data=json.dumps({
                "currentPassword": "password123",
                "newPassword": "newpassword456",
            }),
            content_type="application/json",
        )
        assert resp.status_code == 200

        # Verify new password works
        login_resp = client.post(
            "/api/auth/login",
            data=json.dumps({
                "email": "fixture@example.com",
                "password": "newpassword456",
            }),
            content_type="application/json",
        )
        assert login_resp.status_code == 200

    def test_change_password_wrong_current(self, client, registered_user):
        """PATCH /api/account/password rejects wrong current password."""
        resp = client.patch(
            "/api/account/password",
            headers=_auth_header(registered_user["token"]),
            data=json.dumps({
                "currentPassword": "wrongpassword",
                "newPassword": "newpassword456",
            }),
            content_type="application/json",
        )
        assert resp.status_code == 401

    def test_change_password_too_short(self, client, registered_user):
        """PATCH /api/account/password rejects short new password."""
        resp = client.patch(
            "/api/account/password",
            headers=_auth_header(registered_user["token"]),
            data=json.dumps({
                "currentPassword": "password123",
                "newPassword": "short",
            }),
            content_type="application/json",
        )
        assert resp.status_code == 400


# =============================================================================
# Account Deletion Tests
# =============================================================================


class TestAccountDeletion:
    """Test account deletion endpoint."""

    def test_delete_account_success(self, client, registered_user):
        """DELETE /api/account deletes account with correct password."""
        resp = client.delete(
            "/api/account",
            headers=_auth_header(registered_user["token"]),
            data=json.dumps({"password": "password123"}),
            content_type="application/json",
        )
        assert resp.status_code == 200

        # Verify account no longer exists
        login_resp = client.post(
            "/api/auth/login",
            data=json.dumps({
                "email": "fixture@example.com",
                "password": "password123",
            }),
            content_type="application/json",
        )
        assert login_resp.status_code == 401

    def test_delete_account_wrong_password(self, client, registered_user):
        """DELETE /api/account rejects wrong password."""
        resp = client.delete(
            "/api/account",
            headers=_auth_header(registered_user["token"]),
            data=json.dumps({"password": "wrongpassword"}),
            content_type="application/json",
        )
        assert resp.status_code == 401


# =============================================================================
# Saved Routes Tests
# =============================================================================


class TestSavedRoutes:
    """Test saved routes endpoints."""

    def test_save_route_success(self, client, registered_user):
        """POST /api/account/saved-routes saves a route."""
        resp = client.post(
            "/api/account/saved-routes",
            headers=_auth_header(registered_user["token"]),
            data=json.dumps({
                "routeName": "Morning Commute",
                "routeStart": "Preston",
                "routeEnd": "Blackpool",
            }),
            content_type="application/json",
        )
        assert resp.status_code == 201
        data = json.loads(resp.data)
        assert "routeID" in data

    def test_save_route_missing_fields(self, client, registered_user):
        """POST /api/account/saved-routes rejects missing fields."""
        resp = client.post(
            "/api/account/saved-routes",
            headers=_auth_header(registered_user["token"]),
            data=json.dumps({"routeName": "Incomplete Route"}),
            content_type="application/json",
        )
        assert resp.status_code == 400

    def test_list_saved_routes(self, client, registered_user):
        """GET /api/account/saved-routes returns user's saved routes."""
        # Save a route first
        client.post(
            "/api/account/saved-routes",
            headers=_auth_header(registered_user["token"]),
            data=json.dumps({
                "routeName": "Test Route",
                "routeStart": "Manchester",
                "routeEnd": "Liverpool",
            }),
            content_type="application/json",
        )

        resp = client.get(
            "/api/account/saved-routes",
            headers=_auth_header(registered_user["token"]),
        )
        assert resp.status_code == 200
        data = json.loads(resp.data)
        assert len(data["savedRoutes"]) == 1
        assert data["savedRoutes"][0]["routeStart"] == "Manchester"

    def test_delete_saved_route(self, client, registered_user):
        """DELETE /api/account/saved-routes/:id removes a saved route."""
        # Save a route first
        save_resp = client.post(
            "/api/account/saved-routes",
            headers=_auth_header(registered_user["token"]),
            data=json.dumps({
                "routeName": "To Delete",
                "routeStart": "A",
                "routeEnd": "B",
            }),
            content_type="application/json",
        )
        route_id = json.loads(save_resp.data)["routeID"]

        # Delete it
        resp = client.delete(
            f"/api/account/saved-routes/{route_id}",
            headers=_auth_header(registered_user["token"]),
        )
        assert resp.status_code == 200

        # Verify it's gone
        list_resp = client.get(
            "/api/account/saved-routes",
            headers=_auth_header(registered_user["token"]),
        )
        routes = json.loads(list_resp.data)["savedRoutes"]
        assert len(routes) == 0

    def test_delete_nonexistent_route(self, client, registered_user):
        """DELETE /api/account/saved-routes/:id handles nonexistent route."""
        resp = client.delete(
            "/api/account/saved-routes/99999",
            headers=_auth_header(registered_user["token"]),
        )
        assert resp.status_code == 404


# =============================================================================
# Notifications Tests
# =============================================================================


class TestNotifications:
    """Test notification endpoints."""

    def test_get_notifications(self, client, registered_user):
        """GET /api/account/notifications returns user notifications."""
        resp = client.get(
            "/api/account/notifications",
            headers=_auth_header(registered_user["token"]),
        )
        assert resp.status_code == 200
        data = json.loads(resp.data)
        assert "notifications" in data
        # Should have welcome notification from registration
        assert len(data["notifications"]) >= 1

    def test_mark_notification_read(self, client, registered_user):
        """PATCH /api/account/notifications/:id/read marks notification as read."""
        # Get notifications to find an ID
        list_resp = client.get(
            "/api/account/notifications",
            headers=_auth_header(registered_user["token"]),
        )
        notifications = json.loads(list_resp.data)["notifications"]
        notif_id = notifications[0]["notificationID"]

        resp = client.patch(
            f"/api/account/notifications/{notif_id}/read",
            headers=_auth_header(registered_user["token"]),
        )
        assert resp.status_code == 200


# =============================================================================
# Legacy Tests (for backwards compatibility)
# =============================================================================


def test_register_login_and_me_flow():
    client = app.test_client()

    register_resp = client.post(
        "/api/auth/register",
        data=json.dumps(
            {
                "email": "tester@example.com",
                "userName": "tester",
                "password": "password123",
            }
        ),
        content_type="application/json",
    )
    assert register_resp.status_code == 201

    register_data = json.loads(register_resp.data)
    token = register_data.get("token")
    assert token

    me_resp = client.get("/api/account/me", headers=_auth_header(token))
    assert me_resp.status_code == 200
    me_data = json.loads(me_resp.data)
    assert me_data["user"]["email"] == "tester@example.com"

    login_resp = client.post(
        "/api/auth/login",
        data=json.dumps({"email": "tester@example.com", "password": "password123"}),
        content_type="application/json",
    )
    assert login_resp.status_code == 200


def test_saved_route_crud_flow():
    client = app.test_client()

    register_resp = client.post(
        "/api/auth/register",
        data=json.dumps(
            {
                "email": "routes@example.com",
                "userName": "routes-user",
                "password": "password123",
            }
        ),
        content_type="application/json",
    )
    token = json.loads(register_resp.data)["token"]

    save_resp = client.post(
        "/api/account/saved-routes",
        headers=_auth_header(token),
        data=json.dumps(
            {
                "routeName": "Morning Commute",
                "routeStart": "Preston",
                "routeEnd": "Blackpool",
            }
        ),
        content_type="application/json",
    )
    assert save_resp.status_code == 201
    route_id = json.loads(save_resp.data)["routeID"]

    list_resp = client.get("/api/account/saved-routes", headers=_auth_header(token))
    assert list_resp.status_code == 200
    routes = json.loads(list_resp.data)["savedRoutes"]
    assert len(routes) == 1

    delete_resp = client.delete(f"/api/account/saved-routes/{route_id}", headers=_auth_header(token))
    assert delete_resp.status_code == 200
