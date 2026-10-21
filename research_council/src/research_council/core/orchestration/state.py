from __future__ import annotations

from uuid import UUID

from pydantic import Field

from research_council.agents.contracts import PaperOutline, SynthesisOutput
from research_council.core.saturation import SearchSaturationSignal
from research_council.schemas.models import (
    CitationAudit,
    Evidence,
    EvidenceConflict,
    ExperimentPlan,
    Gap,
    HardwareAssessment,
    LiteratureRow,
    NoveltyCandidate,
    NoveltyDecision,
    PaperCandidate,
    PaperChunk,
    PriorArtReport,
    QualityGateResult,
    ResearchClaim,
    ResearchKnowledgeMap,
    ResearchPerspective,
    ResearchPlan,
    ReviewerReport,
    Schema,
    SearchAttempt,
    SearchQuery,
    WorkflowEvent,
)


class WorkflowState(Schema):
    schema_version: int = 1
    plan: ResearchPlan = Field(default_factory=ResearchPlan)
    perspectives: list[ResearchPerspective] = Field(default_factory=list)
    queries: list[SearchQuery] = Field(default_factory=list)
    search_history: list[SearchAttempt] = Field(default_factory=list)
    candidates: list[PaperCandidate] = Field(default_factory=list)
    evidence: list[Evidence] = Field(default_factory=list)
    chunks: list[PaperChunk] = Field(default_factory=list)
    conflicts: list[EvidenceConflict] = Field(default_factory=list)
    claims: list[ResearchClaim] = Field(default_factory=list)
    matrix: list[LiteratureRow] = Field(default_factory=list)
    gaps: list[Gap] = Field(default_factory=list)
    novelty_candidates: list[NoveltyCandidate] = Field(default_factory=list)
    prior_art: list[PriorArtReport] = Field(default_factory=list)
    reviews: list[ReviewerReport] = Field(default_factory=list)
    decisions: list[NoveltyDecision] = Field(default_factory=list)
    hardware: list[HardwareAssessment] = Field(default_factory=list)
    experiments: list[ExperimentPlan] = Field(default_factory=list)
    outline: PaperOutline = Field(default_factory=PaperOutline)
    audits: list[CitationAudit] = Field(default_factory=list)
    gates: list[QualityGateResult] = Field(default_factory=list)
    knowledge_map: ResearchKnowledgeMap | None = None
    synthesis: SynthesisOutput = Field(default_factory=SynthesisOutput)
    novelty_iteration: int = 0
    pending_targeted_queries: list[str] = Field(default_factory=list)
    completed_approvals: list[str] = Field(default_factory=list)
    pending_approval: str | None = None
    limitations: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    events: list[WorkflowEvent] = Field(default_factory=list)
    saturation: list[SearchSaturationSignal] = Field(default_factory=list)
    core_paper_ids: list[UUID] = Field(default_factory=list)
