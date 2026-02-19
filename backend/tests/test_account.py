import json

from app import app, db


def _auth_header(token):
    return {"Authorization": f"Bearer {token}"}


def setup_function():
    app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite://"
    app.config["TESTING"] = True
    with app.app_context():
        db.drop_all()
        db.create_all()


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
