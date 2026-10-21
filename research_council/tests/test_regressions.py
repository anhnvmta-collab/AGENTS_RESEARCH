import asyncio
import json
from uuid import uuid4

import pytest

from research_council.core.config import Route, Settings
from research_council.core.gates import PublicationReadinessGate
from research_council.core.human_review import ScientificAttestation, attest_claim
from research_council.core.orchestration import Stage, WorkflowEngine, WorkflowState
from research_council.core.routing import BudgetExceeded, ModelRouter
from research_council.providers.base import ProviderError
from research_council.providers.fake import FakeProvider
from research_council.schemas.models import (
    ClaimType,
    Evidence,
    ExperimentPlan,
    ModelExecution,
    Paper,
    PaperCandidate,
    PaperMetadata,
    ResearchClaim,
    ResearchPlan,
    TaskProfile,
    VerificationStatus,
)
from research_council.tools.local import LocalDocumentAdapter


async def test_cancelled_model_call_is_observable(repository):
    repo, run = repository
    router = ModelRouter(Settings(), {"fake": FakeProvider(delay=10)}, repo, run.run_id)
    task = asyncio.create_task(router.generate(TaskProfile.SYNTHESIS, "test", "", "", ResearchPlan))
    await asyncio.sleep(0.01)
    assert repo.list_all("model_executions", ModelExecution, run.run_id)[0].status == "RUNNING"
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert repo.list_all("model_executions", ModelExecution, run.run_id)[0].status == "CANCELLED"


async def test_failed_paid_attempt_consumes_conservative_budget(repository):
    repo, run = repository
    provider = FakeProvider([ProviderError(retryable=True)])
    provider.name = "mock_live"
    settings = Settings(retries=0)
    settings.models[TaskProfile.SYNTHESIS] = [
        Route(
            provider="mock_live", model="test", input_cost_per_million=1, output_cost_per_million=1
        )
    ]
    router = ModelRouter(settings, {"mock_live": provider}, repo, run.run_id)
    with pytest.raises(RuntimeError):
        await router.generate(TaskProfile.SYNTHESIS, "test", "", "", ResearchPlan)
    assert router.cost > 0
    record = repo.list_all("model_executions", ModelExecution, run.run_id)[0]
    assert record.cost_basis == "reserved_upper_bound"
    settings.research.budget_usd = router.cost
    with pytest.raises(BudgetExceeded):
        await router.generate(TaskProfile.SYNTHESIS, "test", "", "", ResearchPlan)


def test_checkpoint_is_atomic_when_evidence_is_invalid(repository):
    repo, run = repository
    paper = Paper(
        metadata=PaperMetadata(title="Atomic test paper", metadata_source="test"),
        source_text="Source text",
    )
    evidence = Evidence(
        paper_id=paper.paper_id,
        evidence_type="test",
        source_location="abstract",
        verbatim_excerpt="Invented text",
        normalized_statement="Test",
        extraction_agent="test",
    )
    state = WorkflowState(candidates=[PaperCandidate(paper=paper)], evidence=[evidence])
    with pytest.raises(ValueError, match="ungrounded"):
        repo.checkpoint(run, {"state": state})
    assert repo.get_paper(paper.paper_id) is None
    assert "state" not in repo.artifacts(run.run_id)


async def test_local_sidecar_does_not_self_verify(tmp_path):
    (tmp_path / "source.txt").write_text("Source text")
    (tmp_path / "source.txt.metadata.json").write_text(
        json.dumps(
            {
                "title": "Document identity",
                "authors": ["Test author"],
                "year": 2020,
                "metadata_verified": True,
            }
        )
    )
    paper = await LocalDocumentAdapter(tmp_path).read("source.txt")
    assert paper.metadata.year == 2020 and not paper.metadata.metadata_verified


async def test_within_stage_checkpoint_survives_failure(repository):
    repo, run = repository

    async def stage(run, state):
        state.novelty_iteration = 2
        repo.checkpoint(run, {"state": state})
        raise RuntimeError("interrupted")

    engine = WorkflowEngine(repo, Settings(), [Stage("long stage", stage)])
    with pytest.raises(RuntimeError):
        await engine.resume(run.run_id)
    assert engine.load_state(run.run_id).novelty_iteration == 2


def human_ready_state():
    paper = Paper(
        metadata=PaperMetadata(
            title="Unit-test source (not literature)",
            authors=["Unit test author"],
            year=2024,
            url="https://example.invalid/unit-test",
            metadata_source="unit-test",
        ),
        source_text="Unit test statement.",
    )
    evidence = Evidence(
        paper_id=paper.paper_id,
        evidence_type="test",
        source_location="text",
        verbatim_excerpt="Unit test statement.",
        normalized_statement="Unit test statement",
        extraction_agent="test",
        verification_status=VerificationStatus.PARTIALLY_VERIFIED,
    )
    claim = ResearchClaim(
        statement="Unit test statement",
        claim_type=ClaimType.AUTHOR_REPORTED,
        evidence_ids=[evidence.evidence_id],
        source_paper_ids=[paper.paper_id],
    )
    return WorkflowState(
        candidates=[PaperCandidate(paper=paper)],
        evidence=[evidence],
        claims=[claim],
        experiments=[
            ExperimentPlan(
                baselines=["test baseline"], metrics=["test metric"], procedures=["test procedure"]
            )
        ],
        limitations=["Unit test only."],
        pending_approval="before_final_report",
    )


def test_explicit_human_attestation_and_claim_specific_gate(repository):
    repo, run = repository
    run.mode = "deep"
    run.status = "PAUSED"
    state = human_ready_state()
    repo.checkpoint(run, {"state": state})
    attestation = ScientificAttestation(
        claim_id=state.claims[0].claim_id,
        reviewer="Unit test reviewer",
        note="Unit test of explicit human scientific review handling.",
        source_identity_checked=True,
        source_locations_checked=True,
        scientific_entailment_checked=True,
        retraction_status_checked=True,
    )
    reviewed = attest_claim(repo, run.run_id, attestation)
    assert reviewed.gates[-1].passed
    audit = reviewed.audits[-1].model_copy(update={"claim_ids": [uuid4()]})
    gate = PublicationReadinessGate().evaluate(
        [item.paper for item in reviewed.candidates],
        reviewed.claims,
        reviewed.evidence,
        [audit],
        reviewed.experiments,
        reviewed.limitations,
    )
    assert not gate.passed


def test_human_cannot_promote_fixture_publication(repository):
    repo, run = repository
    state = human_ready_state()
    state.candidates[0].paper.provenance = "fixture"
    run.status = "PAUSED"
    repo.checkpoint(run, {"state": state})
    attestation = ScientificAttestation(
        claim_id=state.claims[0].claim_id,
        reviewer="Unit test reviewer",
        note="Unit test of fixture rejection during scientific review.",
        source_identity_checked=True,
        source_locations_checked=True,
        scientific_entailment_checked=True,
        retraction_status_checked=True,
    )
    with pytest.raises(ValueError, match="Synthetic"):
        attest_claim(repo, run.run_id, attestation)
