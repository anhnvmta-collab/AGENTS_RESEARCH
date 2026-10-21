from uuid import uuid4

import pytest
from pydantic import ValidationError
from test_regressions import human_ready_state

from research_council.core.conflict_review import (
    ConflictResolutionRequest,
    resolve_evidence_conflict,
)
from research_council.core.grounding import validate_analysis_claims
from research_council.core.integrity import (
    synchronize_conflicts,
    unresolved_conflict,
    validate_graph,
)
from research_council.core.orchestration.state import WorkflowState
from research_council.knowledge.retrieval import LexicalEvidenceRetriever, LocatedChunker
from research_council.schemas.models import (
    ClaimType,
    Paper,
    PaperCandidate,
    PaperMetadata,
    VerificationStatus,
)


def test_late_page_ranking_and_stable_source_offsets():
    paper = Paper(
        metadata=PaperMetadata(title="Unit source", metadata_source="test"),
        source_kind="local_pdf",
        page_texts={
            1: "background " * 4000,
            20: "FPGA throughput latency AXI memory bandwidth measurements.",
        },
    )
    chunks = LocatedChunker().chunk(paper)
    assert chunks == LocatedChunker().chunk(paper)
    ranked = LexicalEvidenceRetriever().rank("FPGA AXI latency bandwidth", chunks, 1)
    assert ranked[0].chunk.page == 20 and ranked[0].score > 0
    state = WorkflowState(candidates=[PaperCandidate(paper=paper)], chunks=chunks)
    validate_graph(state)
    state.chunks[-1].start_offset = 1
    with pytest.raises(ValueError, match="offsets"):
        validate_graph(state)


def test_conflicts_survive_model_omission_and_require_documented_resolution(repository):
    repo, run = repository
    run.status = "PAUSED"
    state = human_ready_state()
    opposite = state.evidence[0].model_copy(update={"evidence_id": uuid4()})
    state.evidence.append(opposite)
    state.claims[0].contradicting_evidence_ids = [opposite.evidence_id]
    repo.checkpoint(run, {"state": state})
    synchronize_conflicts(state)
    state.claims[0].contradicting_evidence_ids = []
    synchronize_conflicts(state)
    assert state.claims[0].contradicting_evidence_ids == [opposite.evidence_id]
    assert unresolved_conflict(state.claims[0], state.conflicts)
    result = resolve_evidence_conflict(
        repo,
        run.run_id,
        ConflictResolutionRequest(
            conflict_id=state.conflicts[0].conflict_id,
            reviewer="Test reviewer",
            note="Reviewed opposing evidence and documented the scoped interpretation.",
            resolution_status="RESOLVED",
        ),
    )
    assert not unresolved_conflict(result.claims[0], result.conflicts)
    assert result.claims[0].verification_status == VerificationStatus.UNVERIFIED
    assert result.claims[0].contradicting_evidence_ids == [opposite.evidence_id]
    assert len(result.evidence) == 2
    result.claims[0].resolved_conflict_ids = [uuid4()]
    with pytest.raises(ValueError, match="resolved-conflict"):
        validate_graph(result)


def test_math_hypotheses_and_quartile_context_fail_closed():
    state = human_ready_state()
    state.claims[0].claim_type = ClaimType.HYPOTHESIS
    assert (
        validate_analysis_claims(state.claims, state.evidence)[0].verification_status
        == VerificationStatus.UNVERIFIED
    )
    with pytest.raises(ValidationError):
        PaperMetadata(
            title="Unit source",
            metadata_source="test",
            quartile="Q1",
            quartile_source="unspecified",
        )


def test_dictionary_checkpoint_cannot_bypass_graph_validation(repository):
    repo, run = repository
    state = human_ready_state()
    state.claims[0].evidence_ids = [uuid4()]
    with pytest.raises(ValueError, match="claim-to-evidence"):
        repo.checkpoint(run, {"state": state.model_dump(mode="json")})
    assert "state" not in repo.artifacts(run.run_id)


def test_previous_checkpoint_conflict_survives_fresh_state_omission(repository):
    repo, run = repository
    state = human_ready_state()
    opposite = state.evidence[0].model_copy(update={"evidence_id": uuid4()})
    state.evidence.append(opposite)
    state.claims[0].contradicting_evidence_ids = [opposite.evidence_id]
    repo.checkpoint(run, {"state": state})
    replacement = state.model_copy(deep=True)
    replacement.conflicts = []
    replacement.claims[0].contradicting_evidence_ids = []
    repo.checkpoint(run, {"state": replacement.model_dump(mode="json")})
    saved = WorkflowState.model_validate(repo.artifacts(run.run_id)["state"])
    assert saved.conflicts and unresolved_conflict(saved.claims[0], saved.conflicts)
    assert saved.claims[0].contradicting_evidence_ids == [opposite.evidence_id]


async def test_reader_receives_ranked_chunks_and_stamps_exact_provenance(repository):
    import json

    from research_council.agents.contracts import ReadingInput
    from research_council.agents.deep_reader import DeepReader
    from research_council.core.config import Settings
    from research_council.core.routing import ModelRouter
    from research_council.providers.base import LLMResponse
    from research_council.providers.fake import FakeProvider

    repo, run = repository
    state = human_ready_state()
    paper = state.candidates[0].paper
    quote = "FPGA sampling bandwidth latency measurement remained unavailable."
    paper.source_kind = "local_pdf"
    paper.source_text = None
    paper.page_texts = {1: "Background " * 4000, 25: quote}
    item = state.evidence[0].model_copy(update={"page": 25, "verbatim_excerpt": quote})
    provider = FakeProvider(
        [LLMResponse(text=json.dumps({"evidence": [item.model_dump(mode="json")]}))]
    )
    output = await DeepReader(ModelRouter(Settings(), {"fake": provider}, repo, run.run_id)).run(
        ReadingInput(task="FPGA latency bandwidth", paper=paper)
    )
    sent = json.loads(provider.requests[0].user)["untrusted_task_data"]
    assert sent["paper"]["source_text"] is None and not sent["paper"]["page_texts"]
    assert sent["chunks"][0]["page"] == 25 and len(sent["chunks"]) <= 8
    assert output.evidence[0].chunk_id and output.evidence[0].source_sha256
    assert output.evidence[0].verification_status == VerificationStatus.PARTIALLY_VERIFIED
