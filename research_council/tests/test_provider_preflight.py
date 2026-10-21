from datetime import date
from pathlib import Path

import httpx
import pytest
import yaml
from typer.testing import CliRunner

from research_council.cli import app
from research_council.core.config import load_settings
from research_council.providers.base import LLMRequest
from research_council.providers.http import GeminiProvider
from research_council.validation.preflight import PROVIDER_KEYS, provider_preflight
from research_council.validation.provider_smoke import provider_smoke


@pytest.fixture
def operator_config(tmp_path, monkeypatch):
    raw = yaml.safe_load(Path("config/phase11.operator.example.yaml").read_text())
    # Fictional model IDs, prices and credentials only for offline contract tests.
    for routes in [*raw["models"].values(), *raw["role_routes"].values()]:
        for route in routes:
            route.update(
                model=f"unit-{route['provider']}-model",
                input_cost_per_million=0.5,
                output_cost_per_million=1,
                pricing_verified_on=date.today(),
            )
    for key in PROVIDER_KEYS.values():
        monkeypatch.setenv(key, "private-unit-test-token")
    monkeypatch.setattr("research_council.cli.providers.load_dotenv", lambda **kwargs: False)
    path = tmp_path / "operator.yaml"

    def save():
        path.write_text(yaml.safe_dump(raw), encoding="utf-8")
        return path

    save()
    return raw, save


def test_safe_preflight_is_complete_and_creates_no_clients(operator_config, monkeypatch):
    _, save = operator_config

    def forbidden(*args, **kwargs):
        raise AssertionError("Non-paid preflight must not create network clients or Runtime")

    monkeypatch.setattr(httpx, "AsyncClient", forbidden)
    monkeypatch.setattr("research_council.validation.provider_smoke.Runtime", forbidden)
    result = CliRunner().invoke(app, ["providers", "preflight", "--config", str(save())])
    assert result.exit_code == 0, result.output
    assert '"ready": true' in result.output
    assert '"paid_model_calls_made": 0' in result.output
    assert "private-unit-test-token" not in result.output
    report = provider_preflight(save())
    assert len(report.providers) == 3 and all(item["enabled"] for item in report.providers)
    assert len(report.routing) == 9
    assert all(item["status"] == "CONFIGURED_NOT_TESTED" for item in report.sources)
    assert report.budget["max_total_cost"] == 5 and report.budget["max_model_calls"] == 80


@pytest.mark.parametrize(
    "problem,expected",
    [
        ("model", "MODEL_ID_REQUIRED"),
        ("route", "MISSING_ROUTE"),
        ("price", "MISSING_PRICE"),
        ("budget", "BUDGET_OR_RESEARCH_CONFIGURATION_INVALID"),
        ("budget_field", "EXPLICIT_SIX_FIELD_LIVE_BUDGET_REQUIRED"),
        ("approval", "FIRST_RUN_REQUIRES_HUMAN_APPROVAL"),
    ],
)
def test_preflight_rejects_incomplete_or_unsafe_configuration(operator_config, problem, expected):
    raw, save = operator_config
    if problem == "model":
        raw["models"]["SEARCH_PLANNING"][0]["model"] = "CONFIGURE_ME"
    elif problem == "route":
        del raw["models"]["MATH_REASONING"]
    elif problem == "price":
        raw["models"]["SEARCH_PLANNING"][0]["input_cost_per_million"] = None
    elif problem == "budget":
        raw["live_research_budget"]["max_model_calls"] = -1
    elif problem == "budget_field":
        del raw["live_research_budget"]["max_search_calls"]
    else:
        raw["research"]["human_approval_required"] = False
    report = provider_preflight(save())
    assert not report.ready and any(expected in error for error in report.errors)


def test_missing_keys_and_schema_errors_never_disclose_values(operator_config, monkeypatch):
    raw, save = operator_config
    monkeypatch.delenv("GOOGLE_API_KEY")
    result = CliRunner().invoke(app, ["providers", "preflight", "--config", str(save())])
    assert result.exit_code == 1 and "MISSING_KEY: GOOGLE_API_KEY" in result.output
    assert "private-unit-test-token" not in result.output
    raw["models"]["SEARCH_PLANNING"][0]["input_cost_per_million"] = "private-unit-test-token"
    result = CliRunner().invoke(app, ["providers", "preflight", "--config", str(save())])
    assert result.exit_code == 1 and "private-unit-test-token" not in result.output


def test_disabled_providers_allow_single_provider_with_explicit_diversity_warning(
    operator_config, monkeypatch
):
    raw, save = operator_config
    for routes in [*raw["models"].values(), *raw["role_routes"].values()]:
        for route in routes:
            if route["provider"] != "openai":
                route.update(
                    enabled=False,
                    model="${UNSET_PROVIDER_MODEL}",
                    input_cost_per_million=None,
                    output_cost_per_million=None,
                )
    monkeypatch.delenv("ANTHROPIC_API_KEY")
    monkeypatch.delenv("GOOGLE_API_KEY")
    report = provider_preflight(save())
    assert report.ready, report.errors
    assert any("SAME_PROVIDER_REVIEW_FALLBACK" in warning for warning in report.warnings)
    assert sum(item["enabled"] for item in report.providers) == 1
    assert not load_settings(save()).role_routes["NoveltyJudge"][0].enabled


def test_stale_pricing_and_unwired_ieee_are_explicit(operator_config):
    raw, save = operator_config
    raw["models"]["SEARCH_PLANNING"][0]["pricing_verified_on"] = date(2000, 1, 1)
    raw["search"]["adapters"].append("ieee")
    report = provider_preflight(save())
    assert not report.ready and "IEEE_AUTHENTICATED_BACKEND_NOT_WIRED" in report.errors
    assert any("PRICE_MAY_BE_STALE" in warning for warning in report.warnings)


