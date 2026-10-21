from __future__ import annotations

from typing import Literal
from uuid import UUID, uuid4

from pydantic import Field

from research_council.core.gates import PublicationReadinessGate
from research_council.core.integrity import unresolved_conflict
from research_council.core.orchestration.engine import RunLease
from research_council.core.orchestration.state import WorkflowState
from research_council.repositories.store import SQLRepository
from research_council.schemas.models import CitationAudit, Mode, Schema, VerificationStatus, utcnow


class ScientificAttestation(Schema):
    claim_id: UUID
    reviewer: str = Field(min_length=2, max_length=200)
    note: str = Field(min_length=20, max_length=2000)
    source_identity_checked: Literal[True]
    source_locations_checked: Literal[True]
    scientific_entailment_checked: Literal[True]
    retraction_status_checked: Literal[True]


def attest_claim(
    repository: SQLRepository, run_id: UUID, attestation: ScientificAttestation
) -> WorkflowState:
    """Record explicit human scientific review, separately from workflow permission."""
    lease = RunLease(repository, run_id)
    lease.acquire()
    try:
        run = repository.get_run(run_id)
        state = WorkflowState.model_validate(repository.artifacts(run_id).get("state", {}))
        if run.status != "PAUSED" or state.pending_approval != "before_final_report":
            raise ValueError("Scientific attestation requires the before_final_report pause point")
        claim = next((item for item in state.claims if item.claim_id == attestation.claim_id), None)
        if (
            claim is None
            or not claim.evidence_ids
            or claim.contradicting_evidence_ids
            or claim.claim_type == "HYPOTHESIS"
        ):
            raise ValueError("Claim cannot be attested without resolved source evidence")
        papers = {item.paper.paper_id: item.paper for item in state.candidates}
        if unresolved_conflict(claim, state.conflicts) or any(
            audit.status == VerificationStatus.CONTRADICTED
            and (claim.claim_id in audit.claim_ids or audit.paper_id in claim.source_paper_ids)
            for audit in state.audits
        ):
            raise ValueError("Unresolved citation/evidence conflict blocks scientific attestation")
        if any(
            identity not in papers
            or papers[identity].provenance == "fixture"
            or papers[identity].metadata.retracted is True
            for identity in claim.source_paper_ids
        ):
            raise ValueError("Synthetic, retracted or missing publications cannot be attested")
        for item in state.evidence:
            if item.evidence_id in claim.evidence_ids:
                item.verification_status = VerificationStatus.VERIFIED
        claim.verification_status = VerificationStatus.VERIFIED
        claim.reviewer_status = f"HUMAN:{attestation.reviewer}"
        for paper_id in claim.source_paper_ids:
            state.audits.append(
                CitationAudit(
                    paper_id=paper_id,
                    claim_ids=[claim.claim_id],
                    status=VerificationStatus.VERIFIED,
                    verifier=attestation.reviewer,
                    checks={
                        "existence": True,
                        "identity": True,
                        "source_location": True,
                        "scientific_entailment": True,
                        "not_retracted": True,
                    },
                    notes=[
                        "Explicit human scientific attestation",
                        attestation.note,
                        utcnow().isoformat(),
                    ],
                )
            )
        state.gates = [item for item in state.gates if item.gate != 3]
        gate = PublicationReadinessGate().evaluate(
            list(papers.values()),
            state.claims,
            state.evidence,
            state.audits,
            state.experiments,
            state.limitations,
            conflicts=state.conflicts,
            outline=state.outline,
            novelty_candidates=[
                item
                for item in state.novelty_candidates
                if any(
                    decision.candidate_id == item.candidate_id
                    and decision.revision == item.revision
                    and decision.verdict == "SURVIVE"
                    for decision in state.decisions
                )
            ],
        )
        if run.mode in (Mode.NOVELTY, Mode.AUDIT) and not any(
            item.gate == 2 and item.passed for item in state.gates
        ):
            gate.passed = False
            gate.reasons.append("Novelty survival is still required.")
        state.gates.append(gate)
        repository.save("approvals", uuid4(), attestation, run_id)
        repository.checkpoint(run, {"state": state})
        return state
    finally:
        lease.release()
