"""Bounded source quotes for prior-art attacks; no inferred scientific entailment."""

from __future__ import annotations

from uuid import uuid5

from research_council.core.grounding import grounded_excerpt
from research_council.core.orchestration.state import WorkflowState
from research_council.knowledge.retrieval import (
    LexicalEvidenceRetriever,
    LocatedChunker,
    source_hash,
)
from research_council.schemas.models import Evidence, Paper, PriorArtReport, VerificationStatus
from research_council.tools.discovery import PaperDeduplicator


def prior_art_quotes(papers: list[Paper], query: str) -> list[Evidence]:
    result = []
    for paper in papers[:20]:
        if paper.provenance == "fixture":
            continue
        ranked = LexicalEvidenceRetriever().rank(query, LocatedChunker().chunk(paper), limit=1)
        if not ranked:
            continue
        chunk = ranked[0].chunk
        excerpt = chunk.text[:400]
        result.append(
            Evidence(
                evidence_id=uuid5(paper.paper_id, f"prior-art:{chunk.source_sha256}:{excerpt}"),
                paper_id=paper.paper_id,
                evidence_type="PRIOR_ART_SOURCE_QUOTE",
                source_location="abstract"
                if paper.source_kind == "abstract"
                else f"source chunk {chunk.chunk_id}",
                page=chunk.page,
                verbatim_excerpt=excerpt,
                normalized_statement=excerpt,
                agent_interpretation="Retrieved quote only; overlap and scientific entailment require review.",
                extraction_agent="PriorArtSourceRetriever",
                provenance=paper.provenance,
                source_sha256=chunk.source_sha256,
                chunk_id=chunk.chunk_id,
                verification_status=VerificationStatus.PARTIALLY_VERIFIED,
            )
        )
    return list({item.evidence_id: item for item in result}.values())


def merge_prior_art_sources(
    report: PriorArtReport, original_papers: list[Paper], state: WorkflowState
) -> None:
    """Remap deduplicated identities only when the retained snapshot grounds the quote."""
    canonical = {
        old.paper_id: next(
            (item.paper for item in state.candidates if PaperDeduplicator.same(old, item.paper)),
            None,
        )
        for old in original_papers
    }
    evidence_map = {item.evidence_id: item for item in state.evidence}
    remapped = {}
    retained = []
    for old in report.discovered_evidence:
        paper = canonical.get(old.paper_id)
        if paper is None:
            continue
        item = old.model_copy(update={"paper_id": paper.paper_id})
        if not grounded_excerpt(paper, item):
            continue
        chunks = LocatedChunker().chunk(paper)
        chunk = next(
            (
                chunk
                for chunk in chunks
                if item.verbatim_excerpt in chunk.text and chunk.page == item.page
            ),
            None,
        )
        if chunk is None:
            continue
        item.source_sha256, item.chunk_id = source_hash(paper), chunk.chunk_id
        item.source_location = (
            "abstract" if paper.source_kind == "abstract" else f"source chunk {chunk.chunk_id}"
        )
        item.evidence_id = uuid5(
            paper.paper_id, f"prior-art:{item.source_sha256}:{item.verbatim_excerpt}"
        )
        item.provenance = paper.provenance
        item.verification_status = VerificationStatus.PARTIALLY_VERIFIED
        remapped[old.evidence_id] = item.evidence_id
        retained.append(item)
        if item.evidence_id not in evidence_map:
            state.evidence.append(item)
            evidence_map[item.evidence_id] = item
        if chunk.chunk_id not in {entry.chunk_id for entry in state.chunks}:
            state.chunks.append(chunk)
    matches = []
    for match in report.matches:
        paper = canonical.get(match.paper_id)
        if paper:
            match.paper_id = paper.paper_id
        match.evidence_ids = [remapped.get(identity, identity) for identity in match.evidence_ids]
        if (
            not any(item.paper.paper_id == match.paper_id for item in state.candidates)
            or any(
                identity not in evidence_map or evidence_map[identity].paper_id != match.paper_id
                for identity in match.evidence_ids
            )
            or not match.evidence_ids
        ):
            report.complete = False
            report.search_failures.append(
                "Prior-art overlap could not be grounded in the retained source snapshot."
            )
            continue
        matches.append(match)
    report.matches = matches
    report.discovered_evidence = retained
    state.citation_observations.extend(report.citation_observations)
