from __future__ import annotations

import random
from uuid import UUID

from pydantic import Field

from research_council.core.grounding import grounded_excerpt
from research_council.core.hardware import numeric_quote_support
from research_council.schemas.models import (
    Evidence,
    EvidenceConflict,
    HardwareAssessment,
    Paper,
    ResearchClaim,
    Schema,
)
from research_council.validation.coverage import MeasuredRatio


class EvidenceJudgment(Schema):
    evidence_id: UUID
    reviewer: str = Field(min_length=2)
    human_location_correct: bool | None = None
    human_entailment_correct: bool | None = None
    human_interpretation_correct: bool | None = None
    notes: str = ""


class ContradictionLabel(Schema):
    claim_id: UUID
    reviewer: str = Field(min_length=2)
    contradiction_present: bool


class ScientificQualityReport(Schema):
    metrics: dict[str, MeasuredRatio]
    definitions: dict[str, str]
    limitations: list[str]


def scientific_quality(
    papers: list[Paper],
    evidence: list[Evidence],
    claims: list[ResearchClaim],
    conflicts: list[EvidenceConflict],
    reviews: list[EvidenceJudgment] | None = None,
    contradiction_labels: list[ContradictionLabel] | None = None,
    claim_support_labels: dict[UUID, bool] | None = None,
) -> ScientificQualityReport:
    known = {paper.paper_id: paper for paper in papers if paper.provenance != "fixture"}
    actual = [item for item in evidence if item.paper_id in known and item.provenance != "fixture"]
    ids = {item.evidence_id for item in actual}
    annotated = {review.evidence_id: review for review in reviews or []}
    if not set(annotated).issubset(ids):
        raise ValueError("Human evidence judgments reference absent or fixture evidence")
    if len(annotated) != len(reviews or []):
        raise ValueError("Duplicate evidence judgments require explicit adjudication")
    entailed = [
        review.human_entailment_correct
        for review in annotated.values()
        if review.human_entailment_correct is not None
    ]
    location = [
        review.human_location_correct
        for review in annotated.values()
        if review.human_location_correct is not None
    ]
    primary = [
        claim
        for claim in claims
        if claim.primary
        and claim.claim_type != "HYPOTHESIS"
        and set(claim.source_paper_ids).issubset(known)
    ]
    claim_ids = {claim.claim_id for claim in primary}
    labels = claim_support_labels or {}
    if not set(labels).issubset(claim_ids):
        raise ValueError("Claim support labels reference unknown primary claims")
    contradictions = [label for label in contradiction_labels or [] if label.contradiction_present]
    if any(label.claim_id not in {claim.claim_id for claim in claims} for label in contradictions):
        raise ValueError("Contradiction labels reference unknown claims")
    detected = {item.claim_id for item in conflicts}
    return ScientificQualityReport(
        metrics={
            "evidence_location_rate": MeasuredRatio(
                numerator=sum(
                    bool(
                        item.page
                        or item.section
                        or item.source_location == "abstract"
                        or "offsets" in item.source_location
                    )
                    for item in actual
                ),
                denominator=len(actual),
            ),
            "evidence_grounding_rate": MeasuredRatio(
                numerator=sum(grounded_excerpt(known[item.paper_id], item) for item in actual),
                denominator=len(actual),
            ),
            "evidence_entailment_accuracy": MeasuredRatio(
                numerator=sum(entailed), denominator=len(entailed)
            ),
            "human_location_accuracy": MeasuredRatio(
                numerator=sum(location), denominator=len(location)
            ),
            "evidence_contradiction_detection_rate": MeasuredRatio(
                numerator=sum(label.claim_id in detected for label in contradictions),
                denominator=len(contradictions),
            ),
            "unsupported_claim_rate": MeasuredRatio(
                numerator=sum(not supported for supported in labels.values()),
                denominator=len(labels),
            ),
            "structurally_unsupported_claim_rate": MeasuredRatio(
                numerator=sum(
                    not claim.evidence_ids or not set(claim.evidence_ids).issubset(ids)
                    for claim in primary
                ),
                denominator=len(primary),
            ),
        },
        definitions={
            "evidence_location_rate": "Traceable page/section/abstract/offset location availability; not human correctness.",
            "evidence_grounding_rate": "Quote found at the recorded source location, not semantic entailment.",
            "evidence_entailment_accuracy": "Positive independently completed human entailment judgments / completed judgments.",
            "human_location_accuracy": "Correct human-reviewed locations / completed location judgments.",
            "evidence_contradiction_detection_rate": "Detected gold-positive contradictory claims / human-labelled contradictory claims.",
            "unsupported_claim_rate": "Human-labelled unsupported primary claims / independently labelled primary claims.",
            "structurally_unsupported_claim_rate": "Primary claim support missing from actual evidence / primary non-hypothesis claims.",
        },
        limitations=[
            "No human judgments are inferred from LLM confidence.",
            "Missing/empty independent labels produce null ratios.",
            "Fixtures are excluded from scientific metric denominators.",
        ],
    )


def sample_real_evidence(
    papers: list[Paper], evidence: list[Evidence], *, sample_size: int = 20, seed: int = 11
) -> list[Evidence]:
    real = {paper.paper_id for paper in papers if paper.provenance != "fixture"}
    eligible = sorted(
        (item for item in evidence if item.paper_id in real), key=lambda item: str(item.evidence_id)
    )
    return random.Random(seed).sample(eligible, min(sample_size, len(eligible)))


def hardware_parameter_rows(
    assessments: list[HardwareAssessment], evidence: list[Evidence]
) -> list[dict[str, object]]:
    sources = {item.evidence_id: item for item in evidence if item.provenance != "fixture"}
    rows = []
    for assessment in assessments:
        for name, value in assessment.parameters.items():
            if value is None:
                continue
            kind = assessment.parameter_provenance.get(name, "ESTIMATED")
            identities = assessment.parameter_evidence.get(name, [])
            note = ""
            if kind == "SOURCE_REPORTED" and (
                not isinstance(value, (float, int))
                or not identities
                or not all(
                    identity in sources
                    and numeric_quote_support(float(value), sources[identity].verbatim_excerpt)
                    for identity in identities
                )
            ):
                kind, note = (
                    "ESTIMATED",
                    "Source numeric anchors unavailable; source reporting is unverified.",
                )
            if kind == "DERIVED" and not (
                assessment.parameter_derivations.get(name)
                and assessment.parameter_assumptions.get(name)
            ):
                kind, note = "ESTIMATED", "Derivation and assumptions are required."
            if kind == "MEASURED":
                kind, note = (
                    "ESTIMATED",
                    "No independently ingested measurement artifact exists in this research workflow. Author results should be SOURCE_REPORTED.",
                )
            rows.append(
                {
                    "assessment_id": assessment.assessment_id,
                    "parameter": name,
                    "value": value,
                    "provenance": kind,
                    "evidence_ids": ";".join(map(str, identities)),
                    "assumptions": ";".join(assessment.parameter_assumptions.get(name, [])),
                    "derivation": assessment.parameter_derivations.get(name, ""),
                    "notes": note,
                }
            )
    return rows
