import asyncio
import hashlib
import json

import pytest

from research_council.core.config import Settings
from research_council.core.orchestration import Stage, WorkflowEngine, WorkflowState
from research_council.core.runtime import settings_for_run


async def test_cancellation_checkpoints_events_and_resumes(repository):
    repo, run = repository
    started = asyncio.Event()
    calls = []
    fail = True

    async def first(_, state):
        calls.append("first")
        return state

    async def second(_, state):
        if fail:
            started.set()
            await asyncio.sleep(20)
        calls.append("second")
        return state

    engine = WorkflowEngine(repo, Settings(), [Stage("first", first), Stage("second", second)])
    worker = asyncio.create_task(engine.resume(run.run_id))
    await started.wait()
    worker.cancel()
    with pytest.raises(asyncio.CancelledError):
        await worker
    assert repo.get_run(run.run_id).stage == 1
    assert engine.load_state(run.run_id).events[-1].event == "STAGE_FAILED"
    fail = False
    assert (await engine.resume(run.run_id)).status == "COMPLETED"
    assert calls == ["first", "second"]


def test_pinned_legacy_settings_keep_verified_fingerprint(repository):
    repo, run = repository
    raw = Settings().model_dump(mode="json")
    raw.pop("role_routes")
    run.config_fingerprint = hashlib.sha256(json.dumps(raw, sort_keys=True).encode()).hexdigest()
    repo.checkpoint(run, {"settings": raw})
    loaded = settings_for_run(repo, run.run_id)
    assert loaded.fingerprint() == run.config_fingerprint
    loaded.research.max_core_papers += 1
    assert loaded.fingerprint() != run.config_fingerprint


async def test_unknown_checkpoint_schema_is_refused(repository):
    repo, run = repository
    repo.checkpoint(run, {"state": WorkflowState(schema_version=99)})
    with pytest.raises(ValueError, match="schema version"):
        await WorkflowEngine(repo, Settings(), []).resume(run.run_id)
