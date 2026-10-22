import io
import zipfile

from fastapi.testclient import TestClient

from research_council.studio.app import create_app


def test_revision_and_draft_never_certify_science(tmp_path):
    with TestClient(create_app(tmp_path), base_url="http://127.0.0.1") as client:
        project = client.post(
            "/api/projects", json={"title": "Draft study", "topic": "Synthetic draft study"}
        ).json()
        run = client.post("/api/projects/" + project["id"] + "/runs", json={}).json()["run"]
        endpoint = "/api/runs/" + run["run_id"]
        state = client.get(endpoint).json()["state"]
        sections = client.get(endpoint + "/paper").json()
        assert len(sections) == 14
        assert next(row for row in sections if row["section"] == "References")["content"] == ""
        draft = client.post(
            endpoint + "/paper/draft", json={"action": "approve", "reviewer": "Researcher"}
        ).json()
        assert all(row["revision"] == 1 for row in draft)
        request = {
            "kind": "experiment",
            "target": "new hypothesis",
            "content": "Exploratory design; no measured result",
            "reviewer": "Researcher",
        }
        assert client.post(endpoint + "/revisions", json=request).json()["revision"] == 1
        assert client.post(endpoint + "/revisions", json=request).json()["revision"] == 2
        assert client.get(endpoint).json()["state"] == state
        exported = client.get(endpoint + "/export")
        assert exported.status_code == 200
        archive = zipfile.ZipFile(io.BytesIO(exported.content))
        assert "studio_revisions.json" in archive.namelist()
        assert all(".." not in name and "/" not in name for name in archive.namelist())
