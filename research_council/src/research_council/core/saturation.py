from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import Field

from research_council.schemas.models import Schema, utcnow


class SearchSaturationSignal(Schema):
    round: int = Field(ge=1)
    status: str
    new_unique_papers: int = Field(ge=0)
    new_unique_rate: float = Field(ge=0, le=1)
    new_evidence: int = Field(ge=0)
    new_method_families: int | None = Field(default=None, ge=0)
    new_citation_clusters: int | None = Field(default=None, ge=0)
    low_information_rounds: int = Field(ge=0)
    reasons: list[str]
    created_at: datetime = Field(default_factory=utcnow)


class SearchSaturationDetector:
    def __init__(self, patience: int = 3, minimum_new_rate: float = 0.02) -> None:
        if patience < 1:
            raise ValueError("Saturation patience must be positive")
        self.patience, self.minimum_new_rate = patience, minimum_new_rate

    def observe(
        self,
        previous: set[UUID],
        current: set[UUID],
        previous_evidence: int,
        current_evidence: int,
        history: list[SearchSaturationSignal],
        *,
        search_complete: bool,
        new_method_families: int | None = None,
        new_citation_clusters: int | None = None,
    ) -> SearchSaturationSignal:
        added = len(current - previous)
        rate = added / max(1, len(current))
        new_evidence = max(0, current_evidence - previous_evidence)
        low = (
            search_complete
            and rate <= self.minimum_new_rate
            and new_evidence == 0
            and new_method_families in (None, 0)
            and new_citation_clusters in (None, 0)
        )
        low_rounds = (history[-1].low_information_rounds if history else 0) + 1 if low else 0
        status = (
            "SEARCH_SATURATED"
            if low_rounds >= self.patience
            else "CONTINUE"
            if search_complete
            else "INSUFFICIENT_SEARCH"
        )
        reasons = [
            f"New unique papers: {added}; new-paper rate: {rate:.3f}; new evidence: {new_evidence}."
        ]
        if status == "SEARCH_SATURATED":
            reasons.append(
                f"{low_rounds} completed rounds produced negligible new information; this is not proof of universal coverage."
            )
        if not search_complete:
            reasons.append("Failed/missing adapters cannot establish search saturation.")
        return SearchSaturationSignal(
            round=len(history) + 1,
            status=status,
            new_unique_papers=added,
            new_unique_rate=rate,
            new_evidence=new_evidence,
            new_method_families=new_method_families,
            new_citation_clusters=new_citation_clusters,
            low_information_rounds=low_rounds,
            reasons=reasons,
        )
