from fastapi.testclient import TestClient

from research_council.studio.app import create_app


def test_errors_bounds_and_headers_do_not_echo_secrets(tmp_path):
    with TestClient(create_app(tmp_path), base_url="http://127.0.0.1") as client:
        secret = "secret-value-must-not-be-returned"
        response = client.put("/api/settings", json={"api_key": secret})
        assert response.status_code == 422 and secret not in response.text
        assert (
            client.post(
                "/api/projects",
                content=b"x" * 1_000_001,
                headers={"Content-Type": "application/json"},
            ).status_code
            == 413
        )
        assert (
            client.post(
                "/api/projects", json={}, headers={"Sec-Fetch-Site": "cross-site"}
            ).status_code
            == 403
        )
        assert client.get("/api/health").headers["x-content-type-options"] == "nosniff"
        assert client.get("/api/health", headers={"host": "attacker.example"}).status_code == 400
        project = client.post(
            "/api/projects", json={"title": "Cursor test", "topic": "Synthetic cursor test"}
        ).json()
        run = client.post("/api/projects/" + project["id"] + "/runs", json={}).json()["run"]
        assert (
            client.get(
                "/api/runs/" + run["run_id"] + "/events?once=true",
                headers={"Last-Event-ID": "invalid"},
            ).status_code
            == 422
        )
        assert client.get("/api/files?path=C:/Windows/win.ini").status_code == 404
        from pathlib import Path

        frontend = Path(__file__).parents[1] / "studio/frontend/dist/assets"
        if frontend.is_dir():
            asset = next(frontend.glob("*.js"))
            response = client.get("/assets/" + asset.name)
            assert response.status_code == 200
            assert "javascript" in response.headers["content-type"]
