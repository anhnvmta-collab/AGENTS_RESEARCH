from uuid import uuid4

import pytest

from research_council.core.config import Settings
from research_council.core.human_review import ScientificAttestation, attest_claim
from research_council.core.orchestration.state import WorkflowState
from research_council.schemas.models import (
    Paper,
    PaperCandidate,
    PaperMetadata,
    PriorArtMatch,
    PriorArtReport,
)
from research_council.validation.disagreement import ModelDisagreement
from research_council.validation.identity import PaperIdentityAudit
from research_council.validation.prior_art import merge_prior_art_sources, prior_art_quotes
from research_council.validation.reviews import HumanReviewBundle, apply_disagreement_resolutions


@pytest.mark.parametrize(
    "science,conflict,allowed", [(False, False, False), (True, False, True), (True, True, False)]
)
def test_scientific_premises_can_be_reviewed_before_novelty_without_waiving_conflicts(
    repository, science, conflict, allowed
):
    from test_regressions import human_ready_state

    repo, run = repository
    state = human_ready_state()
    state.pending_approval = "after_gaps"
    run.status = "PAUSED"
    if conflict:
        state.identity_audits = [
            PaperIdentityAudit(
                paper_id=state.candidates[0].paper.paper_id, conflicts=["SAME_DOI_DIFFERENT_TITLE"]
            )
        ]
    settings = Settings(science_benchmark="CS_FHSS_DOA_FPGA" if science else None)
    repo.checkpoint(run, {"state": state, "settings": settings})
    review = ScientificAttestation(
        claim_id=state.claims[0].claim_id,
        reviewer="Named test expert",
        note="Explicit source and scientific premise review for this regression.",
        source_identity_checked=True,
        source_locations_checked=True,
        scientific_entailment_checked=True,
        retraction_status_checked=True,
    )
    if allowed:
        result = attest_claim(repo, run.run_id, review)
        assert result.evidence[0].verification_status == "VERIFIED"
        assert result.pending_approval == "after_gaps"
    else:
        with pytest.raises(ValueError):
            attest_claim(repo, run.run_id, review)


@pytest.mark.parametrize("same_snapshot", [True, False])
def test_prior_art_quotes_survive_identity_dedup_only_with_grounded_snapshot(same_snapshot):
    # Local unit source only; no claim that this is a real publication or model result.
    old = Paper(
        metadata=PaperMetadata(
            title="Unit prior art", authors=["Test author"], metadata_source="unit-test"
        ),
        source_text="Existing sparse recovery method overlaps the proposed method.",
        source_kind="abstract",
        provenance="local",
    )
    quoted = prior_art_quotes([old], "sparse recovery")
    assert quoted and quoted[0].verification_status == "PARTIALLY_VERIFIED"
    assert quoted[0].verbatim_excerpt in old.source_text
    retained = old.model_copy(deep=True, update={"paper_id": uuid4()})
    if not same_snapshot:
        retained.source_text = "A different retained source cannot substantiate the original quote."
    state = WorkflowState(candidates=[PaperCandidate(paper=retained)])
    candidate_id = uuid4()
    report = PriorArtReport(
        candidate_id=candidate_id,
        revision=1,
        complete=True,
        discovered_evidence=quoted,
        matches=[
            PriorArtMatch(
                candidate_id=candidate_id,
                paper_id=old.paper_id,
                similarity=0.9,
                overlap="method",
                evidence_ids=[quoted[0].evidence_id],
            )
        ],
    )
    merge_prior_art_sources(report, [old], state)
    if same_snapshot:
        assert report.complete and report.matches[0].paper_id == retained.paper_id
        assert report.matches[0].evidence_ids == [state.evidence[0].evidence_id]
        assert state.evidence[0].chunk_id == state.chunks[0].chunk_id
    else:
        assert not report.complete and report.search_failures
        assert not report.matches and not state.evidence


