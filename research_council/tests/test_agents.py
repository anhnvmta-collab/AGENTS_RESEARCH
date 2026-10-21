from uuid import uuid4

import pytest
from pydantic import ValidationError

from research_council.agents import ResearchPlanner
from research_council.agents.contracts import QuestionInput, ReviewInput
from research_council.core.config import Settings
from research_council.core.context import independent_review
from research_council.core.routing import ModelRouter
from research_council.providers.fake import FakeProvider
from research_council.schemas.models import NoveltyCandidate
from research_council.tools.registry import ToolRegistry


async def test_agent_contract_and_observation(repository):
    repo, run = repository
    provider = FakeProvider()
    agent = ResearchPlanner(ModelRouter(Settings(), {"fake": provider}, repo, run.run_id))
    output = await agent.run(QuestionInput(task="Plan", question=run.question))
    assert output.objective
    assert "ANTI-HALLUCINATION" in provider.requests[0].system
    assert "untrusted_task_data" in provider.requests[0].user
    assert "No module" not in agent.prompt()


async def test_tool_permissions():
    tools = ToolRegistry()
    with pytest.raises(PermissionError):
        await tools.invoke("search", {}, allowlist=frozenset({"evidence_read"}))


def test_reviewer_isolation():
    candidate = NoveltyCandidate(
        gap_ids=[uuid4()],
        evidence_ids=[uuid4()],
        normalized_claim="Test claim",
        keywords=["test"],
        what_is_new="Persuasion",
        why_it_matters="SECRET_GENERATOR_REASON",
        why_prior_methods_insufficient="persuasion",
        proposed_method="method",
        validation_plan="plan",
    )
    review = independent_review(candidate, [])
    assert "SECRET_GENERATOR_REASON" not in review.model_dump_json()
    assert "Persuasion" not in review.model_dump_json()
    with pytest.raises(ValidationError):
        ReviewInput.model_validate({**review.model_dump(), "generator_reasoning": "leak"})
