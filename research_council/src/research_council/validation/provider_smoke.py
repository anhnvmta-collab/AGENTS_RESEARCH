"""Explicit, separately budgeted provider protocol smoke; never starts research stages."""

from __future__ import annotations

import asyncio
from contextlib import suppress
from pathlib import Path
from typing import Literal

from research_council.core.config import Route, load_settings
from research_council.core.orchestration.engine import RunLease
from research_council.core.runtime import Runtime, create_run, open_repository
from research_council.schemas.models import Mode, ResearchQuestion, Schema, TaskProfile
from research_council.validation.budget import LiveBudgetExhausted, LiveResearchBudget
from research_council.validation.preflight import provider_preflight


class ProviderSmokeResponse(Schema):
    ok: Literal[True]


async def provider_smoke(
    config: Path, workspace: Path, *, live: bool = False, confirm_paid_apis: bool = False
) -> dict[str, object]:
    if not (live and confirm_paid_apis):
        raise ValueError("Provider smoke requires BOTH --live --confirm-paid-apis")
    report = provider_preflight(config)
    if not report.ready:
        raise ValueError("Resolve non-paid preflight errors before provider smoke")
    settings = load_settings(config).model_copy(deep=True)
    choices: dict[str, Route] = {}
    for routes in settings.route_groups():
        for route in routes:
            choices.setdefault(route.provider, route.model_copy(update={"max_output_tokens": 128}))
    cap = min(
        0.25,
        settings.research.budget_usd,
        settings.live_research_budget.max_total_cost if settings.live_research_budget else 0.25,
    )
    settings.retries = 0
    settings.research.budget_usd = cap
    settings.research.max_model_calls = len(choices)
    settings.live_research_budget = LiveResearchBudget(
        max_total_cost=cap,
        max_model_calls=len(choices),
        max_search_calls=0,
        max_core_papers=0,
        max_deep_reads=0,
        max_novelty_iterations=0,
    )
    settings.role_routes = {f"ProviderPreflight_{name}": [route] for name, route in choices.items()}
    repository = open_repository(workspace)
    try:
        run = create_run(
            repository,
            ResearchQuestion(
                topic="PROVIDER_SMOKE_ONLY: structured transport check; no scientific findings"
            ),
            Mode.QUICK,
            settings,
            live=True,
            confirm_paid_apis=True,
        )
        lease = RunLease(repository, run.run_id)
        lease.acquire()
        heartbeat = asyncio.create_task(lease.heartbeat())
        outcomes = []
        try:
            async with Runtime(workspace, repository, settings, run) as pipeline:
                for name in choices:
                    if heartbeat.done():
                        await heartbeat
                    try:
                        await pipeline.router.generate(
                            TaskProfile.SYNTHESIS,
                            f"ProviderPreflight_{name}",
                            'Return only {"ok":true}. Protocol test only.',
                            "No research. Return the requested JSON.",
                            ProviderSmokeResponse,
                            retries=0,
                        )
                        outcomes.append({"provider": name, "status": "PROTOCOL_SMOKE_PASSED"})
                    except LiveBudgetExhausted:
                        outcomes.append({"provider": name, "status": "BUDGET_EXHAUSTED"})
                        break
                    except (RuntimeError, ValueError):
                        outcomes.append({"provider": name, "status": "PROTOCOL_SMOKE_FAILED"})
            records = repository.list_model_executions(run.run_id)
            exhausted = (
                repository.artifacts(run.run_id)
                .get("live_budget_usage", {})
                .get("exhausted", False)
            )
            run.status = (
                "BUDGET_EXHAUSTED"
                if exhausted
                else "COMPLETED"
                if len(outcomes) == len(choices)
                and all(item["status"] == "PROTOCOL_SMOKE_PASSED" for item in outcomes)
                else "FAILED"
            )
            repository.save_run(run)
            return {
                "mode": "PROVIDER_SMOKE_ONLY",
                "run_id": str(run.run_id),
                "status": run.status,
                "providers": outcomes,
                "maximum_model_attempts": len(choices),
                "model_attempts_admitted": len(records),
                "max_output_tokens_per_request": 128,
                "estimated_cost_cap_usd": cap,
                "estimated_model_cost_usd": sum(item.estimated_cost or 0 for item in records),
                "actual_billed_cost_usd": None,
                "live_benchmark_executed": False,
                "scientific_readiness_advanced": False,
            }
        finally:
            heartbeat.cancel()
            with suppress(asyncio.CancelledError):
                await heartbeat
            lease.release()
    finally:
        repository.engine.dispose()
