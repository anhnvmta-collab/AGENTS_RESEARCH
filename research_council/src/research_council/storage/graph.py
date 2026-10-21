from __future__ import annotations

from collections.abc import Sequence
from typing import TYPE_CHECKING
from uuid import UUID, uuid5

from sqlalchemy import delete, insert
from sqlalchemy.engine import Connection

from research_council.schemas.models import Schema
from research_council.storage.database import tables

if TYPE_CHECKING:
    from research_council.core.orchestration.state import WorkflowState
    from research_council.repositories.store import SQLRepository


def record_id(run_id: UUID, kind: str, identity: UUID, revision: int = 1) -> UUID:
    return uuid5(run_id, f"{kind}:{identity}:{revision}")


def project_graph(
    repository: SQLRepository, connection: Connection, run_id: UUID, state: WorkflowState
) -> None:
    nodes: dict[tuple[str, UUID, int], UUID] = {}

    def node(kind: str, identity: UUID, obj: Schema, revision: int = 1) -> None:
        identity_key = record_id(run_id, kind, identity, revision)
        nodes[kind, identity, revision] = identity_key
        repository._put(
            connection,
            "scientific_artifacts",
            str(identity_key),
            obj.model_dump(mode="json"),
            run_id=str(run_id),
            artifact_type=kind,
            artifact_id=str(identity),
            revision=revision,
        )

    for source_candidate in state.candidates:
        node("papers", source_candidate.paper.paper_id, source_candidate.paper)
    collections: list[tuple[str, Sequence[Schema], str]] = [
        ("chunks", state.chunks, "chunk_id"),
        ("targeted_search_requests", state.targeted_requests, "request_id"),
        ("evidence", state.evidence, "evidence_id"),
        ("claims", state.claims, "claim_id"),
        ("gaps", state.gaps, "gap_id"),
        ("search_queries", state.queries, "query_id"),
        ("reviews", state.reviews, "review_id"),
        ("decisions", state.decisions, "decision_id"),
        ("experiments", state.experiments, "experiment_id"),
        ("citation_audits", state.audits, "audit_id"),
        ("quality_gate_results", state.gates, "gate_id"),
        ("conflicts", state.conflicts, "conflict_id"),
        ("hardware", state.hardware, "assessment_id"),
    ]
    for kind, objects, attribute in collections:
        for obj in objects:
            node(kind, getattr(obj, attribute), obj)
    for candidate in state.novelty_candidates:
        node("novelty_candidates", candidate.candidate_id, candidate, candidate.revision)
    for report in state.prior_art:
        node(
            "prior_art_reports", uuid5(report.candidate_id, f"prior-art:{report.revision}"), report
        )
        for match in report.matches:
            node("prior_art_matches", match.match_id, match)
    node("paper_plans", state.outline.plan_id, state.outline)
    links = tables["scientific_links"]
    connection.execute(delete(links).where(links.c.run_id == str(run_id)))

    def edge(source: tuple[str, UUID, int], target: tuple[str, UUID, int], relation: str) -> None:
        left, right = nodes[source], nodes[target]
        identity = uuid5(run_id, f"{left}:{relation}:{right}")
        connection.execute(
            insert(links).values(
                id=str(identity),
                run_id=str(run_id),
                source_id=str(left),
                target_id=str(right),
                relation=relation,
            )
        )

    for chunk in state.chunks:
        edge(("chunks", chunk.chunk_id, 1), ("papers", chunk.paper_id, 1), "source_paper")
    for evidence in state.evidence:
        edge(
            ("evidence", evidence.evidence_id, 1), ("papers", evidence.paper_id, 1), "source_paper"
        )
        if evidence.chunk_id:
            edge(
                ("evidence", evidence.evidence_id, 1),
                ("chunks", evidence.chunk_id, 1),
                "source_chunk",
            )
    for claim in state.claims:
        for identity in claim.evidence_ids:
            edge(("claims", claim.claim_id, 1), ("evidence", identity, 1), "supporting_evidence")
        for identity in claim.contradicting_evidence_ids:
            edge(("claims", claim.claim_id, 1), ("evidence", identity, 1), "contradicting_evidence")
    for gap in state.gaps:
        for identity in gap.evidence_ids:
            edge(("gaps", gap.gap_id, 1), ("evidence", identity, 1), "existing_evidence")
        for identity in gap.claim_ids:
            edge(("gaps", gap.gap_id, 1), ("claims", identity, 1), "limited_claim")
    for candidate in state.novelty_candidates:
        for identity in candidate.gap_ids:
            edge(
                ("novelty_candidates", candidate.candidate_id, candidate.revision),
                ("gaps", identity, 1),
                "research_gap",
            )
        for identity in candidate.evidence_ids:
            edge(
                ("novelty_candidates", candidate.candidate_id, candidate.revision),
                ("evidence", identity, 1),
                "novelty_evidence",
            )
    for report in state.prior_art:
        source = (
            "prior_art_reports",
            uuid5(report.candidate_id, f"prior-art:{report.revision}"),
            1,
        )
        edge(
            source, ("novelty_candidates", report.candidate_id, report.revision), "attacks_revision"
        )
        for match in report.matches:
            edge(
                ("prior_art_matches", match.match_id, 1),
                ("papers", match.paper_id, 1),
                "prior_art_source",
            )
            edge(source, ("prior_art_matches", match.match_id, 1), "ranked_overlap")
    for request in state.targeted_requests:
        edge(
            ("targeted_search_requests", request.request_id, 1),
            ("novelty_candidates", request.candidate_id, request.revision),
            "investigates_revision",
        )
    for review_report in state.reviews:
        edge(
            ("reviews", review_report.review_id, 1),
            ("novelty_candidates", review_report.candidate_id, review_report.revision),
            "reviews_revision",
        )
    for decision in state.decisions:
        edge(
            ("decisions", decision.decision_id, 1),
            ("novelty_candidates", decision.candidate_id, decision.revision),
            "judges_revision",
        )
        for review_report in state.reviews:
            if (
                review_report.candidate_id == decision.candidate_id
                and review_report.revision == decision.revision
            ):
                edge(
                    ("decisions", decision.decision_id, 1),
                    ("reviews", review_report.review_id, 1),
                    "independent_review",
                )
        edge(
            ("decisions", decision.decision_id, 1),
            (
                "prior_art_reports",
                uuid5(decision.candidate_id, f"prior-art:{decision.revision}"),
                1,
            ),
            "prior_art_attack",
        )
    for conflict in state.conflicts:
        edge(
            ("conflicts", conflict.conflict_id, 1),
            ("claims", conflict.claim_id, 1),
            "conflicting_claim",
        )
        for identity in conflict.contradicting:
            edge(
                ("conflicts", conflict.conflict_id, 1),
                ("evidence", identity, 1),
                "contradicting_evidence",
            )
    for experiment in state.experiments:
        for identity in experiment.candidate_ids:
            edge(
                ("experiments", experiment.experiment_id, 1),
                ("novelty_candidates", identity, experiment.candidate_revisions[identity]),
                "tests_revision",
            )
        for identity in experiment.claim_ids:
            edge(
                ("experiments", experiment.experiment_id, 1), ("claims", identity, 1), "tests_claim"
            )
        for identity in experiment.gap_ids:
            edge(("experiments", experiment.experiment_id, 1), ("gaps", identity, 1), "tests_gap")
    for identity in state.outline.experiment_ids:
        edge(
            ("paper_plans", state.outline.plan_id, 1),
            ("experiments", identity, 1),
            "experiment_plan",
        )
    for identity in state.outline.claim_ids:
        edge(("paper_plans", state.outline.plan_id, 1), ("claims", identity, 1), "paper_claim")
