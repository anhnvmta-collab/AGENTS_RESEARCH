from __future__ import annotations

from datetime import datetime
from enum import IntEnum
from typing import Literal
from uuid import UUID

from pydantic import Field, model_validator

from research_council.schemas.models import Schema, utcnow


class ScientificReadinessLevel(IntEnum):
    SRL_0 = 0
    SRL_1 = 1
    SRL_2 = 2
    SRL_3 = 3
    SRL_4 = 4
    SRL_5 = 5
    SRL_6 = 6
    SRL_7 = 7
    SRL_8 = 8
    SRL_9 = 9

    @property
    def label(self) -> str:
        return f"SRL-{int(self)}"


SRL_DESCRIPTIONS = {
    0: "Software only",
    1: "Live APIs operational",
    2: "Real literature retrieved",
    3: "Paper identities verified",
    4: "Evidence extraction human-sampled",
    5: "Gap analysis human-reviewed",
    6: "Novelty survives automated adversarial review",
    7: "Novelty survives expert human review",
    8: "Experiment validates contribution",
    9: "Independent replication / publication-grade validation",
}


class ReadinessFacts(Schema):
    successful_live_model_calls: int = Field(default=0, ge=0)
    successful_scholarly_operations: int = Field(default=0, ge=0)
    real_papers: int = Field(default=0, ge=0)
    core_papers: int = Field(default=0, ge=0)
    verified_core_identities: int = Field(default=0, ge=0)
    real_evidence: int = Field(default=0, ge=0)
    correct_human_sampled_evidence: int = Field(default=0, ge=0)
    gaps: int = Field(default=0, ge=0)
    expert_approved_gaps: int = Field(default=0, ge=0)
    automated_survivors: int = Field(default=0, ge=0)
    independent_review_models: int = Field(default=0, ge=0)
    expert_approved_survivors: int = Field(default=0, ge=0)
    unresolved_high_disagreements: int = Field(default=0, ge=0)
    validated_experiments: int = Field(default=0, ge=0)
    independent_replications: int = Field(default=0, ge=0)

    def supports(self, level: ScientificReadinessLevel) -> bool:
        requirements = {
            0: True,
            1: self.successful_live_model_calls > 0 and self.successful_scholarly_operations > 0,
            2: self.real_papers > 0,
            3: self.core_papers > 0 and self.verified_core_identities >= self.core_papers,
            4: self.real_evidence > 0
            and self.correct_human_sampled_evidence >= min(20, self.real_evidence),
            5: self.gaps > 0 and self.expert_approved_gaps >= self.gaps,
            6: self.automated_survivors > 0
            and self.independent_review_models >= 2
            and not self.unresolved_high_disagreements,
            7: self.expert_approved_survivors > 0 and not self.unresolved_high_disagreements,
            8: self.validated_experiments > 0,
            9: self.independent_replications > 0,
        }
        return all(requirements[index] for index in range(int(level) + 1))


class ReadinessEvidence(Schema):
    run_id: UUID
    target: ScientificReadinessLevel
    record_ids: list[str] = Field(min_length=1)
    artifact_path: str
    artifact_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    reviewer: str = Field(min_length=2)
    statement: str = Field(min_length=20)
    source_kind: Literal["LIVE_SYSTEM", "HUMAN_REVIEW", "EXPERIMENT", "INDEPENDENT_REPLICATION"]
    reviewed_at: datetime = Field(default_factory=utcnow)


class ScientificReadinessRecord(Schema):
    run_id: UUID
    level: ScientificReadinessLevel = ScientificReadinessLevel.SRL_0
    history: list[ReadinessEvidence] = Field(default_factory=list)

    @model_validator(mode="after")
    def evidence_chain(self) -> ScientificReadinessRecord:
        if [int(item.target) for item in self.history] != list(range(1, int(self.level) + 1)):
            raise ValueError("Every SRL advancement requires sequential evidence")
        if any(item.run_id != self.run_id for item in self.history):
            raise ValueError("SRL evidence belongs to another run")
        return self


def advance_readiness(
    record: ScientificReadinessRecord,
    proof: ReadinessEvidence,
    facts: ReadinessFacts,
    available_record_ids: set[str],
    actual_artifact_sha256: str,
) -> ScientificReadinessRecord:
    if proof.run_id != record.run_id or int(proof.target) != int(record.level) + 1:
        raise ValueError("SRL advancement must be one level at a time for this run")
    if proof.artifact_sha256 != actual_artifact_sha256 or not set(proof.record_ids).issubset(
        available_record_ids
    ):
        raise ValueError("Readiness artifact digest or record references are unverified")
    if proof.reviewer.casefold() in {"automatic", "model", "fake"}:
        raise ValueError("Readiness advancement requires explicit named operator review")
    required_kind = {
        1: "LIVE_SYSTEM",
        2: "LIVE_SYSTEM",
        3: "LIVE_SYSTEM",
        4: "HUMAN_REVIEW",
        5: "HUMAN_REVIEW",
        6: "LIVE_SYSTEM",
        7: "HUMAN_REVIEW",
        8: "EXPERIMENT",
        9: "INDEPENDENT_REPLICATION",
    }[int(proof.target)]
    if proof.source_kind != required_kind or not facts.supports(proof.target):
        raise ValueError("Scientific readiness prerequisites or evidence kind are not satisfied")
    return ScientificReadinessRecord(
        run_id=record.run_id, level=proof.target, history=[*record.history, proof]
    )
