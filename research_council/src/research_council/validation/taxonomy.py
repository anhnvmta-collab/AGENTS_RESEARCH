from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID

from research_council.schemas.models import ResearchKnowledgeMap
from research_council.validation.coverage import observed_terms, vocabulary

if TYPE_CHECKING:
    from research_council.core.orchestration.state import WorkflowState


def observed_taxonomy(state: WorkflowState) -> ResearchKnowledgeMap:
    methods = vocabulary("expected_method_families.yaml", "families")
    papers = {
        item.paper.paper_id: item.paper
        for item in state.candidates
        if item.paper.provenance != "fixture"
    }
    texts = {
        identity: f"{paper.metadata.title} {paper.metadata.abstract or ''}"
        for identity, paper in papers.items()
    }
    for row in state.matrix:
        if row.paper_id in texts:
            texts[row.paper_id] += " " + " ".join(value or "" for value in row.fields.values())
    groups: dict[str, set[UUID]] = {}
    for identity, text in texts.items():
        for method in observed_terms(text, methods):
            groups.setdefault(method, set()).add(identity)
    # Source extraction may introduce a method outside the starter vocabulary.
    for row in state.matrix:
        for field in ("recovery_algorithm", "DOA_method", "parameter_estimation_method"):
            label = row.fields.get(field)
            if label and row.paper_id in papers and not observed_terms(label, methods):
                groups.setdefault("Observed: " + label[:100], set()).add(row.paper_id)
    children = []
    for name, identities in sorted(groups.items()):
        claims = [item.claim_id for item in state.claims if set(item.source_paper_ids) & identities]
        evidence_ids = {item.evidence_id for item in state.evidence if item.paper_id in identities}
        gaps = [
            item.gap_id
            for item in state.gaps
            if set(item.evidence_ids) & evidence_ids or set(item.claim_ids) & set(claims)
        ]
        with_evidence = {item.paper_id for item in state.evidence if item.paper_id in identities}
        children.append(
            ResearchKnowledgeMap(
                topic=name,
                paper_ids=sorted(identities, key=str),
                claim_ids=claims,
                gap_ids=gaps,
                coverage_score=len(with_evidence) / len(identities),
                coverage_basis="Observed member papers with evidence; lexical/extraction classification, not universal coverage.",
            )
        )
    return ResearchKnowledgeMap(
        topic="Observed FHSS / wideband sparse signal literature",
        subtopics=children,
        paper_ids=list(papers),
        coverage_basis="Empty families are omitted; observed extraction may add new families. No curated seed is automatically a retrieved finding.",
    )
