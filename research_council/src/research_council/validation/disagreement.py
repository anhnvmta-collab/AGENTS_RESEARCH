from __future__ import annotations

from itertools import combinations
from typing import TYPE_CHECKING, Literal
from uuid import UUID, uuid4

from pydantic import Field, model_validator

from research_council.schemas.models import ModelExecution, NoveltyDecision, ReviewerReport, Schema

if TYPE_CHECKING:
    from research_council.core.orchestration.state import WorkflowState


class ModelPosition(Schema):
    subject_id: str
    task: str
    provider: str
    model: str
    execution_id: UUID
    stance: Literal["SUPPORT", "OPPOSE", "UNCERTAIN"]
    position: str


class ModelDisagreement(Schema):
    disagreement_id: UUID = Field(default_factory=uuid4)
    subject_id: str
    task: str
    model_A: str
    model_B: str
    provider_A: str
    provider_B: str
    execution_A: UUID
    execution_B: UUID
    position_A: str
    position_B: str
    severity: Literal["LOW", "MEDIUM", "HIGH"]
    resolution_status: Literal["OPEN", "RESOLVED", "UNRESOLVED"] = "OPEN"
    resolved_by: str | None = None
    resolution_note: str | None = None

    @model_validator(mode="after")
    def documented_resolution(self) -> ModelDisagreement:
        if self.resolution_status == "RESOLVED" and not (self.resolved_by and self.resolution_note):
            raise ValueError(
                "Model disagreement resolution requires a named reviewer and explanation"
            )
        return self


def detect_disagreements(
    positions: list[ModelPosition], executions: list[ModelExecution]
) -> list[ModelDisagreement]:
    actual = {item.execution_id: item for item in executions}
    for position in positions:
        record = actual.get(position.execution_id)
        if (
            not record
            or record.status != "SUCCESS"
            or not record.structured_output_valid
            or (record.provider, record.model) != (position.provider, position.model)
        ):
            raise ValueError("Model position does not match a successful actual execution")
    result = []
    for left, right in combinations(positions, 2):
        if (
            (left.subject_id, left.task) != (right.subject_id, right.task)
            or (left.provider, left.model) == (right.provider, right.model)
            or left.execution_id == right.execution_id
            or left.stance == right.stance
        ):
            continue
        result.append(
            ModelDisagreement(
                subject_id=left.subject_id,
                task=left.task,
                model_A=left.model,
                model_B=right.model,
                provider_A=left.provider,
                provider_B=right.provider,
                execution_A=left.execution_id,
                execution_B=right.execution_id,
                position_A=left.position,
                position_B=right.position,
                severity="HIGH"
                if {left.stance, right.stance} == {"SUPPORT", "OPPOSE"}
                else "MEDIUM",
            )
        )
    return result


def novelty_disagreements(
    state: WorkflowState, executions: list[ModelExecution]
) -> list[ModelDisagreement]:
    actual = {item.execution_id: item for item in executions if item.provider != "fake"}
    positions = []
    reports: list[ReviewerReport | NoveltyDecision] = [*state.reviews, *state.decisions]
    for report in reports:
        record = actual.get(report.model_execution_id) if report.model_execution_id else None
        if not record or record.status != "SUCCESS":
            continue
        stance: Literal["SUPPORT", "OPPOSE", "UNCERTAIN"] = (
            "SUPPORT"
            if report.verdict in {"SURVIVE", "SURVIVES"}
            else "OPPOSE"
            if report.verdict == "REJECT"
            else "UNCERTAIN"
        )
        positions.append(
            ModelPosition(
                subject_id=f"{report.candidate_id}:{report.revision}",
                task="novelty_survival",
                provider=record.provider,
                model=record.model,
                execution_id=record.execution_id,
                stance=stance,
                position=report.verdict,
            )
        )
    return detect_disagreements(positions, executions)
