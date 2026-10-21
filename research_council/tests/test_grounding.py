from uuid import uuid4

import pytest

from research_council.agents.contracts import AuditInput, ReadingOutput
from research_council.core.gates import SourceIntegrityGate
from research_council.core.grounding import validate_reading
from research_council.schemas.models import (
    ClaimType,
    Evidence,
    Paper,
    PaperMetadata,
    ResearchClaim,
    VerificationStatus,
)
from research_council.tools.audit import CitationAuditService


def source():
    paper = Paper(
        metadata=PaperMetadata(
            title="Synthetic source",
            authors=["Fixture Author"],
            year=2024,
            url="https://example.invalid/source",
            metadata_source="fixture",
        ),
        provenance="fixture",
        source_kind="fixture",
        source_text="Latency was not measured.",
        page_texts={1: "Latency was not measured."},
    )
    evidence = Evidence(
        paper_id=paper.paper_id,
        evidence_type="limitation",
        source_location="page 1",
        page=1,
        verbatim_excerpt="Latency was not measured.",
        normalized_statement="Latency unknown",
        extraction_agent="DeepReader",
        verification_status=VerificationStatus.VERIFIED,
    )
    claim = ResearchClaim(
        statement="Latency unknown",
        claim_type=ClaimType.AUTHOR_REPORTED,
        source_paper_ids=[paper.paper_id],
        evidence_ids=[evidence.evidence_id],
        verification_status=VerificationStatus.VERIFIED,
    )
    return paper, evidence, claim


def test_reader_cannot_self_verify():
    paper, evidence, claim = source()
    result = validate_reading(paper, ReadingOutput(evidence=[evidence], claims=[claim]))
    assert result.claims[0].verification_status == VerificationStatus.PARTIALLY_VERIFIED
    assert result.evidence[0].verification_status == VerificationStatus.PARTIALLY_VERIFIED
    assert result.evidence[0].provenance == "fixture"


def test_abstract_does_not_acquire_invented_page_numbers():
    paper, evidence, _ = source()
    paper.source_kind = "abstract"
    with pytest.raises(ValueError, match="Abstract-only"):
        validate_reading(paper, ReadingOutput(evidence=[evidence]))


def test_location_and_reference_guards():
    paper, evidence, claim = source()
    with pytest.raises(ValueError, match="location"):
        validate_reading(paper, ReadingOutput(evidence=[evidence.model_copy(update={"page": 2})]))
    with pytest.raises(ValueError, match="supported"):
        validate_reading(
            paper,
            ReadingOutput(
                evidence=[evidence], claims=[claim.model_copy(update={"evidence_ids": [uuid4()]})]
            ),
        )


def test_source_integrity():
    paper, _, _ = source()
    assert SourceIntegrityGate().evaluate([paper]).passed
    assert not SourceIntegrityGate().evaluate([paper, paper]).passed
    assert not SourceIntegrityGate().evaluate([]).passed
    paper.source_text = None
    assert not SourceIntegrityGate().evaluate([paper]).passed


async def test_citation_audit_does_not_verify_fixtures():
    import asyncio

    paper, evidence, claim = source()
    result = await CitationAuditService([], asyncio.Semaphore(2)).audit(
        AuditInput(task="audit", papers=[paper], evidence=[evidence], claims=[claim])
    )
    assert result.audits[0].status == VerificationStatus.UNVERIFIED
    assert "SYNTHETIC" in result.audits[0].notes[0]


async def test_citation_conflict_and_unknown_quartile():
    import asyncio

    paper, evidence, claim = source()
    paper.provenance = "live"
    paper.metadata.doi = "10.1234/test"

    class Resolver:
        name = "resolver"

        async def resolve(self, doi):
            return paper.metadata.model_copy(update={"title": "Different title"})

    result = await CitationAuditService([Resolver()], asyncio.Semaphore(2)).audit(
        AuditInput(task="audit", papers=[paper], evidence=[evidence], claims=[claim])
    )
    assert result.audits[0].status == VerificationStatus.CONTRADICTED
    assert result.audits[0].checks["quartile"] is None
