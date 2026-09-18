from fastapi.testclient import TestClient

from app.main import create_app


def test_health_contract():
    with TestClient(create_app()) as client:
        response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "service": "scheduler-api"}


def test_frontend_origin_is_allowed():
    with TestClient(create_app()) as client:
        response = client.get("/api/health", headers={"Origin": "http://localhost:5173"})
    assert response.headers["access-control-allow-origin"] == "http://localhost:5173"
