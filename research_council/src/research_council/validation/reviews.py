from __future__ import annotations

from typing import Literal
from uuid import UUID

from pydantic import Field

from research_council.core.gates import surviving_candidates
from research_council.core.orchestration.state import WorkflowState
from research_council.schemas.models import ModelExecution, ResearchRun, Schema
from research_council.validation.disagreement import ModelPosition, detect_disagreements
from research_council.validation.models import ModelHumanScore
from research_council.validation.quality import (
    ContradictionLabel,
    EvidenceJudgment,
    sample_real_evidence,
    scientific_quality,
)
from research_council.validation.readiness import ReadinessFacts


class ExpertNoveltyReview(Schema):
    candidate_id: UUID
    revision: int = Field(ge=1)
    verdict: Literal["APPROVE", "REJECT", "UNRESOLVED"]
    note: str = Field(min_length=20)


class HumanReviewBundle(Schema):
    reviewer: str = Field(min_length=2)
    note: str = Field(min_length=20)
    evidence: list[EvidenceJudgment] = Field(default_factory=list)
    contradiction_labels: list[ContradictionLabel] = Field(default_factory=list)
    claim_support_labels: dict[UUID, bool] = Field(default_factory=dict)
    gap_reviews: dict[UUID, Literal["APPROVE", "REJECT", "UNRESOLVED"]] = Field(
        default_factory=dict
    )
    novelty_reviews: list[ExpertNoveltyReview] = Field(default_factory=list)
    model_scores: list[ModelHumanScore] = Field(default_factory=list)
    model_positions: list[ModelPosition] = Field(default_factory=list)
    disagreement_resolutions: dict[UUID, str] = Field(default_factory=dict)


def validate_human_reviews(
    bundle: HumanReviewBundle, state: WorkflowState, executions: list[ModelExecution]
) -> None:
    if bundle.reviewer.casefold() in {"automatic", "model", "fake", "reviewertwo", "noveltyjudge"}:
        raise ValueError("An explicit named human reviewer is required")
    if not set(bundle.gap_reviews).issubset({item.gap_id for item in state.gaps}):
        raise ValueError("Human gap review references absent gaps")
    revisions = {(item.candidate_id, item.revision) for item in state.novelty_candidates}
    if any((item.candidate_id, item.revision) not in revisions for item in bundle.novelty_reviews):
        raise ValueError("Human novelty review references an absent candidate revision")
    scientific_quality(
        [item.paper for item in state.candidates],
        state.evidence,
        state.claims,
        state.conflicts,
        bundle.evidence,
        bundle.contradiction_labels,
        bundle.claim_support_labels,
    )
    detect_disagreements(bundle.model_positions, executions)


def apply_disagreement_resolutions(bundle: HumanReviewBundle, state: WorkflowState) -> None:
    known = {item.disagreement_id: item for item in state.model_disagreements}
    if not set(bundle.disagreement_resolutions).issubset(known):
        raise ValueError("Human resolution references an absent model disagreement")
    if any(len(note.strip()) < 20 for note in bundle.disagreement_resolutions.values()):
        raise ValueError(
            "Human disagreement resolution requires an explanation of at least 20 characters"
        )
    state.model_disagreements = [
        item.__class__.model_validate(
            {
                **item.model_dump(),
                "resolution_status": "RESOLVED",
                "resolved_by": bundle.reviewer,
                "resolution_note": bundle.disagreement_resolutions[item.disagreement_id],
            }
        )
        if item.disagreement_id in bundle.disagreement_resolutions
        else item
        for item in state.model_disagreements
    ]


def readiness_facts(
    run: ResearchRun,
    state: WorkflowState,
    executions: list[ModelExecution],
    bundle: HumanReviewBundle | None = None,
    minimum_evidence: int = 2,
) -> ReadinessFacts:
    real_papers = [item.paper for item in state.candidates if item.paper.provenance != "fixture"]
    actual = [
        item
        for item in executions
        if run.provenance == "live"
        and item.provider in {"openai", "anthropic", "google"}
        and item.status == "SUCCESS"
        and item.structured_output_valid
    ]
    sample_ids = {item.evidence_id for item in sample_real_evidence(real_papers, state.evidence)}
    correct = (
        {
            item.evidence_id
            for item in bundle.evidence
            if item.human_location_correct is True
            and item.human_entailment_correct is True
            and item.human_interpretation_correct is True
        }
        if bundle
        else set()
    )
    verified = {item.paper_id for item in state.identity_audits if item.status == "VERIFIED"} - {
        item.paper_id for item in state.identity_audits if item.conflicts
    }
    survivors = {
        (item.candidate_id, item.revision)
        for item in surviving_candidates(state, executions, minimum_evidence)
        if not item.is_negative_control
    }
    expert = (
        {
            (item.candidate_id, item.revision)
            for item in bundle.novelty_reviews
            if item.verdict == "APPROVE"
        }
        if bundle
        else set()
    )
    models = {
        (item.provider, item.model)
        for item in actual
        if item.agent_id in {"NoveltyGenerator", "ReviewerTwo"}
    }
    return ReadinessFacts(
        successful_live_model_calls=len(actual),
        successful_scholarly_operations=sum(
            item.status == "SUCCESS" and item.adapter in {"crossref", "openalex", "arxiv"}
            for item in state.search_history
        ),
        real_papers=len(real_papers),
        core_papers=len(state.core_paper_ids),
        verified_core_identities=len(verified & set(state.core_paper_ids)),
        real_evidence=len([item for item in state.evidence if item.provenance != "fixture"]),
        correct_human_sampled_evidence=len(sample_ids & correct),
        gaps=len(state.gaps),
        expert_approved_gaps=sum(verdict == "APPROVE" for verdict in bundle.gap_reviews.values())
        if bundle
        else 0,
        automated_survivors=len(survivors),
        independent_review_models=len(models),
        expert_approved_survivors=len(survivors & expert),
        unresolved_high_disagreements=sum(
            item.severity == "HIGH" and item.resolution_status != "RESOLVED"
            for item in state.model_disagreements
        ),
    )
