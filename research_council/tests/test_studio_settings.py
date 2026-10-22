from fastapi.testclient import TestClient

from research_council.studio.app import create_app


def test_settings_preflight_and_real_confirmation_are_offline(tmp_path, monkeypatch):
    calls = []

    async def forbidden(*args, **kwargs):
        calls.append("network")
        raise AssertionError("No provider requests allowed")

    monkeypatch.setattr("httpx.AsyncClient.post", forbidden)
    for key in ["OPENAI_API_KEY", "ANTHROPIC_API_KEY", "GOOGLE_API_KEY"]:
        monkeypatch.setenv(key, "sensitive-offline-sentinel")
    with TestClient(create_app(tmp_path), base_url="http://127.0.0.1") as client:
        response = client.get("/api/settings")
        assert "sensitive-offline-sentinel" not in response.text
        config = response.json()["settings"]
        assert len(response.json()["compatibility"]) == 20
        assert any(row["anthropic"] == "BLOCKED" for row in response.json()["compatibility"])
        assert client.put("/api/settings", json=config).status_code == 422
        for routes in [*config["models"].values(), *config["role_routes"].values()]:
            for route in routes:
                route.update(enabled=True, input_cost_per_million=1, output_cost_per_million=1)
        config["search"]["adapters"] = ["arxiv"]
        assert client.put("/api/settings", json=config).status_code == 200
        project = client.post(
            "/api/projects",
            json={
                "title": "Real configured study",
                "topic": "Real configured study",
                "practice": False,
            },
        ).json()
        report = client.post("/api/projects/" + project["id"] + "/preflight").json()
        assert report["ready"] is True
        endpoint = "/api/projects/" + project["id"] + "/runs"
        assert client.post(endpoint, json={}).status_code == 422
        # Creating an explicitly confirmed run is configuration-only. Never start it here.
        run = client.post(endpoint, json={"confirmation": "START REAL RESEARCH"}).json()
        assert run["run"]["provenance"] == "live"
        assert run["models"] == []
        assert calls == []
