import asyncio

import pytest

from research_council.core.config import Settings
from research_council.core.orchestration import Stage, WorkflowEngine, WorkflowState, parallel_map
from research_council.core.orchestration.engine import RunLease


async def test_checkpoint_resume(repository):
    repo, run = repository
    calls = []
    broken = True

    async def first(_, state):
        calls.append("first")
        state.limitations.append("Saved stage")
        return state

    async def second(_, state):
        if broken:
            raise RuntimeError("simulated failure")
        calls.append("second")
        return state

    engine = WorkflowEngine(repo, Settings(), [Stage("first", first), Stage("second", second)])
    with pytest.raises(RuntimeError):
        await engine.resume(run.run_id)
    assert repo.get_run(run.run_id).stage == 1
    assert engine.load_state(run.run_id).limitations == ["Saved stage"]
    broken = False
    assert (await engine.resume(run.run_id)).status == "COMPLETED"
    assert calls == ["first", "second"]
    await engine.resume(run.run_id)
    assert calls == ["first", "second"]


async def test_parallelism_and_partial_failure():
    active = 0
    maximum = 0

    async def job(value):
        nonlocal active, maximum
        active += 1
        maximum = max(active, maximum)
        await asyncio.sleep(0.01)
        active -= 1
        if value == 1:
            raise RuntimeError("failed branch")
        return value

    result = await parallel_map([0, 1, 2, 3], job, asyncio.Semaphore(2))
    assert maximum == 2
    assert isinstance(result[1], RuntimeError)
    assert result[3] == 3


async def test_human_pause_cannot_be_bypassed(repository):
    repo, run = repository
    settings = Settings()
    settings.research.human_approval_required = True
    run.config_fingerprint = settings.fingerprint()
    repo.save_run(run)

    async def stage(_, state):
        return state

    engine = WorkflowEngine(repo, settings, [Stage("approval", stage, ("after_plan",))])
    assert (await engine.resume(run.run_id)).status == "PAUSED"
    assert (await engine.resume(run.run_id)).stage == 0
    engine.human_decision(run.run_id, "approve")
    assert (await engine.resume(run.run_id)).status == "COMPLETED"


def test_lease_and_config(repository):
    repo, run = repository
    first, second = RunLease(repo, run.run_id), RunLease(repo, run.run_id)
    first.acquire()
    with pytest.raises(RuntimeError, match="owned"):
        second.acquire()
    first.release()
    second.acquire()
    second.release()
    assert WorkflowState().schema_version == 1
