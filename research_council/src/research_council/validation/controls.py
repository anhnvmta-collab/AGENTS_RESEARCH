from __future__ import annotations

from typing import Literal

from pydantic import Field

from research_council.repositories.store import normalized_title
from research_council.schemas.models import NoveltyCandidate, Paper, PriorArtReport, Schema


class ReferenceSearchResult(Schema):
    status: Literal["NOT_FOUND_IN_SEARCHED_SOURCES", "PARTIALLY_VERIFIED"]
    matches: list[Paper] = Field(default_factory=list)
    note: str = "Exact title match within returned scholarly metadata only; absence is not universal nonexistence or scientific verification."


def verify_reference_title(title: str, retrieved: list[Paper]) -> ReferenceSearchResult:
    matches = [
        paper
        for paper in retrieved
        if paper.provenance != "fixture"
        and normalized_title(paper.metadata.title) == normalized_title(title)
        and paper.metadata.metadata_verified
        and (paper.metadata.doi or paper.metadata.url)
    ]
    return ReferenceSearchResult(
        status="PARTIALLY_VERIFIED" if matches else "NOT_FOUND_IN_SEARCHED_SOURCES", matches=matches
    )


def novelty_coverage_status(prior: PriorArtReport) -> str:
    if (
        not prior.complete
        or prior.search_failures
        or not prior.search_attempts
        or not prior.matches
    ):
        return "INSUFFICIENT_SEARCH_COVERAGE"
    if any(match.invalidates or match.severity == "HIGH" for match in prior.matches):
        return "KNOWN_PRIOR_ART_OVERLAP"
    return "CLOSEST_PRIOR_ART_REQUIRES_REVIEW"


def unchanged_method_control(candidate: NoveltyCandidate) -> bool:
    return (
        candidate.is_negative_control
        and candidate.mathematical_change.upper() == "NONE"
        and candidate.implementation_change.upper() == "NONE"
    )
