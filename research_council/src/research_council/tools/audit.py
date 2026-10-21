from __future__ import annotations

import asyncio

from research_council.agents.contracts import AuditInput, AuditsOutput
from research_council.core.grounding import grounded_excerpt
from research_council.core.integrity import unresolved_conflict
from research_council.repositories.store import normalized_title
from research_council.schemas.models import CitationAudit, Paper, PaperMetadata, VerificationStatus
from research_council.tools.search import MetadataAdapter


class CitationAuditService:
    def __init__(self, adapters: list[MetadataAdapter], semaphore: asyncio.Semaphore) -> None:
        self.adapters, self.semaphore = adapters, semaphore

    async def audit(self, value: AuditInput) -> AuditsOutput:
        async def one(paper: Paper) -> CitationAudit:
            async with self.semaphore:
                return await self._audit_paper(paper, value)

        return AuditsOutput(
            audits=list(await asyncio.gather(*(one(paper) for paper in value.papers)))
        )

    async def _audit_paper(self, paper: Paper, value: AuditInput) -> CitationAudit:
        relevant_claims = [
            claim for claim in value.claims if paper.paper_id in claim.source_paper_ids
        ]
        evidence = [item for item in value.evidence if item.paper_id == paper.paper_id]
        audit = CitationAudit(
            paper_id=paper.paper_id, claim_ids=[claim.claim_id for claim in relevant_claims]
        )
        if paper.provenance == "fixture":
            audit.notes.append("SYNTHETIC FIXTURE: not a real publication or scientific finding.")
            audit.checks = {"existence": False, "scientific_entailment": False}
            return audit
        resolved: PaperMetadata | None = None
        if paper.metadata.doi:
            for adapter in self.adapters:
                try:
                    resolved = await adapter.resolve(paper.metadata.doi)
                except Exception as exc:
                    audit.notes.append(
                        f"Metadata resolution failed: {adapter.name}:{type(exc).__name__}"
                    )
                if resolved:
                    break
        original = paper.metadata
        checks: dict[str, bool | None] = {
            "existence": bool(resolved),
            "title": None,
            "authors": None,
            "year": None,
            "venue": None,
            "doi": None,
            "quartile": None,
            "not_retracted": None,
            "source_location": all(grounded_excerpt(paper, item) for item in evidence)
            if evidence
            else None,
            "scientific_entailment": None,
        }
        evidence_map = {item.evidence_id: item for item in value.evidence}
        support_present = all(
            bool(claim.evidence_ids) and set(claim.evidence_ids).issubset(evidence_map)
            for claim in relevant_claims
        )
        checks["claim_support_present"] = support_present
        checks["claim_evidence_consistent"] = (
            all(
                all(
                    evidence_map[identity].paper_id in claim.source_paper_ids
                    for identity in claim.evidence_ids
                )
                and not unresolved_conflict(claim, value.conflicts)
                for claim in relevant_claims
            )
            if support_present
            else None
        )
        if resolved:
            checks.update(
                title=normalized_title(original.title) == normalized_title(resolved.title),
                authors={normalized_title(name) for name in original.authors}
                == {normalized_title(name) for name in resolved.authors}
                if original.authors and resolved.authors
                else None,
                year=original.year == resolved.year if original.year and resolved.year else None,
                doi=original.doi == resolved.doi,
                venue=normalized_title(original.venue) == normalized_title(resolved.venue)
                if original.venue and resolved.venue
                else None,
                quartile=original.quartile == resolved.quartile
                if original.quartile and resolved.quartile_source
                else None,
                not_retracted=not resolved.retracted if resolved.retracted is not None else None,
            )
        audit.checks = checks
        contradictions = any(
            checks[key] is False
            for key in (
                "title",
                "authors",
                "year",
                "venue",
                "quartile",
                "doi",
                "source_location",
                "not_retracted",
                "claim_evidence_consistent",
            )
        )
        if contradictions:
            audit.status = VerificationStatus.CONTRADICTED
            audit.notes.append("Identity, location or retraction conflict requires resolution.")
        elif resolved and support_present:
            audit.status = VerificationStatus.PARTIALLY_VERIFIED
        else:
            audit.notes.append("Independent metadata resolution unavailable.")
        audit.notes.append(
            "Quotation grounding is not semantic entailment; human scientific review is required."
        )
        if checks["quartile"] is None:
            audit.notes.append("Journal quartile is unknown.")
        if checks["not_retracted"] is None:
            audit.notes.append("Retraction status is unknown.")
        return audit
