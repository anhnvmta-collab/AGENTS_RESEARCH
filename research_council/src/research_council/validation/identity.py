from __future__ import annotations

import asyncio
from uuid import UUID, uuid4

from pydantic import Field

from research_council.repositories.store import normalized_title
from research_council.schemas.models import (
    Paper,
    PaperCandidate,
    PaperMetadata,
    Schema,
    VerificationStatus,
)
from research_council.tools.ports import MetadataProvider


class PaperIdentityAudit(Schema):
    audit_id: UUID = Field(default_factory=uuid4)
    paper_id: UUID
    identity_sources: list[PaperMetadata] = Field(default_factory=list)
    conflicts: list[str] = Field(default_factory=list)
    failures: list[str] = Field(default_factory=list)
    confidence: float = Field(default=0, ge=0, le=1)
    status: VerificationStatus = VerificationStatus.UNVERIFIED
    scope: str = "Metadata identity only; not scientific entailment or retraction verification."


class IdentityInput(Schema):
    papers: list[Paper]
    observations: dict[str, list[PaperMetadata]] = Field(default_factory=dict)


class IdentityOutput(Schema):
    audits: list[PaperIdentityAudit]


def identity_keys(metadata: PaperMetadata) -> list[str]:
    return ["title:" + normalized_title(metadata.title)] + (
        ["doi:" + metadata.doi] if metadata.doi else []
    )


def retain_identity_observations(
    observations: dict[str, list[PaperMetadata]], candidates: list[PaperCandidate]
) -> None:
    for candidate in candidates:
        metadata = candidate.paper.metadata
        for key in identity_keys(metadata):
            sources = observations.setdefault(key, [])
            fingerprint = metadata.model_dump(exclude={"retrieved_at"})
            if not any(
                item.model_dump(exclude={"retrieved_at"}) == fingerprint for item in sources
            ):
                sources.append(metadata.model_copy(deep=True))


def audit_identity(paper: Paper, sources: list[PaperMetadata]) -> PaperIdentityAudit:
    result = PaperIdentityAudit(paper_id=paper.paper_id, identity_sources=sources)
    if paper.provenance == "fixture":
        result.failures.append("Fixture identity cannot verify a real publication")
        return result
    original = paper.metadata
    for source in sources:
        same_title = normalized_title(original.title) == normalized_title(source.title)
        if original.doi and source.doi and original.doi == source.doi and not same_title:
            result.conflicts.append("SAME_DOI_DIFFERENT_TITLE")
        elif same_title and original.doi and source.doi and original.doi != source.doi:
            result.conflicts.append("SAME_TITLE_DIFFERENT_DOI")
        elif not same_title:
            result.conflicts.append("TITLE_MISMATCH")
        if original.year and source.year and original.year != source.year:
            result.conflicts.append("YEAR_MISMATCH")
        if (
            original.authors
            and source.authors
            and {normalized_title(author) for author in original.authors}
            != {normalized_title(author) for author in source.authors}
        ):
            result.conflicts.append("AUTHOR_MISMATCH")
        if (
            original.venue
            and source.venue
            and normalized_title(original.venue) != normalized_title(source.venue)
        ):
            result.conflicts.append("VENUE_MISMATCH")
    result.conflicts = list(dict.fromkeys(result.conflicts))
    if result.conflicts:
        result.status = VerificationStatus.CONTRADICTED
        return result
    # Confidence is a descriptor after deterministic checks, never an override.
    trusted = any(
        item.metadata_verified and item.metadata_source in {"crossref", "openalex", "arxiv"}
        for item in sources
    )
    complete = bool(
        original.title and original.authors and original.year and (original.doi or original.url)
    )
    if sources and trusted and complete:
        result.status, result.confidence = VerificationStatus.VERIFIED, 1
    return result


class IdentityAuditService:
    def __init__(self, adapters: list[MetadataProvider], semaphore: asyncio.Semaphore) -> None:
        self.adapters, self.semaphore = adapters, semaphore

    async def audit(self, value: IdentityInput) -> IdentityOutput:
        async def one(paper: Paper) -> PaperIdentityAudit:
            observations = [
                item
                for key in identity_keys(paper.metadata)
                for item in value.observations.get(key, [])
            ]
            failures = []
            if paper.provenance != "fixture" and paper.metadata.doi:
                async with self.semaphore:
                    for adapter in self.adapters:
                        try:
                            resolved = await adapter.resolve(paper.metadata.doi)
                            if resolved:
                                observations.append(resolved)
                        except Exception as exc:
                            failures.append(f"{adapter.name}:{type(exc).__name__}")
            result = audit_identity(paper, observations)
            result.failures.extend(failures)
            return result

        return IdentityOutput(
            audits=list(await asyncio.gather(*(one(paper) for paper in value.papers)))
        )
