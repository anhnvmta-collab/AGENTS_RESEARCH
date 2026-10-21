"""Deterministic observed-corpus map. Scores never imply exhaustive search."""

from __future__ import annotations

from research_council.core.orchestration.state import WorkflowState
from research_council.schemas.models import ResearchKnowledgeMap

TAXONOMY = {
    "Detection": {
        "Energy": ["energy"],
        "Time-frequency": ["spectrogram", "time-frequency", "stft"],
        "Compressed sensing": ["compressed sensing", "compressive", "sparse recovery"],
        "Deep learning": ["neural", "deep learning"],
    },
    "Parameter Estimation": {
        "Hop parameters": ["hop rate", "dwell", "frequency estimation", "parameter estimation"]
    },
    "DOA": {
        "MUSIC": ["music"],
        "ESPRIT": ["esprit"],
        "Sparse DOA": ["sparse doa", "sparse direction"],
        "Correlation": ["correlation", "coherence"],
    },
    "Hardware": {
        "CPU": ["cpu", "processor"],
        "GPU": ["gpu", "cuda"],
        "FPGA": ["fpga", "zynq"],
        "RFSoC": ["rfsoc"],
    },
}


def build_knowledge_map(topic: str, state: WorkflowState) -> ResearchKnowledgeMap:
    papers = {item.paper.paper_id: item.paper for item in state.candidates}
    texts = {
        identity: f"{paper.metadata.title} {paper.metadata.abstract or ''}".casefold()
        for identity, paper in papers.items()
    }
    for row in state.matrix:
        texts[row.paper_id] = (
            texts.get(row.paper_id, "")
            + " "
            + " ".join(value or "" for value in row.fields.values()).casefold()
        )
    grounded = {item.paper_id for item in state.evidence}

    def node(
        name: str, identities: set, children: list[ResearchKnowledgeMap] | None = None
    ) -> ResearchKnowledgeMap:
        claims = [
            claim.claim_id
            for claim in state.claims
            if identities.intersection(claim.source_paper_ids)
        ]
        evidence = {item.evidence_id for item in state.evidence if item.paper_id in identities}
        gaps = [
            gap.gap_id
            for gap in state.gaps
            if evidence.intersection(gap.evidence_ids) or set(claims).intersection(gap.claim_ids)
        ]
        return ResearchKnowledgeMap(
            topic=name,
            paper_ids=sorted(identities, key=str),
            claim_ids=claims,
            gap_ids=gaps,
            coverage_score=len(identities & grounded) / len(identities) if identities else 0,
            coverage_basis="Fraction of this node's observed papers with extracted evidence; not universal coverage.",
            subtopics=children or [],
        )

    branches = []
    for branch, methods in TAXONOMY.items():
        leaves = [
            node(
                method,
                {
                    identity
                    for identity, text in texts.items()
                    if any(word in text for word in keywords)
                },
            )
            for method, keywords in methods.items()
        ]
        identities = {identity for leaf in leaves for identity in leaf.paper_ids}
        branches.append(node(branch, identities, leaves))
    return node(topic, set(papers), branches)
