from __future__ import annotations

from uuid import UUID

from pydantic import Field

from research_council.schemas.models import (
    CitationAudit,
    Evidence,
    ExperimentPlan,
    Gap,
    HardwareAssessment,
    LiteratureRow,
    Mode,
    NoveltyCandidate,
    NoveltyDecision,
    Paper,
    PaperCandidate,
    PaperScore,
    PriorArtReport,
    QualityGateResult,
    ResearchClaim,
    ResearchPerspective,
    ResearchPlan,
    ResearchQuestion,
    ReviewerReport,
    Schema,
    SearchAttempt,
    SearchQuery,
)


class AgentInput(Schema):
    task: str


class QuestionInput(AgentInput):
    question: ResearchQuestion
    mode: Mode = Mode.REVIEW


class DirectorOutput(Schema):
    recommended_mode: Mode = Mode.REVIEW
    rationale: str = "Requested mode is controlled by the workflow."
    suggested_budget_usd: float = Field(default=5, ge=0)


class PlanInput(QuestionInput):
    plan: ResearchPlan


class PerspectivesOutput(Schema):
    perspectives: list[ResearchPerspective] = Field(default_factory=list)


class QueriesOutput(Schema):
    queries: list[SearchQuery] = Field(default_factory=list)


class SearchInput(AgentInput):
    queries: list[SearchQuery] = Field(default_factory=list)
    seed_papers: list[Paper] = Field(default_factory=list)
    local_paths: list[str] = Field(default_factory=list)
    direction: str = "related"


class CandidatesOutput(Schema):
    candidates: list[PaperCandidate] = Field(default_factory=list)
    failures: list[str] = Field(default_factory=list)
    attempts: list[SearchAttempt] = Field(default_factory=list)


class TriageInput(QuestionInput):
    candidates: list[PaperCandidate]


class ScoresOutput(Schema):
    scores: list[PaperScore] = Field(default_factory=list)


class ReadingInput(AgentInput):
    paper: Paper


class Extraction(Schema):
    field: str
    value: str
    evidence_ids: list[UUID] = Field(min_length=1)


class ReadingOutput(Schema):
    extractions: list[Extraction] = Field(default_factory=list)
    evidence: list[Evidence] = Field(default_factory=list)
    claims: list[ResearchClaim] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)


class AnalysisInput(QuestionInput):
    papers: list[Paper] = Field(default_factory=list)
    evidence: list[Evidence] = Field(default_factory=list)
    claims: list[ResearchClaim] = Field(default_factory=list)


class MathOutput(Schema):
    claims: list[ResearchClaim] = Field(default_factory=list)
    numerical_risks: list[str] = Field(default_factory=list)
    unknowns: list[str] = Field(default_factory=list)


class GapInput(AnalysisInput):
    matrix: list[LiteratureRow] = Field(default_factory=list)
    search_scope: str = "Only the logged searched corpus."


class GapsOutput(Schema):
    gaps: list[Gap] = Field(default_factory=list)


class NoveltyInput(QuestionInput):
    gaps: list[Gap]
    evidence: list[Evidence]
    previous_candidates: list[NoveltyCandidate] = Field(default_factory=list)
    required_changes: list[str] = Field(default_factory=list)


class NoveltyOutput(Schema):
    candidates: list[NoveltyCandidate] = Field(default_factory=list)


class ReviewInput(AgentInput):
    """Allowlist projection: no generator persuasion or hidden reasoning field exists."""

    candidate_id: UUID
    revision: int
    normalized_claim: str
    technical_keywords: list[str]
    evidence: list[Evidence] = Field(default_factory=list)
    prior_art_papers: list[Paper] = Field(default_factory=list)


class JudgmentInput(AgentInput):
    candidate: NoveltyCandidate
    evidence: list[Evidence]
    prior_art: PriorArtReport
    review: ReviewerReport


class ExperimentInput(AnalysisInput):
    gaps: list[Gap] = Field(default_factory=list)
    candidates: list[NoveltyCandidate] = Field(default_factory=list)
    hardware: list[HardwareAssessment] = Field(default_factory=list)


class PaperInput(AgentInput):
    experiments: list[ExperimentPlan]
    claims: list[ResearchClaim]
    limitations: list[str]


class PaperOutline(Schema):
    title: str = "Research roadmap — evidence acquisition required"
    sections: dict[str, list[str]] = Field(default_factory=dict)
    limitations: list[str] = Field(default_factory=list)


class AuditInput(AgentInput):
    papers: list[Paper]
    claims: list[ResearchClaim]
    evidence: list[Evidence]


class AuditsOutput(Schema):
    audits: list[CitationAudit] = Field(default_factory=list)


class SynthesisInput(AgentInput):
    verified_claims: list[ResearchClaim]
    evidence: list[Evidence]
    audits: list[CitationAudit]
    gates: list[QualityGateResult]
    limitations: list[str]


class SynthesisOutput(Schema):
    summary: str = "No verified scientific conclusions are available."
    claim_ids: list[UUID] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)


# Exported role output types are explicit even where a domain object is the contract.
__all__ = ["NoveltyDecision", "ReviewerReport", "PriorArtReport"]
