from datetime import datetime, timedelta, timezone
import os
from uuid import uuid4

import bcrypt
import jwt
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool
from sqlalchemy.schema import CreateSchema, DropSchema

from app.core.config import get_settings
from app.db.session import Base, get_db
from app.main import create_app
from app.models.user import User


@pytest.fixture
def auth_client(monkeypatch):
    monkeypatch.setenv("SIGNUP_CODE", "defaultcode")
    monkeypatch.setenv("JWT_SECRET", "test-secret-for-authentication-32-characters")
    get_settings.cache_clear()
    postgres_url = os.environ.get("AUTH_TEST_DATABASE_URL")
    schema = None
    if postgres_url:
        engine = create_engine(postgres_url, connect_args={"connect_timeout": 5})
        schema = "auth_test_" + uuid4().hex
        with engine.begin() as connection:
            connection.execute(CreateSchema(schema))
        engine = engine.execution_options(schema_translate_map={None: schema})
    else:
        # SQLite is used only in isolated tests; the application uses PostgreSQL.
        engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)

    def test_db():
        with Session(engine) as session:
            yield session

    app = create_app()
    app.dependency_overrides[get_db] = test_db
    with TestClient(app) as client:
        yield client, engine
    if schema:
        # Remove only this test's newly created schema; preserve application data.
        with engine.begin() as connection:
            connection.execute(DropSchema(schema, cascade=True))
    engine.dispose()
    get_settings.cache_clear()


def signup(client, **changes):
    data = {"email": "planner@example.com", "password": "correct-password", "signup_code": "defaultcode"}
    return client.post("/api/auth/signup", json={**data, **changes})


def test_signup_signin_and_me(auth_client):
    client, engine = auth_client
    response = signup(client, email=" Planner@Example.com ")
    assert response.status_code == 201
    assert response.json()["user"]["email"] == "planner@example.com"
    assert "password" not in response.json()["user"]
    with Session(engine) as db:
        user = db.scalar(select(User))
        assert user.password_hash != "correct-password"
        assert bcrypt.checkpw(b"correct-password", user.password_hash.encode())
    login = client.post("/api/auth/signin", json={"email": "PLANNER@example.com", "password": "correct-password"})
    assert login.status_code == 200
    token = login.json()["access_token"]
    me = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me.status_code == 200
    assert me.json() == response.json()["user"]


def test_wrong_code_creates_no_account(auth_client):
    client, engine = auth_client
    assert signup(client, signup_code="wrongcode").status_code == 403
    with Session(engine) as db:
        assert db.scalar(select(User)) is None


def test_duplicate_and_invalid_login(auth_client):
    client, _ = auth_client
    assert signup(client).status_code == 201
    assert signup(client, email="PLANNER@example.com").status_code == 409
    for email in ("planner@example.com", "missing@example.com"):
        response = client.post("/api/auth/signin", json={"email": email, "password": "wrong-password"})
        assert response.status_code == 401
        assert response.json()["detail"] == "Invalid email or password."


@pytest.mark.parametrize("password", ["short", "a" * 73, "é" * 37])
def test_password_limits_do_not_echo_secrets(auth_client, password):
    client, _ = auth_client
    response = signup(client, password=password)
    assert response.status_code == 422
    assert password not in response.text
    assert "defaultcode" not in response.text


def test_missing_tampered_and_expired_tokens(auth_client):
    client, _ = auth_client
    assert client.get("/api/auth/me").status_code == 401
    assert client.get("/api/auth/me", headers={"Authorization": "Bearer invalid"}).status_code == 401
    result = signup(client).json()
    expired = jwt.encode({
        "sub": result["user"]["id"], "iat": datetime.now(timezone.utc) - timedelta(minutes=2),
        "exp": datetime.now(timezone.utc) - timedelta(minutes=1),
    }, get_settings().jwt_secret.get_secret_value(), algorithm="HS256")
    assert client.get("/api/auth/me", headers={"Authorization": f"Bearer {expired}"}).status_code == 401


def test_signup_cors_preflight(auth_client):
    client, _ = auth_client
    response = client.options("/api/auth/signup", headers={
        "Origin": "http://localhost:5173", "Access-Control-Request-Method": "POST",
        "Access-Control-Request-Headers": "content-type",
    })
    assert response.status_code == 200


def test_missing_signing_key_does_not_create_account(auth_client, monkeypatch):
    client, engine = auth_client
    monkeypatch.setenv("JWT_SECRET", "")
    get_settings.cache_clear()
    assert signup(client).status_code == 503
    with Session(engine) as db:
        assert db.scalar(select(User)) is None
