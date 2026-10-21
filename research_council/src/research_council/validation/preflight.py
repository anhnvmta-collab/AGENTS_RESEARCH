"""Configuration-only preflight. No client, repository or network runtime is created."""

from __future__ import annotations

import os
import re
from collections.abc import Mapping
from datetime import date
from pathlib import Path

import yaml
from pydantic import Field, ValidationError

from research_council.core.config import Route, Settings, load_settings
from research_council.schemas.models import Schema, TaskProfile

PROVIDER_KEYS = {
    "openai": "OPENAI_API_KEY",
    "anthropic": "ANTHROPIC_API_KEY",
    "google": "GOOGLE_API_KEY",
}


class PreflightReport(Schema):
    ready: bool = False
    mode: str = "CONFIGURATION_ONLY"
    errors: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    providers: list[dict[str, object]] = Field(default_factory=list)
    routing: list[dict[str, object]] = Field(default_factory=list)
    sources: list[dict[str, object]] = Field(default_factory=list)
    budget: dict[str, object] = Field(default_factory=dict)
    paid_model_calls_made: int = 0
    live_benchmark_executed: bool = False
    scientific_readiness_level: str = "SRL-0"
    limitations: list[str] = Field(
        default_factory=lambda: [
            "No provider authentication, model access, structured-output compatibility or service reachability was tested.",
            "Configuration readiness is not scientific validation or literature coverage.",
            "Token-price estimates are distinct from actual billing and source-service fees.",
        ]
    )


def effective_routes(settings: Settings, role: str, profile: TaskProfile) -> list[Route]:
    return [
        route for route in settings.role_routes.get(role, settings.models[profile]) if route.enabled
    ]


