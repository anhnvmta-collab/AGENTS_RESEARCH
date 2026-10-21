import pytest

from research_council.core.config import Route, Settings, load_settings
from research_council.core.routing import ModelRouter
from research_council.providers.fake import FakeProvider
from research_council.schemas.models import ResearchPlan, TaskProfile


def test_role_routes_and_model_environment_are_supported(tmp_path, monkeypatch):
    monkeypatch.setenv("OPENAI_DIRECTOR_MODEL", "configured-model-id")
    path = tmp_path / "config.yaml"
    path.write_text(
        "models:\n  director:\n    provider: openai\n    model: ${OPENAI_DIRECTOR_MODEL}\n"
    )
    settings = load_settings(path)
    assert settings.role_routes["ResearchDirector"][0].model == "configured-model-id"
    assert set(settings.models) == set(TaskProfile)
    assert "API_KEY" not in settings.model_dump_json()


def test_configuration_cannot_expand_secrets(tmp_path, monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "private-test-value")
    path = tmp_path / "config.yaml"
    path.write_text('models:\n  SEARCH_PLANNING: [{provider: openai, model: "${OPENAI_API_KEY}"}]')
    with pytest.raises(ValueError) as error:
        load_settings(path)
    assert "private-test-value" not in str(error.value)


async def test_reviewer_prefers_other_actual_provider(repository):
    repo, run = repository
    a, b = FakeProvider(), FakeProvider()
    a.name, b.name = "provider_a", "provider_b"
    settings = Settings()
    settings.role_routes["ReviewerTwo"] = [
        Route(provider="a", input_cost_per_million=0, output_cost_per_million=0),
        Route(provider="b", input_cost_per_million=0, output_cost_per_million=0),
    ]
    router = ModelRouter(settings, {"a": a, "b": b}, repo, run.run_id)
    await router.generate(
        TaskProfile.ADVERSARIAL_REVIEW,
        "ReviewerTwo",
        "rules",
        "claim",
        ResearchPlan,
        avoid_provider="provider_a",
    )
    assert not a.requests and len(b.requests) == 1
    assert router.last_success["ReviewerTwo"].routing_note == "DIFFERENT_PROVIDER_PREFERRED"


async def test_single_provider_fallback_is_explicit(repository):
    repo, run = repository
    router = ModelRouter(Settings(), {"fake": FakeProvider()}, repo, run.run_id)
    await router.generate(
        TaskProfile.ADVERSARIAL_REVIEW,
        "ReviewerTwo",
        "rules",
        "claim",
        ResearchPlan,
        avoid_provider="fake",
    )
    assert router.last_success["ReviewerTwo"].routing_note == "SAME_PROVIDER_FALLBACK"
