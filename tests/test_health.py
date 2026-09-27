from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health_returns_ok_and_correlation_id() -> None:
    response = client.get("/api/v1/health")

    assert response.status_code == 200
    assert response.json()["status"] == "ok"
    assert response.headers["x-correlation-id"]


def test_health_reuses_correlation_id() -> None:
    response = client.get(
        "/api/v1/health",
        headers={"X-Correlation-ID": "test-correlation-id"},
    )

    assert response.status_code == 200
    assert response.headers["x-correlation-id"] == "test-correlation-id"
