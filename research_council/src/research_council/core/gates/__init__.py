from __future__ import annotations

from research_council.core.grounding import grounded_excerpt
from research_council.schemas.models import (
    CitationAudit,
    Evidence,
    ExperimentPlan,
    NoveltyCandidate,
    NoveltyDecision,
    Paper,
    PriorArtReport,
    QualityGateResult,
    ResearchClaim,
    ReviewerReport,
    VerificationStatus,
)


class SourceIntegrityGate:
    def evaluate(self, papers: list[Paper]) -> QualityGateResult:
        reasons: list[str] = []
        if not papers:
            reasons.append("No source papers were retrieved.")
        seen: set[str] = set()
        for paper in papers:
            meta = paper.metadata
            identity = meta.doi or " ".join(meta.title.casefold().split())
            if identity in seen:
                reasons.append(f"Duplicate source identity: {paper.paper_id}")
            seen.add(identity)
            if (
                not meta.authors
                or meta.year is None
                or not (meta.doi or meta.url or paper.source_path)
            ):
                reasons.append(f"Incomplete paper identity: {paper.paper_id}")
            if not paper.source_text or not paper.source_text.strip():
                reasons.append(f"Source text unavailable: {paper.paper_id}")
            if meta.retracted is True:
                reasons.append(f"Retracted source: {paper.paper_id}")
        return QualityGateResult(
            gate=1,
            passed=not reasons,
            reasons=reasons,
            checked_ids=[item.paper_id for item in papers],
        )


class NoveltySurvivalGate:
    def __init__(self, minimum_evidence: int = 2) -> None:
        self.minimum_evidence = minimum_evidence

    def evaluate(
        self,
        candidate: NoveltyCandidate,
        evidence: list[Evidence],
        prior_art: PriorArtReport,
        review: ReviewerReport,
        decision: NoveltyDecision,
    ) -> QualityGateResult:
        reasons: list[str] = []
        records = (prior_art, review, decision)
        if any(
            item.candidate_id != candidate.candidate_id or item.revision != candidate.revision
            for item in records
        ):
            reasons.append("Reports do not match this candidate revision.")
        if not prior_art.complete or prior_art.search_failures or not prior_art.queries:
            reasons.append("Prior-art search is incomplete.")
        if not review.complete:
            reasons.append("Independent review is incomplete.")
        if decision.verdict != "SURVIVE" or review.verdict != "SURVIVES":
            reasons.append("Novelty has not survived independent review and judgment.")
        grounded = {
            item.evidence_id
            for item in evidence
            if item.verification_status
            in (VerificationStatus.PARTIALLY_VERIFIED, VerificationStatus.VERIFIED)
            and item.provenance != "fixture"
        }
        if len(set(candidate.evidence_ids) & grounded) < self.minimum_evidence or not set(
            candidate.evidence_ids
        ).issubset(grounded):
            reasons.append("Insufficient grounded evidence for the contribution.")
        if any(item.severity == "HIGH" and not item.resolved for item in review.reasons):
            reasons.append("Unresolved high-severity review contradiction.")
        if any(match.invalidates for match in prior_art.matches):
            reasons.append("Prior art invalidates the novelty claim.")
        return QualityGateResult(
            gate=2,
            passed=not reasons,
            reasons=reasons,
            checked_ids=[candidate.candidate_id, review.review_id, decision.decision_id],
        )


class PublicationReadinessGate:
    def evaluate(
        self,
        papers: list[Paper],
        claims: list[ResearchClaim],
        evidence: list[Evidence],
        audits: list[CitationAudit],
        experiments: list[ExperimentPlan],
        limitations: list[str],
    ) -> QualityGateResult:
        reasons: list[str] = []
        primary = [claim for claim in claims if claim.primary]
        known_papers = {paper.paper_id: paper for paper in papers}
        known_evidence = {item.evidence_id: item for item in evidence}
        verified_audits = [
            audit
            for audit in audits
            if audit.status == VerificationStatus.VERIFIED and audit.verifier != "automatic"
        ]
        if not primary:
            reasons.append("No primary scientific claims available.")
        for claim in primary:
            if (
                claim.verification_status != VerificationStatus.VERIFIED
                or claim.contradicting_evidence_ids
            ):
                reasons.append(f"Primary claim is not verified: {claim.claim_id}")
            if not claim.evidence_ids or not set(claim.evidence_ids).issubset(known_evidence):
                reasons.append(f"Missing primary evidence: {claim.claim_id}")
            for identity in claim.evidence_ids:
                support = known_evidence.get(identity)
                if support and (
                    support.verification_status != VerificationStatus.VERIFIED
                    or support.paper_id not in claim.source_paper_ids
                    or support.paper_id not in known_papers
                    or not grounded_excerpt(known_papers[support.paper_id], support)
                ):
                    reasons.append(f"Invalid evidence support: {identity}")
            if any(
                not any(
                    audit.paper_id == identity and claim.claim_id in audit.claim_ids
                    for audit in verified_audits
                )
                for identity in claim.source_paper_ids
            ):
                reasons.append(f"Independent scientific citation audit required: {claim.claim_id}")
            for identity in claim.source_paper_ids:
                paper = known_papers.get(identity)
                if not paper or paper.provenance == "fixture" or paper.metadata.retracted is True:
                    reasons.append(f"Invalid primary publication source: {identity}")
        if not experiments or any(
            not plan.baselines or not plan.metrics or not plan.procedures for plan in experiments
        ):
            reasons.append("Experimental plans require baselines, metrics and procedures.")
        if not limitations:
            reasons.append("Limitations must be stated.")
        return QualityGateResult(
            gate=3,
            passed=not reasons,
            reasons=list(dict.fromkeys(reasons)),
            checked_ids=[claim.claim_id for claim in primary],
        )
