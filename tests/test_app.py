import pytest

from CampusTrack import create_app


@pytest.fixture()
def app():
    app = create_app({"TESTING": True, "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:"})
    with app.app_context():
        from CampusTrack.extensions import db

        db.create_all()
    yield app


@pytest.fixture()
def client(app):
    return app.test_client()


def test_home_page_renders(client):
    response = client.get("/")
    assert response.status_code == 200


def test_admin_and_login_routes_render(client):
    for path in ["/admin", "/admin/login", "/user/login"]:
        response = client.get(path)
        assert response.status_code == 200
