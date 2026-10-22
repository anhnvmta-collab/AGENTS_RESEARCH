from uuid import UUID

import pytest
from fastapi.testclient import TestClient

from research_council.studio.app import create_app
from research_council.studio.interactions import approve_proposal, discuss, propose
from research_council.studio.models import Decision, Interaction, StudioProject
from research_council.studio.service import StudioService


async def test_discussion_is_read_only_and_action_requires_review(tmp_path):
    service = StudioService(tmp_path)
    project = StudioProject(title="Synthetic FHSS", topic="Synthetic FHSS")
    service.save_project(project)
    identity = UUID(service.new_run(project.id)["run"]["run_id"])
    await service.start(identity)
    await service.jobs[identity]
    original = service.repository.artifacts(identity)["state"]
    request = Interaction(run_id=identity, task="Please refine the synthetic study scope")
    discussion = await discuss(service, "ResearchPlanner", request)
    assert discussion["canonical_mutation"] is False
    assert service.repository.artifacts(identity)["state"] == original
    assert len(service.agents(identity)) == 20
    assert any(row["operations"] for row in service.agents(identity))
    proposal = propose(service, "ResearchPlanner", request)
    assert proposal["status"] == "PROPOSED"
    assert service.repository.artifacts(identity)["state"] == original
    applied = await approve_proposal(
        service, UUID(proposal["id"]), Decision(action="approve", reviewer="Local researcher")
    )
    assert applied["canonical_mutation"] is True
    assert service.repository.get_run(identity).stage == 0
    assert service.repository.artifacts(identity)["state"]["pending_approval"] is None
    assert (
        "Approved researcher action"
        in service.repository.get_run(identity).question.constraints[-1]
    )
    with pytest.raises(ValueError):
        await approve_proposal(
            service, UUID(proposal["id"]), Decision(action="approve", reviewer="Local researcher")
        )
    with pytest.raises(KeyError):
        await discuss(service, "ArbitraryPromptExecutor", request)
    service.repository.engine.dispose()


def test_sse_replay_is_persisted_and_safe(tmp_path):
    with TestClient(create_app(tmp_path), base_url="http://127.0.0.1") as client:
        project = client.post(
            "/api/projects", json={"title": "Practice FHSS", "topic": "Synthetic FHSS"}
        ).json()
        run = client.post("/api/projects/" + project["id"] + "/runs", json={}).json()["run"]
        client.post("/api/runs/" + run["run_id"] + "/start")
        import time

        for _ in range(60):
            snapshot = client.get("/api/runs/" + run["run_id"]).json()
            if snapshot["state"]["pending_approval"]:
                break
            time.sleep(0.05)
        response = client.get("/api/runs/" + run["run_id"] + "/events?once=true")
        assert "event: agent_completed" in response.text
        assert "event: human_review_required" in response.text
        assert "api_key" not in response.text
        assert "untrusted_task_data" not in response.text
        last = response.text.split("id: ")[-1].splitlines()[0]
        replay = client.get(
            "/api/runs/" + run["run_id"] + "/events?once=true", headers={"Last-Event-ID": last}
        )
        assert "event:" not in replay.text


async def test_live_operational_summary_exists_before_agent_finishes(repository):
    import asyncio

    from research_council.agents.contracts import QuestionInput
    from research_council.agents.research_planner import ResearchPlanner
    from research_council.core.config import Settings
    from research_council.core.routing import ModelRouter
    from research_council.providers.fake import FakeProvider
    from research_council.schemas.models import AgentExecution

    repo, run = repository
    router = ModelRouter(Settings(), {"fake": FakeProvider(delay=0.1)}, repo, run.run_id)
    task = asyncio.create_task(
        ResearchPlanner(router).run(
            QuestionInput(task="Plan bounded research", question=run.question)
        )
    )
    await asyncio.sleep(0.02)
    execution = repo.list_all("agent_executions", AgentExecution, run.run_id)[0]
    assert execution.status == "RUNNING"
    summary = repo.artifacts(run.run_id)["operation_" + str(execution.execution_id)]
    assert summary["input_contract"] == "QuestionInput"
    assert "untrusted_task_data" not in str(summary)
    await task
    assert repo.artifacts(run.run_id)["agent_output_" + str(execution.execution_id)]["objective"]
