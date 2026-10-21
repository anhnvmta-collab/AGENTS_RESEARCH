from __future__ import annotations

import json

from research_council.agents.contracts import ReviewInput, SynthesisInput
from research_council.core.security import sanitize_text
from research_council.schemas.models import Evidence, NoveltyCandidate, Schema, VerificationStatus


def build_context(value: Schema, *, max_chars: int = 150_000, role: str | None = None) -> str:
    content = value.model_dump(mode="json")
    if isinstance(value, ReviewInput):
        for item in content["evidence"]:
            item["agent_interpretation"] = ""
            item["confidence"] = 0
        for paper in content["prior_art_papers"]:
            paper["source_text"], paper["page_texts"] = None, {}
            if paper["metadata"].get("abstract"):
                paper["metadata"]["abstract"] = paper["metadata"]["abstract"][:2500]
    if role not in (None, "DeepReader") and "papers" in content:
        content["papers"] = content["papers"][:30]
        for paper in content["papers"]:
            paper["source_text"], paper["page_texts"] = None, {}
            paper["metadata"]["abstract"] = None
    if role in ("MathDSPAnalyst", "HardwareArchitect", "GapMiner"):
        content["evidence"] = content.get("evidence", [])[:80]
        known = {item["evidence_id"] for item in content["evidence"]}
        content["claims"] = [
            claim
            for claim in content.get("claims", [])
            if set(claim["evidence_ids"]).issubset(known)
        ][:60]
    if role == "NoveltyGenerator":
        content["gaps"] = content.get("gaps", [])[:8]
        used = {identity for gap in content["gaps"] for identity in gap["evidence_ids"]}
        content["evidence"] = [
            item for item in content.get("evidence", []) if item["evidence_id"] in used
        ]
    encoded = json.dumps({"untrusted_task_data": content}, ensure_ascii=False)
    if len(encoded) > max_chars:
        raise ValueError("Context limit exceeded; retrieve a smaller evidence window")
    return sanitize_text(encoded, max_chars)


def independent_review(candidate: NoveltyCandidate, evidence: list[Evidence]) -> ReviewInput:
    relevant = [item for item in evidence if item.evidence_id in candidate.evidence_ids]
    return ReviewInput(
        task="Try to invalidate the normalized contribution claim.",
        candidate_id=candidate.candidate_id,
        revision=candidate.revision,
        normalized_claim=candidate.normalized_claim,
        technical_keywords=candidate.keywords,
        evidence=[
            item.model_copy(update={"agent_interpretation": "", "confidence": 0})
            for item in relevant
        ],
    )


def validate_synthesis_input(value: SynthesisInput) -> None:
    if any(
        item.verification_status != VerificationStatus.VERIFIED for item in value.verified_claims
    ):
        raise ValueError("Final synthesizer may only read verified claims")
    allowed = {item.evidence_id for item in value.evidence}
    if any(not set(item.evidence_ids).issubset(allowed) for item in value.verified_claims):
        raise ValueError("Missing synthesis evidence")
