from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def test_openapi_exposes_non_authentication_delivery_contract() -> None:
    paths = client.get("/openapi.json").json()["paths"]

    expected = {
        "/api/v1/projects/{project_id}/partners",
        "/api/v1/projects/{project_id}/sprints",
        "/api/v1/resources/{resource_id}/skills",
        "/api/v1/resources/{resource_id}/availability",
        "/api/v1/partners",
        "/api/v1/skills",
    }
    assert expected.issubset(paths)


def test_openapi_documents_dependency_if_match_contract() -> None:
    operation = client.get("/openapi.json").json()["paths"][
        "/api/v1/projects/{project_id}/dependencies/{dependency_id}"
    ]["patch"]
    parameter_names = {parameter["name"] for parameter in operation["parameters"]}

    assert "If-Match" in parameter_names