def test_named_resolution_preserves_both_model_positions():
    conflict = ModelDisagreement(
        subject_id="hardware:1",
        task="hardware",
        model_A="A",
        model_B="B",
        provider_A="mock_A",
        provider_B="mock_B",
        execution_A=uuid4(),
        execution_B=uuid4(),
        position_A="Feasible under stated clock assumptions",
        position_B="Clock assumption lacks source evidence",
        severity="HIGH",
    )
    state = WorkflowState(model_disagreements=[conflict])
    bundle = HumanReviewBundle(
        reviewer="Named test expert",
        note="Independent review of the specified source and clock assumptions.",
        disagreement_resolutions={
            conflict.disagreement_id: "Use the conservative clock assumption and retain both model positions."
        },
    )
    apply_disagreement_resolutions(bundle, state)
    assert state.model_disagreements[0].resolution_status == "RESOLVED"
    assert state.model_disagreements[0].position_A == conflict.position_A
    assert state.model_disagreements[0].position_B == conflict.position_B
    bundle.disagreement_resolutions = {
        uuid4(): "Unknown disagreement must not be cleared by a human bundle."
    }
    with pytest.raises(ValueError, match="absent"):
        apply_disagreement_resolutions(bundle, state)


@pytest.mark.parametrize("forged_evidence", [False, True])
async def test_prior_art_hunter_uses_new_source_quotes_and_rejects_invented_overlap(
    repository, forged_evidence
):
    from research_council.agents.contracts import CandidatesOutput, ReviewInput, SearchInput
    from research_council.agents.prior_art_hunter import PriorArtHunter
    from research_council.core.routing import ModelRouter
    from research_council.providers.base import LLMResponse
    from research_council.providers.fake import FakeProvider
    from research_council.schemas.models import SearchAttempt
    from research_council.tools.registry import ToolRegistry

    repo, run = repository
    paper = Paper(
        metadata=PaperMetadata(
            title="Unit prior-art source", authors=["Unit author"], metadata_source="unit-test"
        ),
        source_kind="abstract",
        source_text="Existing sparse recovery uses the same signal model.",
        provenance="local",
    )
    quote = prior_art_quotes([paper], "sparse recovery")[0]
    candidate_id = uuid4()
    proposed_report = PriorArtReport(
        candidate_id=candidate_id,
        revision=1,
        matches=[
            PriorArtMatch(
                candidate_id=candidate_id,
                paper_id=paper.paper_id,
                similarity=0.9,
                overlap="Signal-model overlap",
                evidence_ids=[uuid4() if forged_evidence else quote.evidence_id],
                overlap_components={"signal_model": "same model"},
            )
        ],
    )
    fake = FakeProvider([LLMResponse(text=proposed_report.model_dump_json())])
    tools = ToolRegistry()

    async def search(value):
        return CandidatesOutput(
            candidates=[PaperCandidate(paper=paper)],
            attempts=[
                SearchAttempt(adapter="unit-test", query=query, status="SUCCESS")
                for query in value.queries
            ],
        )

    async def chains(value):
        return CandidatesOutput()

    tools.register("search", SearchInput, search)
    tools.register("citation_search", SearchInput, chains)
    hunter = PriorArtHunter(
        ModelRouter(
            Settings(science_benchmark="CS_FHSS_DOA_FPGA"), {"fake": fake}, repo, run.run_id
        ),
        tools,
    )
    value = ReviewInput(
        task="Attack the proposed signal model",
        candidate_id=candidate_id,
        revision=1,
        normalized_claim="Sparse recovery signal model",
        technical_keywords=["sparse", "recovery"],
    )
    if forged_evidence:
        with pytest.raises(ValueError, match="source-specific"):
            await hunter.run(value)
    else:
        report = await hunter.run(value)
        assert report.complete and report.matches[0].evidence_ids == [quote.evidence_id]
        assert report.discovered_evidence[0].source_sha256 == quote.source_sha256
        assert report.discovered_evidence[0].verification_status == "PARTIALLY_VERIFIED"
