from __future__ import annotations

from typing import Any, Literal
from uuid import UUID, uuid4

from pydantic import Field, field_validator

from research_council.schemas.models import Mode, Schema, utcnow


class StudioProject(Schema):
    id: UUID = Field(default_factory=uuid4)
    title: str = Field(min_length=3, max_length=200)
    topic: str = Field(min_length=3, max_length=4000)
    objective: str = Field(default="", max_length=4000)
    questions: list[str] = Field(default_factory=list, max_length=30)
    domain: str = Field(default="", max_length=200)
    keywords: list[str] = Field(default_factory=list, max_length=100)
    constraints: list[str] = Field(default_factory=list, max_length=100)
    hardware_constraints: str = Field(default="", max_length=4000)
    target_journal: str = Field(default="", max_length=300)
    publication_type: str = Field(default="Research article", max_length=200)
    date_range: str = Field(default="", max_length=100)
    max_papers: int = Field(default=12, ge=1, le=200)
    mode: Mode = Mode.NOVELTY
    budget: float = Field(default=5, ge=0, le=1000)
    providers: list[Literal["openai", "anthropic", "google"]] = Field(default_factory=list)
    notes: str = Field(default="", max_length=10000)
    practice: bool = True
    created_at: str = Field(default_factory=lambda: utcnow().isoformat())


class StartRequest(Schema):
    confirmation: str = ""


class Decision(Schema):
    action: Literal["approve", "reject", "revise"]
    reviewer: str = Field(min_length=2, max_length=100)
    comment: str = Field(default="", max_length=4000)

    @field_validator("reviewer")
    @classmethod
    def named_reviewer(cls, value: str) -> str:
        if len(value.strip()) < 2:
            raise ValueError("A reviewer name is required")
        return value.strip()


class Interaction(Schema):
    run_id: UUID
    task: str = Field(min_length=3, max_length=4000)
    input: dict[str, Any] | None = None


class Revision(Schema):
    kind: Literal["experiment", "paper"]
    target: str = Field(min_length=1, max_length=200)
    content: str = Field(max_length=30000)
    reviewer: str = Field(min_length=2, max_length=100)
    status: Literal["DRAFT", "RESEARCHER_APPROVED"] = "DRAFT"
