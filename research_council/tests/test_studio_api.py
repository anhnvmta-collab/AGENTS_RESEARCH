from fastapi.testclient import TestClient

from research_council.studio.app import create_app


def test_projects_persist_and_validate(tmp_path):
    with TestClient(create_app(tmp_path)) as client:
        assert client.get("/api/health").status_code == 200
        assert client.post("/api/projects", json={"title": "x", "topic": "x"}).status_code == 422
        project = client.post(
            "/api/projects", json={"title": "FHSS Study", "topic": "Phân tích FHSS"}
        ).json()
        assert project["practice"] is True
        assert client.get("/api/projects/" + project["id"]).json()["topic"] == "Phân tích FHSS"
        assert client.get("/api/dashboard").json()["papers"] == 0
        assert client.get("/api/projects/00000000-0000-0000-0000-000000000000").status_code == 404
    with TestClient(create_app(tmp_path)) as client:
        assert len(client.get("/api/projects").json()) == 1


def test_local_security(tmp_path):
    with TestClient(create_app(tmp_path)) as client:
        assert client.get("/api/health", headers={"host": "evil.test"}).status_code == 400
        assert (
            client.post(
                "/api/projects", json={}, headers={"origin": "https://evil.test"}
            ).status_code
            == 403
        )
        assert (
            "access-control-allow-origin"
            not in client.get("/api/health", headers={"origin": "https://evil.test"}).headers
        )
