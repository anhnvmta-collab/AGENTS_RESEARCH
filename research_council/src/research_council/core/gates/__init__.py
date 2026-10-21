from __future__ import annotations

from typing import TYPE_CHECKING

from research_council.core.grounding import grounded_excerpt
from research_council.core.integrity import unresolved_conflict
from research_council.schemas.models import (
    CitationAudit,
    Evidence,
    EvidenceConflict,
    ExperimentPlan,
    ModelExecution,
    NoveltyCandidate,
    NoveltyDecision,
    Paper,
    PriorArtReport,
    QualityGateResult,
    ResearchClaim,
    ReviewerReport,
    VerificationStatus,
)

if TYPE_CHECKING:
    from research_council.agents.contracts import PaperOutline


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
            if (
                paper.provenance != "fixture"
                and not meta.metadata_verified
                and meta.metadata_source != "local_sidecar"
            ):
                reasons.append(f"Unverified source identity: {paper.paper_id}")
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
        papers: list[Paper] | None = None,
        executions: list[ModelExecution] | None = None,
        conflicts: list[EvidenceConflict] | None = None,
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
        if not prior_art.search_attempts or any(
            item.status != "SUCCESS" for item in prior_art.search_attempts
        ):
            reasons.append("Successful operational prior-art search records are required.")
        searched = {
            item.query.text
            for item in prior_art.search_attempts
            if item.query and item.status == "SUCCESS"
        }
        if not set(prior_art.queries).issubset(searched):
            reasons.append("Not every reported prior-art query was executed successfully.")
        execution_map = {item.execution_id: item for item in executions or []}
        for report, role in (
            (prior_art, "PriorArtHunter"),
            (review, "ReviewerTwo"),
            (decision, "NoveltyJudge"),
        ):
            execution = (
                execution_map.get(report.model_execution_id) if report.model_execution_id else None
            )
            if (
                not execution
                or execution.agent_id != role
                or execution.status != "SUCCESS"
                or not execution.structured_output_valid
            ):
                reasons.append(f"Completed {role} model execution is missing.")
        if not review.complete:
            reasons.append("Independent review is incomplete.")
        if decision.verdict != "SURVIVE" or review.verdict != "SURVIVES":
            reasons.append("Novelty has not survived independent review and judgment.")
        paper_map = {paper.paper_id: paper for paper in papers or []}
        grounded = {
            item.evidence_id
            for item in evidence
            if item.verification_status
            in (VerificationStatus.PARTIALLY_VERIFIED, VerificationStatus.VERIFIED)
            and item.provenance != "fixture"
            and item.paper_id in paper_map
            and grounded_excerpt(paper_map[item.paper_id], item)
            and SourceIntegrityGate().evaluate([paper_map[item.paper_id]]).passed
        }
        if len(set(candidate.evidence_ids) & grounded) < self.minimum_evidence or not set(
            candidate.evidence_ids
        ).issubset(grounded):
            reasons.append("Insufficient grounded evidence for the contribution.")
        if any(item.severity == "HIGH" and not item.resolved for item in review.reasons):
            reasons.append("Unresolved high-severity review contradiction.")
        if any(match.invalidates for match in prior_art.matches):
            reasons.append("Prior art invalidates the novelty claim.")
        if any(match.severity == "HIGH" for match in prior_art.matches):
            reasons.append("High-severity prior-art overlap remains unresolved.")
        if any(
            item.severity == "HIGH"
            and item.resolution_status != "RESOLVED"
            and set(item.supporting + item.contradicting) & set(candidate.evidence_ids)
            for item in conflicts or []
        ):
            reasons.append("Novelty depends on unresolved evidence conflict.")
        return QualityGateResult(
            gate=2,
            passed=not reasons,
            reasons=reasons,
            checked_ids=[candidate.candidate_id, review.review_id, decision.decision_id],
            candidate_id=candidate.candidate_id,
            candidate_revision=candidate.revision,
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
        conflicts: list[EvidenceConflict] | None = None,
        outline: PaperOutline | None = None,
        novelty_candidates: list[NoveltyCandidate] | None = None,
    ) -> QualityGateResult:
        reasons: list[str] = []
        primary = [claim for claim in claims if claim.primary]
        known_papers = {paper.paper_id: paper for paper in papers}
        known_evidence = {item.evidence_id: item for item in evidence}
        verified_audits = [
            audit
            for audit in audits
            if audit.status == VerificationStatus.VERIFIED
            and audit.verifier != "automatic"
            and audit.checks.get("scientific_entailment") is True
            and audit.checks.get("source_location") is True
            and audit.checks.get("not_retracted") is True
        ]
        if not primary:
            reasons.append("No primary scientific claims available.")
        for claim in primary:
            if (
                claim.verification_status != VerificationStatus.VERIFIED
                or claim.contradicting_evidence_ids
                or unresolved_conflict(claim, conflicts or [])
            ):
                reasons.append(f"Primary claim is not verified: {claim.claim_id}")
            if not claim.source_paper_ids:
                reasons.append(f"Primary claim has no source papers: {claim.claim_id}")
            if any(
                audit.status == VerificationStatus.CONTRADICTED
                and claim.claim_id in audit.claim_ids
                for audit in audits
            ):
                reasons.append(f"Unresolved citation conflict: {claim.claim_id}")
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
            not plan.baselines
            or not plan.metrics
            or not plan.procedures
            or not plan.ablations
            or not plan.hypothesis
            or not plan.acceptance_criteria
            or not plan.failure_cases
            or not plan.reproducibility
            or not plan.statistical_plan
            for plan in experiments
        ):
            reasons.append(
                "Experimental plans require hypothesis, baselines, metrics, ablations, procedures, statistics, failure cases, acceptance criteria and reproducibility."
            )
        if (
            not outline
            or not outline.sections
            or not {item.experiment_id for item in experiments}.issubset(
                set(outline.experiment_ids)
            )
        ):
            reasons.append("A linked paper roadmap is required.")
        claim_map = {item.claim_id: item for item in claims}
        for candidate in novelty_candidates or []:
            novelty_claim = (
                claim_map.get(candidate.novelty_claim_id) if candidate.novelty_claim_id else None
            )
            if (
                novelty_claim is None
                or novelty_claim.verification_status != VerificationStatus.VERIFIED
                or novelty_claim.claim_type == "HYPOTHESIS"
            ):
                reasons.append(
                    f"Primary novelty remains unverified: {candidate.candidate_id} revision {candidate.revision}"
                )
        if not limitations:
            reasons.append("Limitations must be stated.")
        return QualityGateResult(
            gate=3,
            passed=not reasons,
            reasons=list(dict.fromkeys(reasons)),
            checked_ids=[claim.claim_id for claim in primary],
        )
