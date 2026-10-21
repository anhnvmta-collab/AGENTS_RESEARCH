from __future__ import annotations

from uuid import UUID

from research_council.schemas.models import PaperCandidate, Schema
from research_council.validation.coverage import observed_terms


class DiversityShortlist(Schema):
    paper_ids: list[UUID]
    selection_reasons: dict[UUID, list[str]]


def diverse_shortlist(
    candidates: list[PaperCandidate], limit: int, methods: dict[str, list[str]], current_year: int
) -> DiversityShortlist:
    ranked = sorted(candidates, key=lambda item: item.aggregate_score or 0, reverse=True)
    selected: dict[UUID, list[str]] = {}

    def pick(candidate: PaperCandidate | None, reason: str) -> None:
        if candidate and (candidate.paper.paper_id in selected or len(selected) < limit):
            selected.setdefault(candidate.paper.paper_id, []).append(reason)

    pick(ranked[0] if ranked else None, "highest aggregate relevance/quality score")
    older = [
        item
        for item in ranked
        if item.paper.metadata.year and item.paper.metadata.year <= current_year - 10
    ]
    pick(
        older[0] if older else None,
        "seminal/older literature safeguard; age is not a quality judgment",
    )
    implementations = [
        item
        for item in ranked
        if observed_terms(
            f"{item.paper.metadata.title} {item.paper.metadata.abstract or ''}",
            {"implementation": ["FPGA", "RFSoC", "SDR", "GPU", "hardware implementation"]},
        )
    ]
    pick(implementations[0] if implementations else None, "implementation literature safeguard")
    recent = [
        item
        for item in ranked
        if item.paper.metadata.year
        and item.paper.metadata.year >= current_year - 2
        and (item.paper.metadata.citation_count or 0) <= 10
    ]
    pick(recent[0] if recent else None, "recent low/unknown citation safeguard")
    covered: set[str] = set()
    for item in ranked:
        families = observed_terms(
            f"{item.paper.metadata.title} {item.paper.metadata.abstract or ''}", methods
        )
        if families - covered:
            pick(item, "additional observed method-family vocabulary")
        if item.paper.paper_id in selected:
            covered.update(families)
    for item in ranked:
        pick(item, "aggregate-score fill")
    return DiversityShortlist(paper_ids=list(selected), selection_reasons=selected)
