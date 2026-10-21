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
