import json

import httpx
import pytest

from research_council.core.config import Route, Settings
from research_council.core.routing import BudgetExceeded, ModelRouter
from research_council.providers.base import LLMRequest, LLMResponse, ProviderError
from research_council.providers.fake import FakeProvider
from research_council.providers.http import AnthropicProvider, GeminiProvider, OpenAIProvider
from research_council.schemas.models import ModelExecution, ResearchPlan, TaskProfile


async def test_structured_retry_and_metrics(repository):
    repo, run = repository
    provider = FakeProvider(
        [
            LLMResponse(text='{"objective": 12}', input_tokens=20),
            LLMResponse(text='{"objective": "Grounded plan"}', input_tokens=30),
        ]
    )
    settings = Settings(retry_base_seconds=0)
    router = ModelRouter(settings, {"fake": provider}, repo, run.run_id)
    result = await router.generate(
        TaskProfile.SEARCH_PLANNING, "planner", "Rules", "Question", ResearchPlan
    )
    assert result.objective == "Grounded plan"
    records = repo.list_all("model_executions", ModelExecution, run.run_id)
    assert len(records) == 2
    assert sum(item.input_tokens for item in records) == 50
    assert [item.structured_output_valid for item in records] == [False, True]


async def test_provider_failure_fallback(repository):
    repo, run = repository
    bad = FakeProvider([ProviderError(retryable=True)] * 3)
    good = FakeProvider([LLMResponse(text='{"objective":"fallback"}')])
    settings = Settings(retry_base_seconds=0)
    settings.models[TaskProfile.SEARCH_PLANNING] = [
        Route(provider="bad", input_cost_per_million=0, output_cost_per_million=0),
        Route(provider="good", input_cost_per_million=0, output_cost_per_million=0),
    ]
    router = ModelRouter(settings, {"bad": bad, "good": good}, repo, run.run_id)
    assert (
        await router.generate(TaskProfile.SEARCH_PLANNING, "planner", "", "", ResearchPlan)
    ).objective == "fallback"
    assert len(bad.requests) == 3


async def test_timeout_budget_and_stream(repository):
    repo, run = repository
    slow = FakeProvider(delay=0.05)
    settings = Settings(timeout_seconds=0.001, retries=0)
    router = ModelRouter(settings, {"fake": slow}, repo, run.run_id)
    with pytest.raises(RuntimeError):
        await router.generate(TaskProfile.SYNTHESIS, "synthesis", "", "", ResearchPlan)
    settings.research.max_model_calls = 1
    with pytest.raises(BudgetExceeded):
        await router.generate(TaskProfile.SYNTHESIS, "synthesis", "", "", ResearchPlan)
    assert [
        part
        async for part in FakeProvider().stream(LLMRequest(model="offline", system="", user=""))
    ] == ["{}"]


@pytest.mark.parametrize(
    "provider_cls,wire",
    [
        (
            OpenAIProvider,
            {
                "output": [{"content": [{"type": "output_text", "text": '{"objective":"wire"}'}]}],
                "usage": {"input_tokens": 7, "output_tokens": 8},
            },
        ),
        (
            AnthropicProvider,
            {
                "content": [{"type": "text", "text": '{"objective":"wire"}'}],
                "usage": {"input_tokens": 7, "output_tokens": 8},
            },
        ),
        (
            GeminiProvider,
            {
                "candidates": [{"content": {"parts": [{"text": '{"objective":"wire"}'}]}}],
                "usageMetadata": {"promptTokenCount": 7, "candidatesTokenCount": 8},
            },
        ),
    ],
)
async def test_adapter_protocol(provider_cls, wire):
    captured = []

    def handler(request):
        captured.append(json.loads(request.content))
        assert "test-key" not in str(request.url)
        return httpx.Response(200, json=wire)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        provider = provider_cls(client, api_key="test-key")
        result, response = await provider.generate_structured(
            LLMRequest(model="configured-model", system="rules", user="input"), ResearchPlan
        )
    assert result.objective == "wire"
    assert response.input_tokens == 7
    assert "json_schema" in json.dumps(captured) or "responseJsonSchema" in json.dumps(captured)


async def test_rate_limit_and_no_secret_error():
    async with httpx.AsyncClient(
        transport=httpx.MockTransport(
            lambda _: httpx.Response(429, headers={"retry-after": "2"}, text="test-key")
        )
    ) as client:
        with pytest.raises(ProviderError) as error:
            await OpenAIProvider(client, api_key="test-key").generate(
                LLMRequest(model="configured", system="", user="")
            )
    assert error.value.retryable and error.value.retry_after == 2
    assert "test-key" not in str(error.value)
