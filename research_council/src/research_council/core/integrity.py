"""Complete scientific graph validation; no SQL, providers or workflow scheduling."""

from __future__ import annotations

from collections.abc import Iterable
from typing import TYPE_CHECKING, Any
from uuid import UUID, uuid5

from research_council.core.grounding import grounded_excerpt
from research_council.knowledge.retrieval import source_hash
from research_council.schemas.models import (
    CitationAudit,
    ConflictResolution,
    EvidenceConflict,
    NoveltyDecision,
    PriorArtReport,
    ResearchClaim,
    ReviewerReport,
    Schema,
    VerificationStatus,
)

if TYPE_CHECKING:
    from research_council.core.orchestration.state import WorkflowState


def unique(items: Iterable[Schema], field: str) -> dict[UUID, Any]:
    result: dict[UUID, Any] = {}
    for item in items:
        identity = getattr(item, field)
        if identity in result:
            raise ValueError(f"Duplicate {field}: {identity}")
        result[identity] = item
    return result


def require(references: Iterable[UUID], available: dict[UUID, Any], edge: str) -> None:
    if not set(references).issubset(available):
        raise ValueError(f"Dangling {edge} reference")


def synchronize_conflicts(state: WorkflowState) -> None:
    """Never delete conflicts when later model output omits a contradictory edge."""
    existing = {
        (item.claim_id, tuple(sorted(map(str, item.contradicting)))) for item in state.conflicts
    }
    for claim in state.claims:
        historical = [
            identity
            for item in state.conflicts
            if item.claim_id == claim.claim_id
            for identity in item.contradicting
        ]
        claim.contradicting_evidence_ids = list(
            dict.fromkeys([*claim.contradicting_evidence_ids, *historical])
        )
        key = (claim.claim_id, tuple(sorted(map(str, claim.contradicting_evidence_ids))))
        if claim.contradicting_evidence_ids and key not in existing:
            state.conflicts.append(
                EvidenceConflict(
                    conflict_id=uuid5(claim.claim_id, "conflict:" + ",".join(key[1])),
                    claim_id=claim.claim_id,
                    supporting=claim.evidence_ids,
                    contradicting=claim.contradicting_evidence_ids,
                )
            )


def unresolved_conflict(claim: ResearchClaim, conflicts: list[EvidenceConflict]) -> bool:
    covered = {
        identity
        for item in conflicts
        if item.conflict_id in claim.resolved_conflict_ids
        and item.claim_id == claim.claim_id
        and item.resolution_status == ConflictResolution.RESOLVED
        for identity in item.contradicting
    }
    return not set(claim.contradicting_evidence_ids).issubset(covered) or any(
        item.claim_id == claim.claim_id
        and item.severity == "HIGH"
        and item.resolution_status != ConflictResolution.RESOLVED
        for item in conflicts
    )


def citation_conflict_open(
    audit: CitationAudit, claim: ResearchClaim, conflicts: list[EvidenceConflict]
) -> bool:
    if audit.status != VerificationStatus.CONTRADICTED:
        return False
    failures = {key for key, value in audit.checks.items() if value is False}
    return failures != {"claim_evidence_consistent"} or unresolved_conflict(claim, conflicts)


