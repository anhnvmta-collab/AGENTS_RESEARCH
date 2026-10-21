"""Never selected by default; real operator configuration and explicit confirmations required."""

import os
from pathlib import Path

import httpx
import pytest

from research_council.core.config import load_settings
from research_council.core.runtime import Runtime, create_run, open_repository
from research_council.schemas.models import Mode, ResearchPlan, ResearchQuestion, TaskProfile
from research_council.tools.search import CrossrefAdapter
from research_council.validation.budget import LiveResearchBudget

pytestmark = pytest.mark.live


async def test_live_crossref_known_reference():
    async with httpx.AsyncClient(timeout=30) as client:
        metadata = await CrossrefAdapter(client).resolve("10.1109/JSTSP.2010.2042414")
    assert metadata is not None and metadata.doi == "10.1109/jstsp.2010.2042414"
    assert "sub-nyquist" in metadata.title.lower()


async def test_live_configured_model_structured_smoke(tmp_path):
    config = os.environ.get("RESEARCH_COUNCIL_LIVE_CONFIG")
    if not config:
        raise pytest.UsageError(
            "Set RESEARCH_COUNCIL_LIVE_CONFIG to an operator-configured YAML file"
        )
    settings = load_settings(Path(config))
    settings.science_benchmark = "CS_FHSS_DOA_FPGA"
    settings.retries = 0
    settings.live_research_budget = LiveResearchBudget(
        max_total_cost=min(settings.research.budget_usd, 0.25),
        max_model_calls=1,
        max_search_calls=0,
    )
    for routes in settings.route_groups():
        for route in routes:
            route.max_output_tokens = 256
    repo = open_repository(tmp_path)
    try:
        run = create_run(
            repo,
            ResearchQuestion(topic="Structured protocol smoke only; no scientific findings"),
            Mode.QUICK,
            settings,
            live=True,
            confirm_paid_apis=True,
        )
        async with Runtime(tmp_path, repo, settings, run) as pipeline:
            result = await pipeline.router.generate(
                TaskProfile.SYNTHESIS,
                "live_protocol_smoke",
                "Return a brief plan, empty lists/maps where appropriate, and no scientific findings.",
                "Protocol validation only.",
                ResearchPlan,
            )
            assert isinstance(result, ResearchPlan)
    finally:
        repo.engine.dispose()
