import pytest

from research_council.core.config import Route, Settings
from research_council.core.routing import ModelRouter
from research_council.providers.base import LLMResponse
from research_council.providers.fake import FakeProvider
from research_council.schemas.models import ModelExecution, ResearchPlan, TaskProfile


async def test_missing_usage_is_budgeted_as_upper_bound(repository):
    repo, run = repository
    provider = FakeProvider([LLMResponse(text="{}", usage_available=False)])
    provider.name = "mock_live"
    settings = Settings(retries=0)
    settings.models[TaskProfile.SYNTHESIS] = [
        Route(
            provider="mock_live",
            model="configured",
            input_cost_per_million=1,
            output_cost_per_million=1,
        )
    ]
    router = ModelRouter(settings, {"mock_live": provider}, repo, run.run_id)
    await router.generate(TaskProfile.SYNTHESIS, "test", "rules", "data", ResearchPlan)
    record = repo.list_all("model_executions", ModelExecution, run.run_id)[0]
    assert record.cost_basis == "reserved_upper_bound" and record.estimated_cost > 0


async def test_truncated_completion_cannot_count_as_success(repository):
    repo, run = repository
    provider = FakeProvider([LLMResponse(text="{}", finish_reason="incomplete")])
    router = ModelRouter(Settings(retries=0), {"fake": provider}, repo, run.run_id)
    with pytest.raises(RuntimeError):
        await router.generate(TaskProfile.SYNTHESIS, "test", "", "", ResearchPlan)
    record = repo.list_all("model_executions", ModelExecution, run.run_id)[0]
    assert record.status == "FAILED" and not record.structured_output_valid