@pytest.mark.parametrize("live,confirm", [(False, False), (True, False), (False, True)])
async def test_smoke_library_requires_both_flags_before_any_configuration_or_runtime(
    tmp_path, monkeypatch, live, confirm
):
    def forbidden(*args, **kwargs):
        raise AssertionError("Missing consent must prevent Runtime creation")

    monkeypatch.setattr("research_council.validation.provider_smoke.Runtime", forbidden)
    with pytest.raises(ValueError, match="BOTH"):
        await provider_smoke(
            tmp_path / "not-read.yaml",
            tmp_path / "not-created",
            live=live,
            confirm_paid_apis=confirm,
        )
    assert not (tmp_path / "not-created").exists()


@pytest.mark.parametrize("flag", ["--live", "--confirm-paid-apis"])
def test_smoke_cli_rejects_single_flag_before_configuration(flag):
    result = CliRunner().invoke(app, ["providers", "preflight", "--config", "not-read.yaml", flag])
    assert result.exit_code == 2 and "BOTH" in result.output


@pytest.mark.parametrize("wire_status", [200, 429])
async def test_mocked_three_provider_smoke_is_small_bounded_and_never_starts_research(
    operator_config, monkeypatch, tmp_path, wire_status
):
    _, save = operator_config
    requests = []

    def wire(request):
        import json

        body = json.loads(request.content)
        assert (
            body.get(
                "max_output_tokens",
                body.get("max_tokens", body.get("generationConfig", {}).get("maxOutputTokens")),
            )
            == 128
        )
        requests.append(request.url.host)
        if request.url.host == "api.openai.com":
            data = {
                "output": [{"content": [{"type": "output_text", "text": '{"ok":true}'}]}],
                "usage": {"input_tokens": 5, "output_tokens": 5},
            }
        elif request.url.host == "api.anthropic.com":
            data = {
                "content": [{"type": "text", "text": '{"ok":true}'}],
                "usage": {"input_tokens": 5, "output_tokens": 5},
            }
        else:
            assert request.url.host == "generativelanguage.googleapis.com"
            data = {
                "candidates": [{"content": {"parts": [{"text": '{"ok":true}'}]}}],
                "usageMetadata": {
                    "promptTokenCount": 5,
                    "candidatesTokenCount": 5,
                    "thoughtsTokenCount": 5,
                },
            }
        return httpx.Response(wire_status, json=data)

    original = httpx.AsyncClient
    monkeypatch.setattr(
        httpx,
        "AsyncClient",
        lambda **kwargs: original(**kwargs, transport=httpx.MockTransport(wire)),
    )

    def forbidden(*args, **kwargs):
        raise AssertionError("Provider smoke must never start a research engine")

    monkeypatch.setattr(
        "research_council.core.orchestration.pipeline.ResearchPipeline.engine", forbidden
    )
    result = await provider_smoke(save(), tmp_path / "smoke", live=True, confirm_paid_apis=True)
    assert result["status"] == ("COMPLETED" if wire_status == 200 else "FAILED")
    assert len(requests) == len(set(requests)) == 3
    assert result["maximum_model_attempts"] == result["model_attempts_admitted"] == 3
    assert result["estimated_cost_cap_usd"] == 0.25
    assert (
        result["live_benchmark_executed"] is False
        and result["scientific_readiness_advanced"] is False
    )
    assert result["actual_billed_cost_usd"] is None


async def test_mocked_smoke_budget_denial_prevents_any_http_request(
    operator_config, monkeypatch, tmp_path
):
    raw, save = operator_config
    for routes in raw["models"].values():
        for route in routes:
            route["input_cost_per_million"] = 1_000_000  # Deliberately prohibitive unit-test price.

    def forbidden(*args, **kwargs):
        raise AssertionError("Budget denial must precede HTTP inference")

    monkeypatch.setattr(httpx.AsyncClient, "post", forbidden)
    result = await provider_smoke(
        save(), tmp_path / "smoke-denied", live=True, confirm_paid_apis=True
    )
    assert result["status"] == "BUDGET_EXHAUSTED"
    assert result["model_attempts_admitted"] == 0 and result["estimated_model_cost_usd"] == 0


async def test_disabled_model_route_is_never_called(repository):
    from research_council.core.config import Route, Settings
    from research_council.core.routing import ModelRouter
    from research_council.providers.fake import FakeProvider
    from research_council.schemas.models import ResearchPlan, TaskProfile

    repo, run = repository
    settings = Settings()
    settings.models[TaskProfile.SYNTHESIS] = [
        Route(provider="disabled", enabled=False, model="CONFIGURE_ME"),
        Route(),
    ]
    disabled, active = FakeProvider(), FakeProvider()
    router = ModelRouter(settings, {"disabled": disabled, "fake": active}, repo, run.run_id)
    await router.generate(TaskProfile.SYNTHESIS, "unit", "", "", ResearchPlan)
    assert not disabled.requests and len(active.requests) == 1


async def test_gemini_reasoning_tokens_are_included_in_estimated_output_cost():
    async with httpx.AsyncClient(
        transport=httpx.MockTransport(
            lambda _: httpx.Response(
                200,
                json={
                    "usageMetadata": {
                        "promptTokenCount": 7,
                        "candidatesTokenCount": 8,
                        "thoughtsTokenCount": 12,
                    }
                },
            )
        )
    ) as client:
        response = await GeminiProvider(client, api_key="unit-test-token").generate(
            LLMRequest(model="unit-model", system="", user="")
        )
    assert response.input_tokens == 7 and response.output_tokens == 20
