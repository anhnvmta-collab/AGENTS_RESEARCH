from __future__ import annotations

import json

from research_council.agents.contracts import ReviewInput, SynthesisInput
from research_council.core.security import sanitize_text
from research_council.schemas.models import Evidence, NoveltyCandidate, Schema, VerificationStatus


def build_context(value: Schema, *, max_chars: int = 150_000) -> str:
    content = value.model_dump(mode="json")
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
        evidence=relevant,
    )


def validate_synthesis_input(value: SynthesisInput) -> None:
    if any(
        item.verification_status != VerificationStatus.VERIFIED for item in value.verified_claims
    ):
        raise ValueError("Final synthesizer may only read verified claims")
    allowed = {item.evidence_id for item in value.evidence}
    if any(not set(item.evidence_ids).issubset(allowed) for item in value.verified_claims):
        raise ValueError("Missing synthesis evidence")
