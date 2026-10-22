import asyncio

import pytest

from research_council.studio.models import Decision, StudioProject
from research_council.studio.service import StudioService


async def test_real_engine_pause_approval_resume_and_cancel(tmp_path):
    service = StudioService(tmp_path)
    project = StudioProject(title="Synthetic FHSS", topic="Synthetic FHSS", mode="novelty")
    service.save_project(project)
    snapshot = service.new_run(project.id)
    identity = service.repository.list_all(
        "research_runs",
        __import__("research_council.schemas.models", fromlist=["ResearchRun"]).ResearchRun,
    )[0].run_id
    assert snapshot["run"]["project_id"] == str(project.id)
    assert snapshot["run"]["provenance"] == "fixture"
    await service.start(identity)
    await service.jobs[identity]
    assert service.snapshot(identity)["state"]["pending_approval"] == "after_plan"
    with pytest.raises(ValueError):
        service.decide(identity, Decision(action="revise", reviewer="Researcher"))
    service.decide(
        identity,
        Decision(action="approve", reviewer="Researcher", comment="Approved synthetic scope"),
    )
    service.control(identity, "pause")
    # Execute directly keeps the cooperative pause request intact.
    await service.execute(identity)
    assert service.snapshot(identity)["run"]["status"] == "PAUSED"
    assert not service.snapshot(identity)["state"]["pending_approval"]
    await service.start(identity)
    await service.jobs[identity]
    assert service.snapshot(identity)["state"]["pending_approval"] == "before_expensive_deep"
    assert len(service.store.list("decision")) == 1
    service.repository.engine.dispose()


async def test_duplicate_worker_and_live_denied(tmp_path):
    service = StudioService(tmp_path)
    project = StudioProject(title="Real research", topic="FHSS study", practice=False)
    service.save_project(project)
    with pytest.raises(ValueError):
        service.new_run(project.id)
    project.practice = True
    service.save_project(project)
    from uuid import UUID

    identity = UUID(service.new_run(project.id)["run"]["run_id"])
    await service.start(identity)
    with pytest.raises(RuntimeError):
        await service.start(identity)
    await asyncio.gather(service.jobs[identity])
    assert all(row.provider == "fake" for row in service.repository.list_model_executions(identity))
    service.repository.engine.dispose()