def validate_graph(state: WorkflowState) -> None:
    # Round trip catches model_copy/list mutation bypasses at the persistence boundary.
    state.__class__.model_validate_json(state.model_dump_json())
    papers = unique((item.paper for item in state.candidates), "paper_id")
    require(state.core_paper_ids, papers, "core-to-paper")
    for identity_audit in state.identity_audits:
        require([identity_audit.paper_id], papers, "identity-audit-to-paper")
    evidence = unique(state.evidence, "evidence_id")
    claims = unique(state.claims, "claim_id")
    gaps = unique(state.gaps, "gap_id")
    unique(state.queries, "query_id")
    conflicts = unique(state.conflicts, "conflict_id")
    chunks = unique(state.chunks, "chunk_id")
    for chunk in chunks.values():
        require([chunk.paper_id], papers, "chunk-to-paper")
        paper = papers[chunk.paper_id]
        text = paper.page_texts.get(chunk.page, "") if chunk.page else paper.source_text or ""
        if (
            chunk.source_sha256 != source_hash(paper)
            or text[chunk.start_offset : chunk.end_offset] != chunk.text
        ):
            raise ValueError("Source chunk hash or offsets do not match paper")
    unique(state.reviews, "review_id")
    unique(state.decisions, "decision_id")
    revisions: dict[tuple[UUID, int], Any] = {}
    for candidate in state.novelty_candidates:
        key = (candidate.candidate_id, candidate.revision)
        if key in revisions:
            raise ValueError("Duplicate candidate revision")
        revisions[key] = candidate
        require(candidate.gap_ids, gaps, "novelty-to-gap")
        require(candidate.evidence_ids, evidence, "novelty-to-evidence")
        if candidate.novelty_claim_id:
            require([candidate.novelty_claim_id], claims, "novelty-to-claim")
        require(candidate.trigger_prior_art_ids, papers, "revision-to-trigger-prior-art")
    for item in evidence.values():
        require([item.paper_id], papers, "evidence-to-paper")
        paper = papers[item.paper_id]
        if not grounded_excerpt(paper, item):
            raise ValueError("Checkpoint contains ungrounded evidence in scientific graph")
        if item.provenance != paper.provenance:
            raise ValueError("Evidence provenance does not match its paper")
        if item.source_sha256 and item.source_sha256 != source_hash(paper):
            raise ValueError("Evidence source hash mismatch")
        if item.chunk_id:
            require([item.chunk_id], chunks, "evidence-to-chunk")
            chunk = chunks[item.chunk_id]
            if chunk.paper_id != item.paper_id or " ".join(
                item.verbatim_excerpt.split()
            ) not in " ".join(chunk.text.split()):
                raise ValueError("Evidence does not quote its source chunk")
        if item.claim_id:
            require([item.claim_id], claims, "evidence-to-claim")
    for claim in claims.values():
        require(claim.resolved_conflict_ids, conflicts, "claim-to-resolved-conflict")
        if any(
            conflicts[identity].claim_id != claim.claim_id
            or conflicts[identity].resolution_status != ConflictResolution.RESOLVED
            for identity in claim.resolved_conflict_ids
        ):
            raise ValueError("Claim references an unresolved or unrelated conflict")
        require(claim.source_paper_ids, papers, "claim-to-paper")
        require(
            claim.evidence_ids + claim.contradicting_evidence_ids, evidence, "claim-to-evidence"
        )
        if any(
            evidence[identity].paper_id not in claim.source_paper_ids
            for identity in claim.evidence_ids
        ):
            raise ValueError("Claim/evidence paper mismatch")
        if claim.verification_status == VerificationStatus.VERIFIED:
            if any(
                evidence[identity].verification_status != VerificationStatus.VERIFIED
                for identity in claim.evidence_ids
            ):
                raise ValueError("Verified claim requires verified evidence")
            if any(papers[identity].provenance == "fixture" for identity in claim.source_paper_ids):
                raise ValueError("Fixture cannot verify a scientific claim")
            if unresolved_conflict(claim, state.conflicts):
                raise ValueError("Verified claim has an unresolved evidence conflict")
    for gap in gaps.values():
        require(gap.known_prior_approaches, papers, "gap-to-known-prior-approach")
        require(gap.evidence_ids, evidence, "gap-to-evidence")
        require(gap.claim_ids, claims, "gap-to-claim")
    for conflict in state.conflicts:
        require([conflict.claim_id], claims, "conflict-to-claim")
        require(conflict.supporting + conflict.contradicting, evidence, "conflict-to-evidence")
    for row in state.matrix:
        require([row.paper_id], papers, "matrix-to-paper")
        require(row.evidence_ids, evidence, "matrix-to-evidence")
    reports: list[PriorArtReport | ReviewerReport | NoveltyDecision] = [
        *state.prior_art,
        *state.reviews,
        *state.decisions,
    ]
    for report in reports:
        if (report.candidate_id, report.revision) not in revisions:
            raise ValueError("Report references unknown candidate revision")
    for request in state.targeted_requests:
        if (request.candidate_id, request.revision) not in revisions:
            raise ValueError("Targeted search references unknown candidate revision")
    for report in state.prior_art:
        for match in report.matches:
            if (
                match.candidate_id != report.candidate_id
                or match.candidate_revision != report.revision
            ):
                raise ValueError("Prior-art match revision mismatch")
            require([match.paper_id], papers, "prior-art-to-paper")
            require(match.evidence_ids, evidence, "prior-art-to-evidence")
    for report in state.reviews:
        for reason in report.reasons:
            require(reason.evidence_ids, evidence, "review-to-evidence")
    for decision in state.decisions:
        require(decision.closest_prior_art, papers, "decision-to-prior-art")
        if not any(
            report.candidate_id == decision.candidate_id and report.revision == decision.revision
            for report in state.prior_art
        ) or not any(
            report.candidate_id == decision.candidate_id and report.revision == decision.revision
            for report in state.reviews
        ):
            raise ValueError("Decision lacks matching prior-art and reviewer reports")
    experiments = unique(state.experiments, "experiment_id")
    for experiment in experiments.values():
        require(experiment.gap_ids, gaps, "experiment-to-gap")
        require(experiment.claim_ids, claims, "experiment-to-claim")
        for identity in experiment.candidate_ids:
            revision = experiment.candidate_revisions.get(identity)
            if (identity, revision) not in revisions:
                raise ValueError("Experiment references unknown candidate revision")
        if set(experiment.candidate_revisions) != set(experiment.candidate_ids):
            raise ValueError("Experiment candidate revision map is incomplete")
    require(state.outline.experiment_ids, experiments, "paper-plan-to-experiment")
    require(state.outline.claim_ids, claims, "paper-plan-to-claim")
    for assessment in state.hardware:
        require(assessment.paper_ids, papers, "hardware-to-paper")
        require(assessment.evidence_ids, evidence, "hardware-to-evidence")
        for identities in assessment.parameter_evidence.values():
            require(identities, evidence, "hardware-parameter-to-evidence")
            if not set(identities).issubset(assessment.evidence_ids):
                raise ValueError("Hardware parameter evidence is outside assessment scope")
    for audit in state.audits:
        require([audit.paper_id], papers, "audit-to-paper")
        require(audit.claim_ids, claims, "audit-to-claim")
        if any(
            audit.paper_id not in claims[identity].source_paper_ids for identity in audit.claim_ids
        ):
            raise ValueError("Audit claim/paper mismatch")
    require(state.synthesis.claim_ids, claims, "synthesis-to-claim")
    if any(
        claims[identity].verification_status != VerificationStatus.VERIFIED
        for identity in state.synthesis.claim_ids
    ):
        raise ValueError("Synthesis references unverified scientific claims")

    def validate_map(node: Any) -> None:
        require(node.paper_ids, papers, "map-to-paper")
        require(node.claim_ids, claims, "map-to-claim")
        require(node.gap_ids, gaps, "map-to-gap")
        for child in node.subtopics:
            validate_map(child)

    if state.knowledge_map:
        validate_map(state.knowledge_map)
