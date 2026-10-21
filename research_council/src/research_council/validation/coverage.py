from __future__ import annotations

import re
from pathlib import Path

import yaml
from pydantic import Field, field_validator, model_validator

from research_council.repositories.store import normalized_title
from research_council.schemas.models import (
    CitationObservation,
    Paper,
    PaperMetadata,
    Schema,
    normalize_doi,
)
from research_council.validation.benchmark import benchmark_directory


class SeedPaper(Schema):
    identifier: str
    metadata: PaperMetadata
    doi_aliases: list[str] = Field(default_factory=list)
    identity_sources: list[str] = Field(min_length=1)
    verified_on: str
    verification_basis: str
    method_families: list[str] = Field(default_factory=list)
    note: str = "Nonexhaustive coverage seed; not a benchmark finding."

    @field_validator("doi_aliases")
    @classmethod
    def normalized_aliases(cls, values: list[str]) -> list[str]:
        return [doi for value in values if (doi := normalize_doi(value))]

    @model_validator(mode="after")
    def real_identity(self) -> SeedPaper:
        if (
            not self.metadata.authors
            or not self.metadata.year
            or not (self.metadata.doi or self.metadata.url)
        ):
            raise ValueError(
                "Seed requires verifiable identity; invented partial references are forbidden"
            )
        if not all(
            url.startswith("https://") and "example.invalid" not in url
            for url in self.identity_sources
        ):
            raise ValueError("Seed requires actual primary-source provenance URLs")
        return self


class MeasuredRatio(Schema):
    numerator: int = Field(ge=0)
    denominator: int = Field(ge=0)

    @property
    def value(self) -> float | None:
        return self.numerator / self.denominator if self.denominator else None


class CoverageReport(Schema):
    measurement_status: str = "OBSERVED_WITHIN_SEARCHED_SOURCES"
    seed_paper_recall: MeasuredRatio
    method_family_recall: MeasuredRatio
    concept_coverage: MeasuredRatio
    citation_chain_recovery: MeasuredRatio
    matched_seeds: list[str]
    observed_method_families: list[str]
    observed_concepts: list[str]
    limitation: str = "Nonexhaustive seed set; lexical family/concept proxies within observed metadata/evidence, not universal completeness."


def load_seeds(directory: Path | None = None) -> list[SeedPaper]:
    raw = yaml.safe_load(
        ((directory or benchmark_directory()) / "seed_papers.yaml").read_text(encoding="utf-8")
    )
    return [SeedPaper.model_validate(item) for item in raw.get("papers", [])]


def verified_citation_edges(observations: list[CitationObservation]) -> set[tuple[str, str]]:
    return {
        (item.seed_identifier, item.target_identifier)
        if item.direction == "backward"
        else (item.target_identifier, item.seed_identifier)
        for item in observations
        if item.relation_verified and item.direction in {"backward", "forward"}
    }


def vocabulary(filename: str, key: str, directory: Path | None = None) -> dict[str, list[str]]:
    return dict(
        yaml.safe_load(
            ((directory or benchmark_directory()) / filename).read_text(encoding="utf-8")
        )[key]
    )


def observed_terms(text: str, definitions: dict[str, list[str]]) -> set[str]:
    return {
        name
        for name, aliases in definitions.items()
        if any(
            re.search(r"(?<!\w)" + re.escape(alias) + r"(?!\w)", text, re.I) for alias in aliases
        )
    }


def seed_matches(seed: SeedPaper, paper: Paper) -> bool:
    if paper.provenance == "fixture":
        return False
    if paper.metadata.doi and paper.metadata.doi in {seed.metadata.doi, *seed.doi_aliases}:
        return True
    return bool(
        normalized_title(seed.metadata.title) == normalized_title(paper.metadata.title)
        and set(map(normalized_title, seed.metadata.authors))
        & set(map(normalized_title, paper.metadata.authors))
        and seed.metadata.year == paper.metadata.year
    )


def coverage_report(
    papers: list[Paper],
    seeds: list[SeedPaper],
    methods: dict[str, list[str]],
    concepts: dict[str, list[str]],
    *,
    evidence_text: str = "",
    expected_citation_edges: set[tuple[str, str]] | None = None,
    observed_citation_edges: set[tuple[str, str]] | None = None,
) -> CoverageReport:
    real = [paper for paper in papers if paper.provenance != "fixture"]
    corpus = (
        " ".join(f"{paper.metadata.title} {paper.metadata.abstract or ''}" for paper in real)
        + " "
        + evidence_text
    )
    found_methods, found_concepts = (
        observed_terms(corpus, methods),
        observed_terms(corpus, concepts),
    )
    matched = [
        seed.identifier for seed in seeds if any(seed_matches(seed, paper) for paper in real)
    ]
    expected = expected_citation_edges or set()
    return CoverageReport(
        seed_paper_recall=MeasuredRatio(numerator=len(matched), denominator=len(seeds)),
        method_family_recall=MeasuredRatio(numerator=len(found_methods), denominator=len(methods)),
        concept_coverage=MeasuredRatio(numerator=len(found_concepts), denominator=len(concepts)),
        citation_chain_recovery=MeasuredRatio(
            numerator=len(expected & (observed_citation_edges or set())), denominator=len(expected)
        ),
        matched_seeds=matched,
        observed_method_families=sorted(found_methods),
        observed_concepts=sorted(found_concepts),
    )
