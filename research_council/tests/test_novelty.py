from uuid import uuid4

from research_council.core.gates import NoveltySurvivalGate, PublicationReadinessGate
from research_council.core.orchestration.novelty import NoveltyLoop
from research_council.core.orchestration.state import WorkflowState
from research_council.schemas.models import (
    Evidence,
    ModelExecution,
    NoveltyCandidate,
    NoveltyDecision,
    Paper,
    PaperMetadata,
    PriorArtReport,
    QualityGateResult,
    ReviewerReport,
    ReviewReason,
    SearchAttempt,
    SearchQuery,
    VerificationStatus,
)


def candidate_and_evidence():
    item = Evidence(
        paper_id=uuid4(),
        evidence_type="limitation",
        source_location="abstract",
        verbatim_excerpt="Test",
        normalized_statement="Test",
        extraction_agent="test",
        verification_status=VerificationStatus.PARTIALLY_VERIFIED,
    )
    candidate = NoveltyCandidate(
        gap_ids=[uuid4()],
        evidence_ids=[item.evidence_id],
        normalized_claim="Test hypothesis",
        keywords=["test"],
        what_is_new="Test",
        why_it_matters="Test",
        why_prior_methods_insufficient="Test",
        proposed_method="Test",
        validation_plan="Test",
    )
    return candidate, item


def test_novelty_gate_rejects_incomplete_and_severe_reviews():
    candidate, item = candidate_and_evidence()
    prior = PriorArtReport(
        candidate_id=candidate.candidate_id, revision=1, complete=True, queries=["query"]
    )
    review = ReviewerReport(
        candidate_id=candidate.candidate_id, revision=1, complete=True, verdict="SURVIVES"
    )
    decision = NoveltyDecision(candidate_id=candidate.candidate_id, revision=1, verdict="SURVIVE")
    gate = NoveltySurvivalGate(1)
    paper = Paper(
        paper_id=item.paper_id,
        metadata=PaperMetadata(
            title="Unit-test source",
            authors=["Unit-test author"],
            year=2024,
            url="https://example.invalid/unit",
            metadata_source="unit-test",
            metadata_verified=True,
        ),
        source_text="Test",
    )
    prior.search_attempts = [
        SearchAttempt(adapter="mock", query=SearchQuery(text="query"), status="SUCCESS")
    ]
    run_id = uuid4()
    executions = [
        ModelExecution(
            run_id=run_id,
            agent_id=role,
            task="ADVERSARIAL_REVIEW",
            provider="mock",
            model="mock",
            status="SUCCESS",
            structured_output_valid=True,
        )
        for role in ("PriorArtHunter", "ReviewerTwo", "NoveltyJudge")
    ]
    prior.model_execution_id, review.model_execution_id, decision.model_execution_id = [
        record.execution_id for record in executions
    ]
    assert gate.evaluate(candidate, [item], prior, review, decision, [paper], executions).passed
    review.reasons = [
        ReviewReason(category="contradiction", severity="HIGH", explanation="Unresolved")
    ]
    assert not gate.evaluate(candidate, [item], prior, review, decision, [paper], executions).passed
    review.reasons = []
    prior.complete = False
    assert not gate.evaluate(candidate, [item], prior, review, decision, [paper], executions).passed


async def test_novelty_loop_terminates_and_searches_again():
    candidate, item = candidate_and_evidence()

    class Operations:
        searches = 0

        async def generate(self, state, iteration):
            return [candidate.model_copy(update={"revision": iteration})]

        async def prior_art(self, candidate, state):
            return PriorArtReport(
                candidate_id=candidate.candidate_id,
                revision=candidate.revision,
                complete=True,
                queries=["test"],
            )

        async def review(self, candidate, state):
            return ReviewerReport(
                candidate_id=candidate.candidate_id, revision=candidate.revision, complete=True
            )

        async def judge(self, candidate, prior, review, state):
            return NoveltyDecision(
                candidate_id=candidate.candidate_id,
                revision=candidate.revision,
                verdict="SURVIVE",
                required_followup_searches=["targeted"],
            )

        async def targeted_search(self, queries, state):
            self.searches += 1
            return state

    operations = Operations()
    state = await NoveltyLoop(operations, max_iterations=3, minimum_evidence=1).run(
        WorkflowState(evidence=[item])
    )
    assert operations.searches == 2
    assert state.novelty_iteration == 3
    assert all(decision.verdict == "UNRESOLVED" for decision in state.decisions)
    assert not any(gate.passed for gate in state.gates)


def test_publication_gate_cannot_pass_empty_work():
    assert not PublicationReadinessGate().evaluate([], [], [], [], [], []).passed


async def test_saturation_stops_search_and_never_promotes_revision():
    from research_council.core.saturation import SearchSaturationDetector

    candidate, _ = candidate_and_evidence()
    signal = SearchSaturationDetector(patience=1).observe(
        set(), set(), 0, 0, [], search_complete=True
    )
    state = WorkflowState(
        novelty_candidates=[candidate],
        decisions=[NoveltyDecision(candidate_id=candidate.candidate_id, revision=1)],
        saturation=[signal],
    )

    class Operations:
        async def generate(self, state, iteration):
            raise AssertionError("Saturated search should not invoke generation")

    result = await NoveltyLoop(Operations()).run(state)
    assert result.decisions[0].verdict == "UNRESOLVED"
    assert "SEARCH_SATURATED" in result.limitations[-1]


async def test_resume_does_not_trust_cached_gate_boolean():
    class Operations:
        async def generate(self, state, iteration):
            return []

    state = WorkflowState(gates=[QualityGateResult(gate=2, passed=True)])
    result = await NoveltyLoop(Operations()).run(state)
    assert not result.gates[0].passed


def test_observed_knowledge_map_links_methods_without_universal_coverage():
    from test_regressions import human_ready_state

    from research_council.knowledge.mapping import build_knowledge_map

    state = human_ready_state()
    state.candidates[0].paper.metadata.title = "Unit FPGA compressed sensing example"
    root = build_knowledge_map("FHSS", state)
    fpga = next(
        child for branch in root.subtopics for child in branch.subtopics if child.topic == "FPGA"
    )
    assert fpga.paper_ids == [state.candidates[0].paper.paper_id]
    assert fpga.claim_ids == [state.claims[0].claim_id] and fpga.coverage_score == 1
    assert "not universal" in fpga.coverage_basis