def provider_preflight(
    config: Path, *, environ: Mapping[str, str] | None = None, today: date | None = None
) -> PreflightReport:
    env = os.environ if environ is None else environ
    current = today or date.today()
    result = PreflightReport()
    try:
        if config.stat().st_size > 2_000_000:
            raise ValueError("Oversized configuration")
        raw = yaml.safe_load(config.read_text(encoding="utf-8"))
        settings = load_settings(config, environ=env)
    except ValidationError as exc:
        # Never serialize Pydantic input values, YAML fragments or exception messages.
        budget_error = any(
            error["loc"] and error["loc"][0] in {"research", "live_research_budget"}
            for error in exc.errors()
        )
        result.errors.append(
            "BUDGET_OR_RESEARCH_CONFIGURATION_INVALID"
            if budget_error
            else "CONFIGURATION_SCHEMA_INVALID"
        )
        return result
    except (OSError, ValueError, TypeError, AttributeError, yaml.YAMLError):
        result.errors.append(
            "CONFIGURATION_UNREADABLE_OR_INVALID; check syntax and model-ID environment variables"
        )
        return result
    if not isinstance(raw, dict) or not isinstance(raw.get("models"), dict):
        result.errors.append("EXPLICIT_ROUTING_PROFILES_REQUIRED")
        return result
    for profile in TaskProfile:
        if profile.value not in raw["models"]:
            result.errors.append(f"MISSING_ROUTE: {profile.value}")
    groups = [
        (profile.value, settings.models[profile])
        for profile in TaskProfile
        if profile.value in raw["models"]
    ]
    groups.extend(
        (
            name
            if name in {"NoveltyJudge", "ReviewerTwo", "NoveltyGenerator"}
            else "ROLE_OVERRIDE",
            routes,
        )
        for name, routes in settings.role_routes.items()
    )
    enabled = {route.provider for routes in settings.route_groups() for route in routes}
    for provider, key in PROVIDER_KEYS.items():
        active = provider in enabled
        present = bool(env.get(key, "").strip()) if active else False
        result.providers.append(
            {
                "provider": provider,
                "enabled": active,
                "required_environment_variable": key,
                "key_present": present,
                "service_status": "NOT_CONTACTED",
            }
        )
        if active and not present:
            result.errors.append(f"MISSING_KEY: {key}")
    for scope, routes in groups:
        active_routes = [route for route in routes if route.enabled]
        result.routing.append(
            {
                "scope": scope,
                "enabled_routes": len(active_routes),
                "disabled_routes": len(routes) - len(active_routes),
                "fallback_routes": max(0, len(active_routes) - 1),
            }
        )
        if not active_routes:
            result.errors.append(f"NO_ENABLED_ROUTE: {scope}")
        if len(active_routes) == 1:
            result.warnings.append(f"NO_FALLBACK_ROUTE: {scope}; a single route is allowed")
        for route in active_routes:
            if route.provider not in PROVIDER_KEYS:
                result.errors.append(f"UNSUPPORTED_LIVE_PROVIDER: {scope}")
            if (
                not route.model.strip()
                or "CONFIGURE_ME" in route.model.upper()
                or "${" in route.model
                or route.model == "offline"
            ):
                result.errors.append(f"MODEL_ID_REQUIRED: {scope}")
            if route.provider == "google" and not re.fullmatch(r"[a-zA-Z0-9_.-]+", route.model):
                result.errors.append(f"GEMINI_MODEL_ID_MUST_BE_SINGLE_PATH_SEGMENT: {scope}")
            if route.input_cost_per_million is None or route.output_cost_per_million is None:
                result.errors.append(f"MISSING_PRICE: {scope}; cost reservation unavailable")
            elif route.input_cost_per_million == 0 or route.output_cost_per_million == 0:
                result.warnings.append(f"ZERO_PRICE_REQUIRES_OPERATOR_REVIEW: {scope}")
            if route.pricing_verified_on is None:
                result.warnings.append(f"PRICE_REVIEW_DATE_MISSING: {scope}")
            elif not 0 <= (current - route.pricing_verified_on).days <= 30:
                result.warnings.append(
                    f"PRICE_MAY_BE_STALE_OR_FUTURE_DATED: {scope}; verify current provider pricing"
                )
    generator = effective_routes(settings, "NoveltyGenerator", TaskProfile.NOVELTY_GENERATION)
    reviewer = effective_routes(settings, "ReviewerTwo", TaskProfile.ADVERSARIAL_REVIEW)
    judge = effective_routes(settings, "NoveltyJudge", TaskProfile.ADVERSARIAL_REVIEW)
    if generator and reviewer:
        distinct = [route for route in reviewer if route.provider != generator[0].provider]
        preferred_reviewer = (distinct or reviewer)[0].provider
        if not distinct:
            result.warnings.append(
                "SAME_PROVIDER_REVIEW_FALLBACK; runtime records SAME_PROVIDER_FALLBACK explicitly"
            )
        if not judge or judge[0].provider in {generator[0].provider, preferred_reviewer}:
            result.warnings.append(
                "THIRD_INDEPENDENT_JUDGE_NOT_PREFERRED; explicit role override is supported"
            )
    if settings.science_benchmark != "CS_FHSS_DOA_FPGA":
        result.errors.append("SCIENTIFIC_BENCHMARK_CONFIGURATION_REQUIRED")
    if not settings.research.human_approval_required:
        result.errors.append("FIRST_RUN_REQUIRES_HUMAN_APPROVAL")
    required_budget = {
        "max_total_cost",
        "max_model_calls",
        "max_search_calls",
        "max_core_papers",
        "max_deep_reads",
        "max_novelty_iterations",
    }
    explicit_budget = raw.get("live_research_budget")
    if (
        not isinstance(explicit_budget, dict)
        or not required_budget.issubset(explicit_budget)
        or not settings.live_research_budget
    ):
        result.errors.append("EXPLICIT_SIX_FIELD_LIVE_BUDGET_REQUIRED")
    else:
        result.budget = settings.live_research_budget.model_dump()
        result.budget["max_total_cost"] = min(
            settings.research.budget_usd, settings.live_research_budget.max_total_cost
        )
        result.budget["max_model_calls"] = min(
            settings.research.max_model_calls, settings.live_research_budget.max_model_calls
        )
        result.budget["max_core_papers"] = min(
            settings.research.max_core_papers, settings.live_research_budget.max_core_papers
        )
        result.budget["max_novelty_iterations"] = min(
            settings.research.max_novelty_iterations,
            settings.live_research_budget.max_novelty_iterations,
        )
        if any(not value for value in result.budget.values()):
            result.errors.append("ZERO_LIVE_BUDGET; no first scientific run can complete")
    if not settings.search.adapters and not settings.search.local_documents:
        result.errors.append("NO_SCHOLARLY_SOURCE_CONFIGURED")
    for name in settings.search.adapters:
        known = name in {"crossref", "openalex", "arxiv", "ieee"}
        result.sources.append(
            {
                "adapter": name if known else "unsupported",
                "status": "BACKEND_NOT_CONFIGURED" if name == "ieee" else "CONFIGURED_NOT_TESTED",
                "scientifically_validated": False,
            }
        )
        if not known or name == "ieee":
            result.errors.append(
                "IEEE_AUTHENTICATED_BACKEND_NOT_WIRED"
                if name == "ieee"
                else "UNSUPPORTED_SCHOLARLY_SOURCE"
            )
        if name == "openalex" and not env.get("OPENALEX_API_KEY", "").strip():
            result.warnings.append(
                "OPENALEX_API_KEY_RECOMMENDED_FOR_RESEARCH_SCALE; unauthenticated limits are not coverage"
            )
    result.errors = list(dict.fromkeys(result.errors))
    result.warnings = list(dict.fromkeys(result.warnings))
    result.ready = not result.errors
    return result
