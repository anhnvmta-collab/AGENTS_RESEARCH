import json

import httpx
import pytest
from pydantic import ValidationError

from research_council import agents
from research_council.agents.contracts import CandidatesOutput
from research_council.core.config import Route, Settings
from research_council.core.routing import ModelRouter
from research_council.providers.base import LLMRequest
from research_council.providers.fake import FakeProvider
from research_council.providers.http import AnthropicProvider
from research_council.providers.schema_transport import (
    SchemaCompatibilityError,
    anthropic_schema,
    count_features,
)
from research_council.schemas.models import HardwareAssessment, ResearchPlan, TaskProfile


def test_map_codec_preserves_values_and_original_validation():
    original = HardwareAssessment(
        platform="Synthetic FPGA",
        parameters={"clock_mhz": 125.0, "notes": None},
        parameter_evidence={"clock_mhz": []},
        parameter_provenance={"clock_mhz": "ESTIMATED"},
    )
    codec = anthropic_schema(HardwareAssessment.model_json_schema())
    encoded = codec.convert(original.model_dump(mode="json"), encode=True)
    assert isinstance(encoded["parameters"], list)
    decoded = codec.convert(encoded)
    assert HardwareAssessment.model_validate(decoded) == original
    encoded["parameters"].append(encoded["parameters"][0])
    with pytest.raises(ValueError):
        codec.convert(encoded)
    plan = anthropic_schema(ResearchPlan.model_json_schema())
    invalid = plan.convert(
        {
            "objective": "test",
            "tasks": [],
            "inclusion_criteria": [],
            "exclusion_criteria": [],
            "limitations": [],
            "subquestions": [],
        }
    )
    assert invalid["subquestions"] == {}


def test_all_roles_have_explicit_capability_and_no_lossy_maps():
    ready = blocked = 0
    for name in agents.__all__:
        schema = getattr(agents, name).output_schema.model_json_schema()
        original = json.dumps(schema, sort_keys=True)
        try:
            codec = anthropic_schema(schema)
            assert count_features(codec.wire)[0] <= 24
            assert count_features(codec.wire)[1] <= 16
            wire = json.dumps(codec.wire)
            assert '"minimum"' not in wire and '"maxLength"' not in wire
            ready += 1
        except SchemaCompatibilityError:
            blocked += 1
        assert json.dumps(schema, sort_keys=True) == original
    assert ready >= 15 and blocked >= 1


async def test_http_uses_wire_and_router_keeps_canonical_constraints(repository):
    repo, run = repository

    def handle(request):
        body = json.loads(request.content)
        assert "Dictionary encoded" in json.dumps(body)
        assert isinstance(
            body["output_config"]["format"]["schema"]["properties"]["subquestions"]["items"], dict
        )
        return httpx.Response(
            200,
            json={
                "stop_reason": "end_turn",
                "content": [
                    {
                        "type": "text",
                        "text": json.dumps(
                            {
                                "subquestions": [
                                    {
                                        "key": "extra",
                                        "value": {
                                            "topic": "x",
                                            "constraints": [],
                                            "audit_claim": None,
                                        },
                                    }
                                ]
                            }
                        ),
                    }
                ],
                "usage": {"input_tokens": 7, "output_tokens": 11},
            },
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handle)) as client:
        provider = AnthropicProvider(client, api_key="offline-test-only")
        response = await provider.generate(
            LLMRequest(
                model="claude-sonnet-5-5",
                system="Return a plan",
                user="Synthetic",
                output_schema=ResearchPlan.model_json_schema(),
            )
        )
        with pytest.raises(ValidationError):
            ResearchPlan.model_validate_json(response.text)
        settings = Settings(retries=0)
        settings.models[TaskProfile.SEARCH_PLANNING] = [
            Route(
                provider="anthropic",
                model="claude-sonnet-5-5",
                input_cost_per_million=1,
                output_cost_per_million=1,
            ),
            Route(),
        ]
        router = ModelRouter(
            settings, {"anthropic": provider, "fake": FakeProvider()}, repo, run.run_id
        )
        result = await router.generate(
            TaskProfile.SEARCH_PLANNING, "PaperScout", "system", "{}", CandidatesOutput
        )
        assert isinstance(result, CandidatesOutput)
        assert repo.artifacts(run.run_id)["schema_fallback_PaperScout"]["status"].startswith(
            "BLOCKED_UNION_LIMIT"
        )
        assert all(row.provider == "fake" for row in repo.list_model_executions(run.run_id))
