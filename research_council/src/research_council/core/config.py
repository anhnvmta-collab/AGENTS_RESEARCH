from __future__ import annotations

import hashlib
import json
import os
import re
from collections.abc import Mapping
from datetime import date
from pathlib import Path
from typing import Literal

import yaml
from pydantic import Field, PrivateAttr, model_validator

from research_council.schemas.models import Schema, TaskProfile
from research_council.validation.budget import LiveResearchBudget


class Route(Schema):
    enabled: bool = True
    provider: str = "fake"
    model: str = "offline"
    input_cost_per_million: float | None = Field(default=None, ge=0)
    output_cost_per_million: float | None = Field(default=None, ge=0)
    max_output_tokens: int = Field(default=4096, ge=128, le=32768)
    pricing_verified_on: date | None = None


class ResearchConfig(Schema):
    max_novelty_iterations: int = Field(default=3, ge=1, le=10)
    max_core_papers: int = Field(default=30, ge=1, le=200)
    min_novelty_evidence: int = Field(default=2, ge=1)
    max_queries: int = Field(default=12, ge=1, le=100)
    max_model_calls: int = Field(default=200, ge=1)
    budget_usd: float = Field(default=5, ge=0)
    human_approval_required: bool = False
    novelty_review_each_revision: bool = False


class ConcurrencyConfig(Schema):
    agents: int = Field(default=5, ge=1, le=64)
    searches: int = Field(default=5, ge=1, le=32)
    paper_reads: int = Field(default=4, ge=1, le=32)


class SearchConfig(Schema):
    adapters: list[str] = Field(default_factory=list)
    results_per_query: int = Field(default=10, ge=1, le=100)
    local_documents: list[str] = Field(default_factory=list)
    contact_email: str | None = None
    saturation_patience: int = Field(default=3, ge=1, le=10)
    minimum_new_unique_rate: float = Field(default=0.02, ge=0, le=1)


class TriageWeights(Schema):
    relevance: float = Field(default=0.25, ge=0, le=1)
    venue_quality: float = Field(default=0.15, ge=0, le=1)
    novelty_relevance: float = Field(default=0.15, ge=0, le=1)
    methodological_value: float = Field(default=0.15, ge=0, le=1)
    hardware_relevance: float = Field(default=0.10, ge=0, le=1)
    citation_influence: float = Field(default=0.10, ge=0, le=1)
    freshness: float = Field(default=0.10, ge=0, le=1)

    @model_validator(mode="after")
    def sum_to_one(self) -> TriageWeights:
        if abs(sum(self.model_dump().values()) - 1) > 1e-8:
            raise ValueError("Triage weights must sum to one")
        return self


class Settings(Schema):
    _fingerprint_alias: tuple[str, str] | None = PrivateAttr(default=None)
    research: ResearchConfig = Field(default_factory=ResearchConfig)
    concurrency: ConcurrencyConfig = Field(default_factory=ConcurrencyConfig)
    search: SearchConfig = Field(default_factory=SearchConfig)
    triage: TriageWeights = Field(default_factory=TriageWeights)
    models: dict[TaskProfile, list[Route]] = Field(
        default_factory=lambda: {profile: [Route()] for profile in TaskProfile}
    )
    role_routes: dict[str, list[Route]] = Field(default_factory=dict)
    science_benchmark: Literal["CS_FHSS_DOA_FPGA"] | None = None
    live_research_budget: LiveResearchBudget | None = None
    retries: int = Field(default=2, ge=0, le=5)
    timeout_seconds: float = Field(default=60, gt=0, le=600)
    retry_base_seconds: float = Field(default=0.5, ge=0, le=30)

    @model_validator(mode="after")
    def complete_routes(self) -> Settings:
        for profile in TaskProfile:
            self.models.setdefault(profile, [Route()])
        return self

    def route_groups(self) -> list[list[Route]]:
        return [
            [route for route in routes if route.enabled]
            for routes in [*self.models.values(), *self.role_routes.values()]
        ]

    def fingerprint(self) -> str:
        current = hashlib.sha256(
            json.dumps(self.model_dump(mode="json"), sort_keys=True).encode()
        ).hexdigest()
        if self._fingerprint_alias and current == self._fingerprint_alias[0]:
            return self._fingerprint_alias[1]
        return current

    def pin_compatible_fingerprint(self, expected: str) -> None:
        self._fingerprint_alias = (self.fingerprint(), expected)


def load_settings(
    path: Path | None = None, *, environ: Mapping[str, str] | None = None
) -> Settings:
    if path is None:
        return Settings()
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(raw or {}, dict):
        raise ValueError("Configuration must be a mapping")
    raw = raw or {}
    role_names = {
        name.replace("_", "").lower(): name
        for name in (
            "ResearchDirector",
            "ResearchPlanner",
            "PerspectiveGenerator",
            "QueryPlanner",
            "PaperScout",
            "CitationScout",
            "LocalDocumentScout",
            "PaperTriage",
            "DeepReader",
            "MathDSPAnalyst",
            "HardwareArchitect",
            "GapMiner",
            "NoveltyGenerator",
            "PriorArtHunter",
            "ReviewerTwo",
            "NoveltyJudge",
            "ExperimentDesigner",
            "PaperArchitect",
            "CitationAuditor",
            "FinalSynthesizer",
        )
    }
    role_names.update(
        director="ResearchDirector", planner="ResearchPlanner", reviewer="ReviewerTwo"
    )
    profiles: dict[str, object] = {}
    roles = dict(raw.get("role_routes", {}))
    for name, routes in raw.get("models", {}).items():
        if name in TaskProfile.__members__:
            profiles[name] = routes if isinstance(routes, list) else [routes]
        else:
            canonical = role_names.get(name.replace("_", "").lower())
            if not canonical:
                raise ValueError(f"Unknown routing task or role: {name}")
            roles[canonical] = routes if isinstance(routes, list) else [routes]
    raw["models"], raw["role_routes"] = profiles, roles
    for routes in [*profiles.values(), *roles.values()]:
        if not isinstance(routes, list):
            raise ValueError("Routing entries must be lists")
        for route in routes:
            if not isinstance(route, dict):
                raise ValueError("Route must be a mapping")
            model = route.get("model", "offline")
            if route.get("enabled", True) and isinstance(model, str) and "${" in model:

                def replace_variable(match: re.Match[str]) -> str:
                    name = match.group(1)
                    if not name.endswith(("_MODEL", "_MODEL_ID")):
                        raise ValueError(
                            "Only model-ID environment variables may appear in model configuration"
                        )
                    value = (os.environ if environ is None else environ).get(name)
                    if not value:
                        raise ValueError(f"Missing model-ID environment variable: {name}")
                    return value

                route["model"] = re.sub(r"\$\{([A-Z][A-Z0-9_]*)\}", replace_variable, model)
                if "${" in route["model"]:
                    raise ValueError("Invalid model-ID environment placeholder")
    return Settings.model_validate(raw or {})
