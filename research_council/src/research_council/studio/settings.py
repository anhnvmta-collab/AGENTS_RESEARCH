from __future__ import annotations

import os
import re
from typing import Any
from uuid import UUID

from research_council import agents
from research_council.core.config import ResearchConfig, Route, Settings
from research_council.providers.schema_transport import SchemaCompatibilityError, anthropic_schema
from research_council.schemas.models import TaskProfile
from research_council.studio.models import StudioError
from research_council.studio.service import StudioService
from research_council.validation.budget import LiveResearchBudget
from research_council.validation.preflight import PROVIDER_KEYS

CANDIDATES = dict.fromkeys(PROVIDER_KEYS, "CONFIGURE_ME")


def defaults() -> Settings:
    routes = [
        Route(provider=provider, model=model, enabled=False)
        for provider, model in CANDIDATES.items()
    ]
    return Settings(
        models={
            profile: [route.model_copy(deep=True) for route in routes] for profile in TaskProfile
        },
        role_routes={
            "NoveltyJudge": [
                routes[1].model_copy(deep=True),
                routes[0].model_copy(deep=True),
                routes[2].model_copy(deep=True),
            ]
        },
        live_research_budget=LiveResearchBudget(),
        research=ResearchConfig(human_approval_required=True),
    )


def current(service: StudioService) -> Settings:
    try:
        return Settings.model_validate(service.store.get("settings", "operator"))
    except KeyError:
        return defaults()


def compatibility() -> list[dict[str, Any]]:
    from research_council.studio.interactions import agent_class

    result = []
    for name in agents.__all__:
        try:
            codec = anthropic_schema(agent_class(name).output_schema.model_json_schema())
            status = "READY_WITH_SCHEMA_TRANSFORM" if codec.transformed else "READY"
            reason = "Canonical Pydantic validation after reversible transport decode"
        except SchemaCompatibilityError as exc:
            status = "BLOCKED"
            reason = str(exc)
        result.append(
            {
                "agent": name,
                "openai": "READY",
                "google": "READY",
                "anthropic": status,
                "reason": reason,
                "verification": "OFFLINE_CONTRACT_ONLY",
            }
        )
    return result


def view(service: StudioService) -> dict[str, Any]:
    from research_council.schemas.models import ModelExecution

    settings = current(service)
    records = service.repository.list_all("model_executions", ModelExecution)
    return {
        "settings": settings.model_dump(mode="json"),
        "compatibility": compatibility(),
        "readiness": readiness(service, settings),
        "providers": [
            {
                "provider": provider,
                "key_present": bool(os.environ.get(key, "").strip()),
                "service_status": "NOT_CONTACTED",
                "enabled": any(
                    route.enabled and route.provider == provider
                    for group in settings.route_groups()
                    for route in group
                ),
                "calls": sum(row.provider == provider for row in records),
                "tokens": sum(
                    row.input_tokens + row.output_tokens
                    for row in records
                    if row.provider == provider
                ),
                "cost": sum(row.estimated_cost or 0 for row in records if row.provider == provider),
                "average_latency": sum(row.latency for row in records if row.provider == provider)
                / max(1, sum(row.provider == provider for row in records)),
            }
            for provider, key in PROVIDER_KEYS.items()
        ],
    }


def readiness(service: StudioService, settings: Settings) -> list[dict[str, Any]]:
    """Local configuration and recorded smoke evidence only; never contact a service."""
    from research_council.schemas.models import ModelExecution

    records = service.repository.list_all("model_executions", ModelExecution)
    result = []
    for name in [*PROVIDER_KEYS, "crossref", "openalex", "arxiv"]:
        is_model = name in PROVIDER_KEYS
        routes = [r for group in settings.route_groups() for r in group if r.provider == name]
        models = sorted({r.model for r in routes})
        configured = (
            bool(routes)
            and all(
                r.model != "CONFIGURE_ME"
                and bool(re.fullmatch(r"[A-Za-z0-9_.-]{3,120}", r.model))
                and r.input_cost_per_million is not None
                and r.output_cost_per_million is not None
                for r in routes
            )
            if is_model
            else name in settings.search.adapters
        )
        key = PROVIDER_KEYS.get(name, "OPENALEX_API_KEY" if name == "openalex" else "")
        present = bool(key and os.environ.get(key, "").strip())
        smoke = [
            row
            for row in records
            if is_model
            and row.provider == name
            and row.model in models
            and row.agent_id == "ProviderPreflight_" + name
            and row.status == "SUCCESS"
            and row.structured_output_valid
            and service.repository.get_run(row.run_id).provenance == "live"
        ]
        tested = bool(models) and set(models) <= {row.model for row in smoke}
        result.append(
            {
                "service": name,
                "configuration_status": "CONFIGURED" if configured else "BLOCKED",
                "credential_status": (
                    "CREDENTIAL_PRESENT" if present else "MISSING" if key else "NOT_REQUIRED"
                ),
                "access_status": "SMOKE_TESTED" if tested else "NOT_TESTED",
                "status": (
                    "BLOCKED"
                    if not configured or (is_model and not present)
                    else "SMOKE_TESTED"
                    if tested
                    else "NOT_TESTED"
                ),
                "models": models,
                "smoke_execution_ids": [str(row.execution_id) for row in smoke],
                "note": (
                    "Smoke applies only to the recorded model and minimal JSON contract; "
                    "full agent schemas and scientific quality remain unverified."
                    if tested
                    else "Configuration/key presence does not verify service or model access."
                ),
            }
        )
    return result


