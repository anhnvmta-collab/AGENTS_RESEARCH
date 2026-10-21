import asyncio

import httpx
import pytest

from research_council.core.config import Settings
from research_council.core.orchestration.engine import Stage
from research_council.core.routing import ModelRouter
from research_council.core.runtime import Runtime, create_run
from research_council.providers.fake import FakeProvider
from research_council.schemas.models import Mode, ResearchPlan, TaskProfile
from research_council.validation.budget import BudgetLedger, LiveBudgetExhausted, LiveResearchBudget


@pytest.mark.parametrize("operation", ["search_calls", "deep_reads"])
def test_live_operation_limits_admit_no_extra_work(operation):
    ledger = BudgetLedger(LiveResearchBudget(max_search_calls=1, max_deep_reads=1))
    ledger.consume(operation)
    with pytest.raises(LiveBudgetExhausted):
        ledger.consume(operation)
    assert getattr(ledger.usage, operation) == 1 and ledger.usage.exhausted


async def test_concurrent_model_reservations_never_exceed_live_limit(repository):
    repo, run = repository
    provider = FakeProvider(delay=0.01)
    router = ModelRouter(Settings(), {"fake": provider}, repo, run.run_id)
    ledger = BudgetLedger(LiveResearchBudget(max_model_calls=1))
    router.live_budget = ledger
    results = await asyncio.gather(
        *(router.generate(TaskProfile.SYNTHESIS, "test", "", "", ResearchPlan) for _ in range(2)),
        return_exceptions=True,
    )
    assert sum(isinstance(result, ResearchPlan) for result in results) == 1
    assert len(provider.requests) == 1 and ledger.usage.model_calls == 1
    cost = BudgetLedger(LiveResearchBudget(max_total_cost=1))
    cost.reserve_model(0.8)
    with pytest.raises(LiveBudgetExhausted):
        cost.reserve_model(0.3)


async def test_budget_exhaustion_preserves_partial_stage_and_resume_counters(repository, tmp_path):
    repo, run = repository
    settings = Settings(live_research_budget=LiveResearchBudget(max_model_calls=1))
    run.config_fingerprint = settings.fingerprint()
    repo.save_run(run)
    async with Runtime(tmp_path, repo, settings, run) as pipeline:

        async def partial(run, state):
            await pipeline.router.generate(TaskProfile.SYNTHESIS, "first", "", "", ResearchPlan)
            state.limitations.append("first operation saved")
            await pipeline.safe(
                pipeline.router.generate(TaskProfile.SYNTHESIS, "second", "", "", ResearchPlan),
                ResearchPlan(),
                state,
                "second",
            )
            return state

        pipeline.stages = lambda mode: [Stage("partial", partial)]
        result = await pipeline.engine(Mode.DEEP).resume(run.run_id)
        assert result.status == "BUDGET_EXHAUSTED"
        assert "first operation saved" in repo.artifacts(run.run_id)["state"]["limitations"]
    async with Runtime(tmp_path, repo, settings, run) as pipeline:
        assert pipeline.router.live_budget.usage.model_calls == 1
        assert pipeline.router.live_budget.usage.exhausted


async def test_scholarly_http_attempts_are_counted_before_request(repository, tmp_path):
    repo, run = repository
    settings = Settings(live_research_budget=LiveResearchBudget(max_search_calls=1))
    runtime = Runtime(tmp_path, repo, settings, run)
    await runtime.client.aclose()
    calls = []

    def handler(request):
        calls.append(request)
        return httpx.Response(200, json={})

    runtime.client = httpx.AsyncClient(
        transport=httpx.MockTransport(handler), event_hooks={"request": [runtime._admit_http]}
    )
    async with runtime:
        await runtime.client.get("https://api.crossref.org/works")
        with pytest.raises(LiveBudgetExhausted):
            await runtime.client.get("https://api.crossref.org/works")
    assert len(calls) == 1


def test_scientific_live_configuration_requires_explicit_confirmation(repository):
    repo, run = repository
    settings = Settings(science_benchmark="CS_FHSS_DOA_FPGA")
    with pytest.raises(ValueError, match="confirm-paid-apis"):
        create_run(repo, run.question, Mode.NOVELTY, settings, live=True)
