from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.core.config import get_settings
from app.core.security import create_access_token
from app.db.session import Base, get_db
from app.main import create_app
from app.models.user import User
from app.workers.scheduling import process_next
from scheduler.loader import REQUIRED_FILES

PUBLIC = Path(__file__).resolve().parents[2] / "01_data"


@pytest.fixture
def client_context(monkeypatch):
    monkeypatch.setenv("JWT_SECRET", "a-test-api-secret-with-more-than-32-characters")
    get_settings.cache_clear()
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        first, second = (
            User(email="one@example.com", password_hash="unused"),
            User(email="two@example.com", password_hash="unused"),
        )
        db.add_all([first, second])
        db.commit()
        tokens = [create_access_token(first.id), create_access_token(second.id)]

    def test_db():
        with Session(engine) as db:
            yield db

    app = create_app()
    app.dependency_overrides[get_db] = test_db
    with TestClient(app) as client:
        yield client, engine, [{"Authorization": f"Bearer {token}"} for token in tokens]
    engine.dispose()
    get_settings.cache_clear()


def upload(client, headers):
    return client.post(
        "/api/instances",
        headers=headers,
        data={"name": "Public instance"},
        files=[
            ("files", (name, (PUBLIC / name).read_bytes(), "text/csv"))
            for name in REQUIRED_FILES
        ],
    )


def test_upload_prepare_persist_and_owner_isolation(client_context):
    client, engine, (owner, other) = client_context
    response = upload(client, owner)
    assert response.status_code == 201
    dataset = response.json()
    assert dataset["summary"]["activities"] == 54
    assert (
        client.get(f"/api/instances/{dataset['id']}", headers=other).status_code == 404
    )
    assert client.get("/api/instances", headers=other).json() == []
    run_response = client.post(
        "/api/runs", headers=owner, json={"dataset_id": dataset["id"], "scenario": "B"}
    )
    assert run_response.status_code == 202
    run = run_response.json()
    assert process_next(engine)
    final = client.get(f"/api/runs/{run['id']}", headers=owner).json()
    assert final["status"] == "needs_validation" and final["schedule"] is not None
    assert final["report"]["policy"]["scenario"] == "B"
    assert client.get(f"/api/runs/{run['id']}", headers=other).status_code == 404
    assert client.get(f"/api/runs/{run['id']}/report", headers=owner).status_code == 200
    assert (
        client.get(f"/api/runs/{run['id']}/submission", headers=owner).status_code
        == 200
    )
    assert not process_next(engine)


def test_authentication_and_invalid_upload(client_context):
    client, _, (owner, _) = client_context
    assert client.get("/api/instances").status_code == 401
    response = client.post(
        "/api/instances",
        headers=owner,
        files=[("files", ("wrong.csv", b"a,b\n1,2\n", "text/csv"))],
    )
    assert response.status_code == 422
    assert client.get("/api/instances", headers=owner).json() == []
    assert client.get("/api/runs/capabilities").json()["can_schedule"] is True


def test_queue_quota(client_context):
    client, _, (owner, _) = client_context
    dataset = upload(client, owner).json()
    for scenario in ("A", "B", "C"):
        assert (
            client.post(
                "/api/runs",
                headers=owner,
                json={"dataset_id": dataset["id"], "scenario": scenario},
            ).status_code
            == 202
        )
    assert (
        client.post(
            "/api/runs",
            headers=owner,
            json={"dataset_id": dataset["id"], "scenario": "A"},
        ).status_code
        == 429
    )
