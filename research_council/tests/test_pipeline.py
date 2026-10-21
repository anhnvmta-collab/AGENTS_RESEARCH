import json

import pytest

from research_council.core.config import Settings
from research_council.core.orchestration.state import WorkflowState
from research_council.core.runtime import Runtime, create_run, open_repository
from research_council.exporters import MarkdownExporter
from research_council.schemas.models import Mode, ResearchQuestion


@pytest.mark.parametrize("mode", list(Mode))
async def test_offline_end_to_end(tmp_path, mode):
    repo = open_repository(tmp_path)
    settings = Settings(retry_base_seconds=0)
    run = create_run(repo, ResearchQuestion(topic="FHSS SDR FPGA system test"), mode, settings)
    async with Runtime(tmp_path, repo, settings, run) as pipeline:
        result = await pipeline.engine(mode).resume(run.run_id)
        assert result.status == "COMPLETED"
    state = WorkflowState.model_validate(repo.artifacts(run.run_id)["state"])
    assert not state.evidence and not state.claims
    target = MarkdownExporter(tmp_path, repo).export(result, state)
    manifest = json.loads((target / "run_manifest.json").read_text())
    assert not manifest["publication_ready"]
    assert len(manifest["files"]) == 13
    repo.engine.dispose()


async def test_fixture_end_to_end_and_resume(tmp_path):
    repo = open_repository(tmp_path)
    settings = Settings(retry_base_seconds=0)
    run = create_run(
        repo, ResearchQuestion(topic="FHSS SDR FPGA system test"), Mode.NOVELTY, settings, demo=True
    )
    async with Runtime(tmp_path, repo, settings, run) as pipeline:
        result = await pipeline.engine(run.mode).resume(run.run_id)
        assert result.status == "COMPLETED"
        assert pipeline.router.providers["fake"].max_active >= 2
        calls = pipeline.router.calls
        await pipeline.engine(run.mode).resume(run.run_id)
        assert pipeline.router.calls == calls
    state = WorkflowState.model_validate(repo.artifacts(run.run_id)["state"])
    assert len(state.candidates) == 2 and len(state.evidence) == 2
    assert len(state.gaps) == 1
    assert state.novelty_iteration == 3
    assert state.search_history and all(
        attempt.status == "SUCCESS" for attempt in state.search_history
    )
    assert all(item.provenance == "fixture" for item in state.evidence)
    assert all(decision.verdict == "UNRESOLVED" for decision in state.decisions)
    target = MarkdownExporter(tmp_path, repo).export(result, state)
    report = (target / "final_report.md").read_text()
    assert "SYNTHETIC FIXTURES" in report
    assert str(state.evidence[0].evidence_id) in report
    assert "NOT ESTABLISHED" in report
    assert not json.loads((target / "run_manifest.json").read_text())["publication_ready"]
    repo.engine.dispose()
