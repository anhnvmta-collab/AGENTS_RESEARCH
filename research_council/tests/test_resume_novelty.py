from uuid import uuid4

import pytest

from research_council.core.config import Settings
from research_council.core.orchestration import WorkflowEngine, WorkflowState
from research_council.core.orchestration.novelty import NoveltyLoop
from research_council.schemas.models import (
    Evidence,
    NoveltyCandidate,
    NoveltyDecision,
    PriorArtReport,
    ReviewerReport,
)


async def test_resume_performs_pending_targeted_search_before_revision():
    gap_id = uuid4()
    evidence = Evidence(
        paper_id=uuid4(),
        evidence_type="test",
        source_location="test",
        verbatim_excerpt="Test",
        normalized_statement="Test",
        extraction_agent="test",
    )
    candidate = NoveltyCandidate(
        gap_ids=[gap_id],
        evidence_ids=[evidence.evidence_id],
        normalized_claim="Test claim",
        keywords=["test"],
        what_is_new="Test",
        why_it_matters="Test",
        why_prior_methods_insufficient="Test",
        proposed_method="Test",
        validation_plan="Test",
    )
    events = []
    checkpoints = []

    class Operations:
        fail_search = True

        async def generate(self, state, iteration):
            events.append(f"generate {iteration}")
            return [candidate.model_copy(update={"revision": iteration})]

        async def prior_art(self, candidate, state):
            return PriorArtReport(candidate_id=candidate.candidate_id, revision=candidate.revision)

        async def review(self, candidate, state):
            return ReviewerReport(candidate_id=candidate.candidate_id, revision=candidate.revision)

        async def judge(self, candidate, prior_art, review, state):
            return NoveltyDecision(
                candidate_id=candidate.candidate_id,
                revision=candidate.revision,
                required_followup_searches=["targeted"],
            )

        async def targeted_search(self, queries, state):
            events.append("search")
            if self.fail_search:
                raise RuntimeError("interrupted before targeted search")
            return state

    operations = Operations()

    async def checkpoint(state):
        checkpoints.append(state.model_copy(deep=True))

    loop = NoveltyLoop(operations, max_iterations=2)
    with pytest.raises(RuntimeError):
        await loop.run(WorkflowState(evidence=[evidence]), checkpoint)
    assert checkpoints[-1].pending_targeted_queries == ["targeted"]
    operations.fail_search = False
    events.clear()
    result = await loop.run(checkpoints[-1], checkpoint)
    assert events[:2] == ["search", "generate 2"]
    assert result.novelty_iteration == 2
    assert result.decisions[-1].verdict == "UNRESOLVED"


async def test_resume_rejects_changed_configuration(repository):
    repo, run = repository
    settings = Settings()
    settings.research.max_novelty_iterations = 2
    with pytest.raises(ValueError, match="mismatch"):
        await WorkflowEngine(repo, settings, []).resume(run.run_id)
