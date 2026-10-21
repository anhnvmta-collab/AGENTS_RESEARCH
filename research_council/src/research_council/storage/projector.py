from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import uuid5

from sqlalchemy.engine import Connection

from research_council.core.grounding import grounded_excerpt
from research_council.core.integrity import synchronize_conflicts, validate_graph
from research_council.core.orchestration.state import WorkflowState
from research_council.repositories.store import normalized_title
from research_council.schemas.models import ResearchRun, VerificationStatus
from research_council.storage.graph import project_graph, record_id

if TYPE_CHECKING:
    from research_council.repositories.store import SQLRepository


def project_state(
    repository: SQLRepository, connection: Connection, run: ResearchRun, state: WorkflowState
) -> None:
    """Project typed checkpoint artifacts into queryable tables in the same transaction."""
    synchronize_conflicts(state)
    validate_graph(state)
    project_graph(repository, connection, run.run_id, state)
    papers = {candidate.paper.paper_id: candidate.paper for candidate in state.candidates}
    evidence = {item.evidence_id: item for item in state.evidence}
    for paper in papers.values():
        repository._put(
            connection,
            "papers",
            str(paper.paper_id),
            paper.model_dump(mode="json"),
            doi=paper.metadata.doi,
            normalized_title=normalized_title(paper.metadata.title),
        )
        repository._put(
            connection,
            "paper_metadata",
            str(paper.paper_id),
            paper.metadata.model_dump(mode="json"),
            paper_id=str(paper.paper_id),
        )
    for item in state.evidence:
        source_paper = papers.get(item.paper_id)
        if source_paper is None or not grounded_excerpt(source_paper, item):
            raise ValueError("Checkpoint contains ungrounded evidence")
        repository._put(
            connection,
            "evidence",
            str(record_id(run.run_id, "evidence", item.evidence_id)),
            item.model_dump(mode="json"),
            run_id=str(run.run_id),
            paper_id=str(item.paper_id),
        )
    for claim in state.claims:
        if not set(claim.evidence_ids + claim.contradicting_evidence_ids).issubset(evidence):
            raise ValueError("Checkpoint claim references unknown evidence")
        if not set(claim.source_paper_ids).issubset(papers):
            raise ValueError("Checkpoint claim references unknown papers")
        if any(
            evidence[identity].paper_id not in claim.source_paper_ids
            for identity in claim.evidence_ids
        ):
            raise ValueError("Checkpoint claim/paper mismatch")
        if claim.verification_status == VerificationStatus.VERIFIED:
            if any(
                evidence[identity].verification_status != VerificationStatus.VERIFIED
                for identity in claim.evidence_ids
            ):
                raise ValueError("Checkpoint verified claim lacks verified evidence")
            if any(papers[identity].provenance == "fixture" for identity in claim.source_paper_ids):
                raise ValueError("Synthetic fixtures cannot support verified claims")
        repository._put(
            connection,
            "claims",
            str(record_id(run.run_id, "claims", claim.claim_id)),
            claim.model_dump(mode="json"),
            run_id=str(run.run_id),
        )
    for name, items, key in (
        ("search_queries", state.queries, "query_id"),
        ("gaps", state.gaps, "gap_id"),
        ("novelty_candidates", state.novelty_candidates, "candidate_id"),
        ("reviews", state.reviews, "review_id"),
        ("quality_gate_results", state.gates, "gate_id"),
    ):
        for artifact in items:
            repository._put(
                connection,
                name,
                str(
                    record_id(
                        run.run_id, name, getattr(artifact, key), getattr(artifact, "revision", 1)
                    )
                ),
                artifact.model_dump(mode="json"),
                run_id=str(run.run_id),
            )
    for report in state.prior_art:
        for match in report.matches:
            repository._put(
                connection,
                "prior_art_matches",
                str(record_id(run.run_id, "prior_art_matches", match.match_id)),
                match.model_dump(mode="json"),
                run_id=str(run.run_id),
            )
    for audit in state.audits:
        repository._put(
            connection,
            "citation_audits",
            str(record_id(run.run_id, "citation_audits", audit.audit_id)),
            audit.model_dump(mode="json"),
            run_id=str(run.run_id),
            paper_id=str(audit.paper_id),
        )
    for candidate in state.candidates:
        if candidate.score:
            repository._put(
                connection,
                "paper_scores",
                str(uuid5(run.run_id, str(candidate.paper.paper_id))),
                candidate.score.model_dump(mode="json"),
                run_id=str(run.run_id),
                paper_id=str(candidate.paper.paper_id),
            )
