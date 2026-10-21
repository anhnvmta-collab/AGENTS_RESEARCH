import json

import httpx
import pytest

from research_council.agents.contracts import QuestionInput
from research_council.agents.research_planner import ResearchPlanner
from research_council.core.config import Settings
from research_council.core.routing import ModelRouter
from research_council.providers.base import LLMRequest, LLMResponse
from research_council.providers.fake import FakeProvider
from research_council.providers.http import AnthropicProvider, GeminiProvider, OpenAIProvider
from research_council.schemas.models import ModelExecution, ResearchPlan, Schema, TaskProfile


class ProtocolResult(Schema):
    result: str


@pytest.mark.parametrize(
    "provider_type,model,host,path",
    [
        (OpenAIProvider, "gpt-6.1-sol", "api.openai.com", "/v1/responses"),
        (AnthropicProvider, "claude-sonnet-5-5", "api.anthropic.com", "/v1/messages"),
        (
            GeminiProvider,
            "gemini-4-argon",
            "generativelanguage.googleapis.com",
            "/v1beta/models/gemini-4-argon:generateContent",
        ),
    ],
)
async def test_candidate_model_wire_contract_and_thinking_isolation(
    provider_type, model, host, path
):
    # Supported small schema only; this does not assert compatibility of all research schemas.
    def wire(request):
        assert request.url.host == host and request.url.path == path
        assert "unit-test-key" not in str(request.url)
        body = json.loads(request.content)
        assert (
            body["model"] == model if provider_type is not GeminiProvider else "model" not in body
        )
        assert not {"temperature", "top_p", "top_k", "reasoning_effort"} & set(body)
        if provider_type is OpenAIProvider:
            assert body["max_output_tokens"] == 256 and body["store"] is False
            assert body["text"]["format"]["type"] == "json_schema"
            assert body["text"]["format"]["strict"] is False
            assert "reasoning" not in body  # Documented medium default, not none/minimal.
            data = {
                "status": "completed",
                "output": [
                    {
                        "type": "reasoning",
                        "summary": [{"type": "summary_text", "text": "Not the result"}],
                    },
                    {
                        "type": "message",
                        "content": [{"type": "output_text", "text": '{"result":"ok"}'}],
                    },
                ],
                "usage": {
                    "input_tokens": 7,
                    "output_tokens": 20,
                    "output_tokens_details": {"reasoning_tokens": 12},
                },
            }
        elif provider_type is AnthropicProvider:
            assert body["max_tokens"] == 256 and "max_output_tokens" not in body
            assert body["output_config"]["format"]["schema"] == ProtocolResult.model_json_schema()
            assert "thinking" not in body and "tool_choice" not in body
            assert request.headers["anthropic-version"] == "2023-06-01"
            data = {
                "stop_reason": "end_turn",
                "content": [
                    {"type": "thinking", "thinking": "", "signature": "unit-signature"},
                    {"type": "text", "text": '{"result":"ok"}'},
                ],
                "usage": {"input_tokens": 7, "output_tokens": 20},
            }
        else:
            config = body["generationConfig"]
            assert (
                config["maxOutputTokens"] == 256
                and config["responseMimeType"] == "application/json"
            )
            assert config["responseJsonSchema"] == ProtocolResult.model_json_schema()
            assert config["thinkingConfig"] == {"thinkingLevel": "MEDIUM"}
            assert "thinkingBudget" not in config["thinkingConfig"]
            data = {
                "candidates": [
                    {
                        "finishReason": "STOP",
                        "content": {
                            "parts": [
                                {"thought": True, "text": "Not the result"},
                                {"text": '{"result":"ok"}', "thoughtSignature": "unit-signature"},
                            ]
                        },
                    }
                ],
                "usageMetadata": {
                    "promptTokenCount": 7,
                    "candidatesTokenCount": 8,
                    "thoughtsTokenCount": 12,
                },
            }
        return httpx.Response(200, json=data)

    async with httpx.AsyncClient(transport=httpx.MockTransport(wire)) as client:
        result, response = await provider_type(client, api_key="unit-test-key").generate_structured(
            LLMRequest(
                model=model,
                system="Protocol test only",
                user="No scientific task",
                max_output_tokens=256,
            ),
            ProtocolResult,
        )
    assert result.result == "ok" and response.input_tokens == 7 and response.output_tokens == 20


async def test_continuation_is_not_accepted_as_complete_json(repository):
    repo, run = repository
    provider = FakeProvider(
        [LLMResponse(text='{"objective":"partial"}', finish_reason="CONTINUATION")]
    )
    router = ModelRouter(Settings(retries=0), {"fake": provider}, repo, run.run_id)
    with pytest.raises(RuntimeError):
        await router.generate(TaskProfile.SEARCH_PLANNING, "unit", "", "", ResearchPlan)
    assert len(provider.requests) == 1
    assert repo.list_all("model_executions", ModelExecution, run.run_id)[0].status == "FAILED"


@pytest.mark.parametrize("configured_timeout", [0.5, 60, 180, 600])
async def test_configured_agent_timeout_is_honored_without_waiting(
    repository, monkeypatch, configured_timeout
):
    repo, run = repository
    router = ModelRouter(
        Settings(timeout_seconds=configured_timeout), {"fake": FakeProvider()}, repo, run.run_id
    )
    observed = []

    async def capture(*args, **kwargs):
        observed.append(kwargs["timeout_seconds"])
        return ResearchPlan()

    monkeypatch.setattr(router, "generate", capture)
    await ResearchPlanner(router).execute(
        QuestionInput(task="Offline timeout forwarding test", question=run.question)
    )
    assert observed == [configured_timeout]


async def test_explicit_role_timeout_still_caps_configured_timeout(repository, monkeypatch):
    repo, run = repository
    router = ModelRouter(Settings(timeout_seconds=180), {"fake": FakeProvider()}, repo, run.run_id)
    observed = []

    async def capture(*args, **kwargs):
        observed.append(kwargs["timeout_seconds"])
        return ResearchPlan()

    monkeypatch.setattr(router, "generate", capture)
    agent = ResearchPlanner(router)
    agent.timeout = 12
    await agent.execute(QuestionInput(task="Offline role deadline test", question=run.question))
    assert observed == [12]