def validate(settings: Settings) -> list[str]:
    errors = []
    for group in settings.route_groups():
        if not group:
            errors.append("Every profile needs an enabled preferred route")
        for route in group:
            if (
                route.provider not in PROVIDER_KEYS
                or not re.fullmatch(r"[A-Za-z0-9_.-]{3,120}", route.model)
                or route.model.startswith(("sk-", "AIza"))
                or route.model == "CONFIGURE_ME"
            ):
                errors.append("Provider/model ID invalid")
            if route.input_cost_per_million is None or route.output_cost_per_million is None:
                errors.append("Both token prices are required")
    if set(settings.role_routes) - set(agents.__all__):
        errors.append("Unknown role override")
    if not settings.research.human_approval_required:
        errors.append("Studio requires explicit human approval")
    if not settings.live_research_budget:
        errors.append("Six-field live budget required")
    if set(settings.search.adapters) - {"crossref", "openalex", "arxiv"}:
        errors.append("Source backend unavailable")
    if settings.search.local_documents:
        errors.append("Use project PDF uploads instead of arbitrary local paths")
    return list(dict.fromkeys(errors))


def save(service: StudioService, settings: Settings) -> dict[str, Any]:
    errors = validate(settings)
    if errors:
        raise StudioError("; ".join(errors))
    service.store.put("settings", "operator", settings.model_dump(mode="json"))
    return view(service)


def preflight(
    service: StudioService, identity: UUID, settings: Settings | None = None
) -> dict[str, Any]:
    from research_council.studio.interactions import agent_class

    project = service.project(identity)
    settings = settings or current(service)
    errors = validate(settings)
    if project.providers:
        for routes in [*settings.models.values(), *settings.role_routes.values()]:
            for route in routes:
                if route.provider not in project.providers:
                    route.enabled = False
    if not settings.search.adapters and not any(
        row["project_id"] == str(identity) and row["status"] == "PARSED"
        for row in service.store.list("document")
    ):
        errors.append("No scholarly source or parsed project PDF")
    for group in settings.route_groups():
        if not group:
            errors.append("Project provider selection leaves a routing profile empty")
        for route in group:
            if not os.environ.get(PROVIDER_KEYS.get(route.provider, ""), "").strip():
                errors.append("Missing credential for " + route.provider)
    for name in agents.__all__:
        role = agent_class(name)
        routes = [
            r
            for r in settings.role_routes.get(name, settings.models[role.task_profile])
            if r.enabled
        ]
        supported = False
        for route in routes:
            try:
                if route.provider == "anthropic":
                    anthropic_schema(role.output_schema.model_json_schema())
                supported = True
            except SchemaCompatibilityError:
                continue
        if not supported:
            errors.append("No compatible route for " + name)
    cap = settings.live_research_budget or LiveResearchBudget()
    return {
        "ready": not errors,
        "errors": list(dict.fromkeys(errors)),
        "warnings": [
            "Configuration and schema checks only; model access and source reachability are not verified."
        ],
        "models": {
            p.value: [r.model_dump(mode="json") for r in rs if r.enabled]
            for p, rs in settings.models.items()
        },
        "providers": sorted({r.provider for group in settings.route_groups() for r in group}),
        "role_routes": {
            role: [r.model_dump(mode="json") for r in routes if r.enabled]
            for role, routes in settings.role_routes.items()
        },
        "anthropic_blocked_roles": [
            {
                "agent": row["agent"],
                "reason": row["reason"],
                "routes": [
                    r.model_dump(mode="json")
                    for r in settings.role_routes.get(
                        row["agent"], settings.models[agent_class(row["agent"]).task_profile]
                    )
                    if r.enabled
                ],
                "explicit_override": row["agent"] in settings.role_routes,
            }
            for row in compatibility()
            if row["anthropic"] == "BLOCKED"
        ],
        "readiness": readiness(service, settings),
        "sources": settings.search.adapters,
        "max_budget": min(project.budget, settings.research.budget_usd, cap.max_total_cost),
        "max_model_calls": min(settings.research.max_model_calls, cap.max_model_calls),
        "caps": cap.model_dump(mode="json"),
        "human_approval_required": settings.research.human_approval_required,
        "novelty_review_each_revision": settings.research.novelty_review_each_revision,
        "paid_model_calls_made": 0,
    }


def cost(service: StudioService, identity: UUID) -> dict[str, Any]:
    snapshot = service.snapshot(identity)
    usage = service.repository.artifacts(identity).get("live_budget_usage", {})
    spent = max(
        sum(row["estimated_cost"] or 0 for row in snapshot["models"]),
        usage.get("estimated_cost", 0),
    )
    reserved = usage.get("reserved_cost", 0)
    budget = snapshot["run"]["budget_usd"]
    return {
        "budget": budget,
        "spent": spent,
        "reserved": reserved,
        "remaining": max(0, budget - spent - reserved),
        "model_calls": usage.get("model_calls", len(snapshot["models"])),
        "search_calls": usage.get("search_calls", len(snapshot["state"]["search_history"])),
        "deep_reads": usage.get(
            "deep_reads", sum(r["agent_id"] == "DeepReader" for r in snapshot["executions"])
        ),
        "novelty_iterations": snapshot["state"]["novelty_iteration"],
        "warnings": [n for n in (50, 75, 90) if budget and (spent + reserved) / budget * 100 >= n],
        "hard_stop": usage.get("exhausted", False)
        or snapshot["run"]["status"] == "BUDGET_EXHAUSTED",
    }
