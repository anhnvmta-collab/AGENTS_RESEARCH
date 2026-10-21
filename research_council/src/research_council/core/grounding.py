from __future__ import annotations

from research_council.agents.contracts import ReadingOutput
from research_council.schemas.models import (
    ClaimType,
    Evidence,
    Paper,
    ResearchClaim,
    VerificationStatus,
)


def grounded_excerpt(paper: Paper, evidence: Evidence) -> bool:
    if evidence.paper_id != paper.paper_id:
        return False
    source = paper.page_texts.get(evidence.page, "") if evidence.page else paper.source_text or ""
    return bool(source) and " ".join(evidence.verbatim_excerpt.split()) in " ".join(source.split())


def validate_reading(paper: Paper, output: ReadingOutput) -> ReadingOutput:
    valid = output.model_copy(deep=True)
    evidence_ids = {item.evidence_id for item in valid.evidence}
    if len(evidence_ids) != len(valid.evidence):
        raise ValueError("Duplicate evidence identifiers")
    for item in valid.evidence:
        if not grounded_excerpt(paper, item):
            raise ValueError("Ungrounded extraction or invalid source location")
        if paper.source_kind == "abstract":
            if any((item.page, item.section, item.table, item.figure)):
                raise ValueError(
                    "Abstract-only evidence cannot assert unavailable full-text locations"
                )
            item.source_location = "abstract"
        # A model cannot assert its own semantic verification.
        item.verification_status = VerificationStatus.PARTIALLY_VERIFIED
        item.provenance = paper.provenance
        item.extraction_agent = "DeepReader"
    for extraction in valid.extractions:
        if not set(extraction.evidence_ids).issubset(evidence_ids):
            raise ValueError("Extraction references missing evidence")
    for claim in valid.claims:
        if (
            set(claim.source_paper_ids) != {paper.paper_id}
            or not claim.evidence_ids
            or not set(claim.evidence_ids).issubset(evidence_ids)
        ):
            raise ValueError("Claim is not supported by the extracted source evidence")
        if not set(claim.contradicting_evidence_ids).issubset(evidence_ids):
            raise ValueError("Unknown contradicting evidence")
        claim.verification_status = (
            VerificationStatus.UNVERIFIED
            if claim.claim_type == ClaimType.HYPOTHESIS
            else VerificationStatus.PARTIALLY_VERIFIED
        )
        claim.reviewer_status = "SEMANTIC_REVIEW_REQUIRED"
    return valid


def validate_analysis_claims(
    claims: list[ResearchClaim], evidence: list[Evidence]
) -> list[ResearchClaim]:
    available = {item.evidence_id: item for item in evidence}
    output: list[ResearchClaim] = []
    for original in claims:
        claim = original.model_copy(deep=True)
        if not claim.evidence_ids or not set(claim.evidence_ids).issubset(available):
            raise ValueError("Analysis claim lacks grounded premises")
        if not {available[identity].paper_id for identity in claim.evidence_ids}.issubset(
            set(claim.source_paper_ids)
        ):
            raise ValueError("Analysis claim paper mismatch")
        if not set(claim.contradicting_evidence_ids).issubset(available):
            raise ValueError("Unknown contradicting evidence")
        claim.verification_status = (
            VerificationStatus.UNVERIFIED
            if claim.claim_type == ClaimType.HYPOTHESIS
            else VerificationStatus.PARTIALLY_VERIFIED
        )
        claim.reviewer_status = "SEMANTIC_REVIEW_REQUIRED"
        output.append(claim)
    return output
