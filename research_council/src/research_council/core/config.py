from __future__ import annotations

import hashlib
import json
from pathlib import Path

import yaml
from pydantic import Field

from research_council.schemas.models import Schema, TaskProfile


class Route(Schema):
    provider: str = "fake"
    model: str = "offline"
    input_cost_per_million: float | None = Field(default=None, ge=0)
    output_cost_per_million: float | None = Field(default=None, ge=0)
    max_output_tokens: int = Field(default=4096, ge=128, le=32768)


class ResearchConfig(Schema):
    max_novelty_iterations: int = Field(default=3, ge=1, le=10)
    max_core_papers: int = Field(default=30, ge=1, le=200)
    min_novelty_evidence: int = Field(default=2, ge=1)
    max_queries: int = Field(default=12, ge=1, le=100)
    max_model_calls: int = Field(default=200, ge=1)
    budget_usd: float = Field(default=5, ge=0)
    human_approval_required: bool = False


class ConcurrencyConfig(Schema):
    agents: int = Field(default=5, ge=1, le=64)
    searches: int = Field(default=5, ge=1, le=32)
    paper_reads: int = Field(default=4, ge=1, le=32)


class SearchConfig(Schema):
    adapters: list[str] = Field(default_factory=list)
    results_per_query: int = Field(default=10, ge=1, le=100)
    local_documents: list[str] = Field(default_factory=list)
    contact_email: str | None = None


class Settings(Schema):
    research: ResearchConfig = Field(default_factory=ResearchConfig)
    concurrency: ConcurrencyConfig = Field(default_factory=ConcurrencyConfig)
    search: SearchConfig = Field(default_factory=SearchConfig)
    models: dict[TaskProfile, list[Route]] = Field(
        default_factory=lambda: {profile: [Route()] for profile in TaskProfile}
    )
    retries: int = Field(default=2, ge=0, le=5)
    timeout_seconds: float = Field(default=60, gt=0, le=600)
    retry_base_seconds: float = Field(default=0.5, ge=0, le=30)

    def fingerprint(self) -> str:
        return hashlib.sha256(
            json.dumps(self.model_dump(mode="json"), sort_keys=True).encode()
        ).hexdigest()


def load_settings(path: Path | None = None) -> Settings:
    if path is None:
        return Settings()
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    return Settings.model_validate(raw or {})
