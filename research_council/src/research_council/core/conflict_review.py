from __future__ import annotations

from typing import Literal
from uuid import UUID, uuid4

from pydantic import Field

from research_council.core.orchestration.engine import RunLease
from research_council.core.orchestration.state import WorkflowState
from research_council.repositories.store import SQLRepository
from research_council.schemas.models import ConflictResolution, Schema, VerificationStatus


class ConflictResolutionRequest(Schema):
    conflict_id: UUID
    reviewer: str = Field(min_length=2, max_length=200)
    note: str = Field(min_length=20, max_length=2000)
    resolution_status: Literal["RESOLVED", "UNRESOLVED"]


def resolve_evidence_conflict(
    repository: SQLRepository, run_id: UUID, request: ConflictResolutionRequest
) -> WorkflowState:
    lease = RunLease(repository, run_id)
    lease.acquire()
    try:
        run = repository.get_run(run_id)
        if run.status != "PAUSED":
            raise ValueError("Conflict review requires a paused run")
        if request.reviewer.casefold() in {"automatic", "model", "fake"}:
            raise ValueError("A named human reviewer is required")
        state = WorkflowState.model_validate(repository.artifacts(run_id).get("state", {}))
        conflict = next(
            (item for item in state.conflicts if item.conflict_id == request.conflict_id), None
        )
        if conflict is None:
            raise ValueError("Unknown evidence conflict")
        claim = next(item for item in state.claims if item.claim_id == conflict.claim_id)
        claim.verification_status = VerificationStatus.UNVERIFIED
        conflict.resolution_note, conflict.resolved_by = request.note, request.reviewer
        conflict.resolution_status = ConflictResolution(request.resolution_status)
        claim.resolved_conflict_ids = [
            identity for identity in claim.resolved_conflict_ids if identity != conflict.conflict_id
        ]
        if conflict.resolution_status == ConflictResolution.RESOLVED:
            claim.resolved_conflict_ids.append(conflict.conflict_id)
        repository.save("approvals", uuid4(), request, run_id)
        repository.checkpoint(run, {"state": state})
        return state
    finally:
        lease.release()
