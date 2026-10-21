from uuid import uuid4

from research_council.core.orchestration.state import WorkflowState
from research_council.evaluation import GoldLabels, HumanScores, evaluate
from research_council.schemas.models import (
    ClaimType,
    Evidence,
    Paper,
    PaperCandidate,
    PaperMetadata,
    ResearchClaim,
)


def test_unmeasured_is_not_perfect():
    result = evaluate(WorkflowState(), [], [])
    assert result.metrics["citation_precision"] is None
    assert result.metrics["novelty_false_positive_rate"] is None
    assert result.metrics["structured_output_success"] is None


def test_grounding_and_gold_labels():
    paper = Paper(
        metadata=PaperMetadata(title="Synthetic record", metadata_source="fixture"),
        provenance="fixture",
        source_text="Fixture content.",
    )
    evidence = Evidence(
        paper_id=paper.paper_id,
        evidence_type="test",
        source_location="fixture",
        verbatim_excerpt="Fixture content.",
        normalized_statement="Test",
        extraction_agent="test",
    )
    claim = ResearchClaim(
        statement="Test",
        claim_type=ClaimType.AUTHOR_REPORTED,
        source_paper_ids=[paper.paper_id],
        evidence_ids=[evidence.evidence_id],
    )
    state = WorkflowState(
        candidates=[PaperCandidate(paper=paper)], evidence=[evidence], claims=[claim]
    )
    labels = GoldLabels(
        paper_exists={paper.paper_id: False},
        paper_identity_correct={paper.paper_id: True},
        candidate_is_novel={uuid4(): False},
    )
    scores = HumanScores(reviewer="test reviewer", technical_depth=0.5)
    result = evaluate(state, [], [], labels, scores)
    assert result.metrics["citation_precision"] == 0
    assert result.metrics["hallucinated_reference_rate"] == 1
    assert result.metrics["citation_completeness"] == 1
    assert result.metrics["evidence_grounding_rate"] == 1
    assert result.human_scores.technical_depth == 0.5


def test_stale_novelty_acceptance_is_excluded_and_usage_is_measured():
    from test_novelty import candidate_and_evidence

    from research_council.schemas.models import ModelExecution, NoveltyDecision, QualityGateResult

    candidate, evidence = candidate_and_evidence()
    newer = candidate.model_copy(update={"revision": 2})
    state = WorkflowState(
        novelty_candidates=[candidate, newer],
        evidence=[evidence],
        decisions=[
            NoveltyDecision(candidate_id=candidate.candidate_id, revision=1, verdict="SURVIVE"),
            NoveltyDecision(candidate_id=candidate.candidate_id, revision=2, verdict="REJECT"),
        ],
        gates=[
            QualityGateResult(
                gate=2, passed=True, candidate_id=candidate.candidate_id, candidate_revision=1
            )
        ],
    )
    execution = ModelExecution(
        run_id=uuid4(),
        agent_id="test",
        task="test",
        provider="fake",
        model="test",
        input_tokens=40,
        output_tokens=10,
        estimated_cost=0,
    )
    result = evaluate(
        state,
        [execution],
        [],
        GoldLabels(candidate_revision_is_novel={f"{candidate.candidate_id}:2": False}),
        HumanScores(
            reviewer="test",
            research_usefulness=0.5,
            hardware_realism=0.4,
            publication_readiness=0.1,
        ),
    )
    assert result.metrics["novelty_false_positive_rate"] == 0
    assert result.metrics["total_tokens"] == 50 and result.metrics["cost_per_run_usd"] == 0
    assert result.denominators["novelty_false_positive_rate"] == 1
    assert evaluate(WorkflowState(), [], []).metrics["total_tokens"] is None
