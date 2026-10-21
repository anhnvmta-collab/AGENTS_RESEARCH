from __future__ import annotations

import re
from datetime import UTC, datetime
from enum import StrEnum
from typing import Annotated, Any, Literal, Self
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

Score = Annotated[float, Field(ge=0, le=1)]


def utcnow() -> datetime:
    return datetime.now(UTC)


def normalize_doi(value: str | None) -> str | None:
    if not value or not value.strip():
        return None
    result = re.sub(r"^(?:https?://(?:dx\.)?doi\.org/|doi:\s*)", "", value.strip(), flags=re.I)
    result = result.strip().lower()
    if not re.fullmatch(r"10\.\d{4,9}/\S+", result):
        raise ValueError("Invalid DOI")
    return result


class Schema(BaseModel):
    model_config = ConfigDict(
        extra="forbid", validate_assignment=True, allow_inf_nan=False, revalidate_instances="always"
    )

    @field_validator("*", mode="after")
    @classmethod
    def normalize_timestamps(cls, value: Any) -> Any:
        if isinstance(value, datetime):
            if value.tzinfo is None or value.utcoffset() is None:
                raise ValueError("Timestamps must be timezone-aware")
            return value.astimezone(UTC)
        return value


class Mode(StrEnum):
    QUICK = "quick"
    REVIEW = "review"
    DEEP = "deep"
    NOVELTY = "novelty"
    AUDIT = "audit"


class VerificationStatus(StrEnum):
    VERIFIED = "VERIFIED"
    PARTIALLY_VERIFIED = "PARTIALLY_VERIFIED"
    UNVERIFIED = "UNVERIFIED"
    CONTRADICTED = "CONTRADICTED"


class ClaimType(StrEnum):
    AUTHOR_REPORTED = "AUTHOR_REPORTED"
    DERIVED = "DERIVED"
    AGENT_ANALYSIS = "AGENT_ANALYSIS"
    HYPOTHESIS = "HYPOTHESIS"


class GapType(StrEnum):
    ALGORITHMIC = "ALGORITHMIC"
    PERFORMANCE = "PERFORMANCE"
    COMPUTATIONAL = "COMPUTATIONAL"
    HARDWARE = "HARDWARE"
    DATASET = "DATASET"
    EXPERIMENTAL = "EXPERIMENTAL"
    SYSTEM_INTEGRATION = "SYSTEM_INTEGRATION"
    REAL_TIME = "REAL_TIME"
    THEORETICAL = "THEORETICAL"


class RiskLevel(StrEnum):
    LOW_RISK = "LOW_RISK"
    BALANCED = "BALANCED"
    HIGH_NOVELTY = "HIGH_NOVELTY"
    HIGH_RISK_HIGH_REWARD = "HIGH_RISK_HIGH_REWARD"


class TaskProfile(StrEnum):
    SEARCH_PLANNING = "SEARCH_PLANNING"
    PAPER_EXTRACTION = "PAPER_EXTRACTION"
    MATH_REASONING = "MATH_REASONING"
    HARDWARE_REASONING = "HARDWARE_REASONING"
    SYNTHESIS = "SYNTHESIS"
    NOVELTY_GENERATION = "NOVELTY_GENERATION"
    ADVERSARIAL_REVIEW = "ADVERSARIAL_REVIEW"
    CITATION_VERIFICATION = "CITATION_VERIFICATION"


class ResearchQuestion(Schema):
    topic: str = Field(min_length=3, max_length=4000)
    constraints: list[str] = Field(default_factory=list)
    audit_claim: str | None = None


class ResearchProject(Schema):
    project_id: UUID = Field(default_factory=uuid4)
    title: str
    question: ResearchQuestion
    created_at: datetime = Field(default_factory=utcnow)


class ResearchRun(Schema):
    run_id: UUID = Field(default_factory=uuid4)
    project_id: UUID
    question: ResearchQuestion
    mode: Mode = Mode.REVIEW
    status: Literal[
        "CREATED", "RUNNING", "PAUSED", "FAILED", "COMPLETED", "REJECTED", "BUDGET_EXHAUSTED"
    ] = "CREATED"
    stage: int = Field(default=0, ge=0)
    workflow_version: int = 1
    config_fingerprint: str
    provenance: Literal["offline", "fixture", "live"] = "offline"
    budget_usd: float = Field(default=5, ge=0)
    created_at: datetime = Field(default_factory=utcnow)
    updated_at: datetime = Field(default_factory=utcnow)
    warnings: list[str] = Field(default_factory=list)


class ResearchPerspective(Schema):
    perspective_id: UUID = Field(default_factory=uuid4)
    name: str
    questions: list[str]


class WorkflowEvent(Schema):
    event_id: UUID = Field(default_factory=uuid4)
    run_id: UUID
    stage: str
    event: Literal[
        "RESUMED",
        "STAGE_STARTED",
        "STAGE_COMPLETED",
        "STAGE_FAILED",
        "PAUSED",
        "COMPLETED",
        "AUDIT_COMPLETED",
    ]
    created_at: datetime = Field(default_factory=utcnow)


class ResearchPlan(Schema):
    objective: str = "Evidence is required before drawing conclusions."
    tasks: list[str] = Field(default_factory=list)
    inclusion_criteria: list[str] = Field(default_factory=list)
    exclusion_criteria: list[str] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)
    subquestions: dict[str, ResearchQuestion] = Field(default_factory=dict)


class SearchQuery(Schema):
    query_id: UUID = Field(default_factory=uuid4)
    text: str = Field(min_length=1, max_length=2000)
    strategy: Literal[
        "broad",
        "exact",
        "synonym",
        "algorithm",
        "hardware",
        "application",
        "recent",
        "seminal",
        "targeted",
    ] = "broad"
    adapter: str = "all"
    iteration: int = Field(default=0, ge=0)
    family: str | None = None
    provenance: str | None = None


class PaperMetadata(Schema):
    title: str = Field(min_length=3)
    authors: list[str] = Field(default_factory=list)
    year: int | None = Field(default=None, ge=1500, le=2200)
    venue: str | None = None
    doi: str | None = None
    url: str | None = None
    abstract: str | None = None
    citation_count: int | None = Field(default=None, ge=0)
    quartile: Literal["Q1", "Q2", "Q3", "Q4"] | None = None
    quartile_source: str | None = None
    quartile_year: int | None = Field(default=None, ge=1500, le=2200)
    quartile_category: str | None = None
    quartile_journal: str | None = None
    retracted: bool | None = None
    metadata_source: str
    metadata_verified: bool = False
    retrieved_at: datetime = Field(default_factory=utcnow)

    _doi = field_validator("doi")(normalize_doi)

    @model_validator(mode="after")
    def require_quartile_source(self) -> Self:
        if self.quartile and not all(
            (
                self.quartile_source,
                self.quartile_year,
                self.quartile_category,
                self.quartile_journal or self.venue,
            )
        ):
            raise ValueError("Quartile requires journal, year, category and supporting source")
        return self


class Paper(Schema):
    paper_id: UUID = Field(default_factory=uuid4)
    metadata: PaperMetadata
    provenance: Literal["live", "local", "fixture"] = "live"
    source_text: str | None = Field(default=None, max_length=200_000)
    source_kind: Literal["abstract", "full_text", "local_pdf", "fixture", "metadata"] = "metadata"
    source_path: str | None = None
    page_texts: dict[int, str] = Field(default_factory=dict)

    @model_validator(mode="after")
    def bounded_page_text(self) -> Self:
        if sum(len(text) for text in self.page_texts.values()) > 200_000:
            raise ValueError("Extracted page text exceeds the source limit")
        return self


class PaperChunk(Schema):
    chunk_id: UUID
    paper_id: UUID
    page: int | None = Field(default=None, ge=1)
    start_offset: int = Field(ge=0)
    end_offset: int = Field(gt=0)
    text: str = Field(min_length=1, max_length=8000)
    source_sha256: str


class RankedChunk(Schema):
    chunk: PaperChunk
    score: float = Field(ge=0)


class SearchAttempt(Schema):
    attempt_id: UUID = Field(default_factory=uuid4)
    adapter: str
    operation: str = "search"
    query: SearchQuery | None = None
    seed_paper_id: UUID | None = None
    status: Literal["SUCCESS", "FAILED"]
    result_count: int = Field(default=0, ge=0)
    error_type: str | None = None
    completed_at: datetime = Field(default_factory=utcnow)


class CitationObservation(Schema):
    seed_identifier: str
    target_identifier: str
    direction: str
    adapter: str
    relation_verified: bool = False
    observed_at: datetime = Field(default_factory=utcnow)


class PaperScore(Schema):
    paper_id: UUID
    relevance: Score = 0
    venue_quality: Score = 0
    methodological_value: Score = 0
    novelty_relevance: Score = 0
    hardware_relevance: Score = 0
    citation_influence: Score = 0
    freshness: Score = 0
    rationale: str = ""

    @property
    def total(self) -> float:
        return self.weighted_total()

    def weighted_total(self, weights: dict[str, float] | None = None) -> float:
        selected = weights or {
            "relevance": 0.25,
            "venue_quality": 0.15,
            "novelty_relevance": 0.15,
            "methodological_value": 0.15,
            "hardware_relevance": 0.10,
            "citation_influence": 0.10,
            "freshness": 0.10,
        }
        return float(sum(getattr(self, name) * weight for name, weight in selected.items()))


class PaperCandidate(Schema):
    paper: Paper
    query_ids: list[UUID] = Field(default_factory=list)
    discovery_sources: list[str] = Field(default_factory=list)
    score: PaperScore | None = None
    aggregate_score: Score | None = None


class Evidence(Schema):
    evidence_id: UUID = Field(default_factory=uuid4)
    paper_id: UUID
    claim_id: UUID | None = None
    evidence_type: str
    source_location: str
    page: int | None = Field(default=None, ge=1)
    section: str | None = None
    table: str | None = None
    figure: str | None = None
    verbatim_excerpt: str = Field(min_length=1, max_length=500)
    normalized_statement: str
    agent_interpretation: str = ""
    extraction_agent: str
    provenance: Literal["live", "local", "fixture"] = "live"
    source_sha256: str | None = None
    chunk_id: UUID | None = None
    verification_status: VerificationStatus = VerificationStatus.UNVERIFIED
    confidence: Score = 0
    created_at: datetime = Field(default_factory=utcnow)


class ResearchClaim(Schema):
    claim_id: UUID = Field(default_factory=uuid4)
    statement: str
    claim_type: ClaimType
    source_paper_ids: list[UUID] = Field(default_factory=list)
    evidence_ids: list[UUID] = Field(default_factory=list)
    contradicting_evidence_ids: list[UUID] = Field(default_factory=list)
    resolved_conflict_ids: list[UUID] = Field(default_factory=list)
    verification_status: VerificationStatus = VerificationStatus.UNVERIFIED
    confidence: Score = 0
    reviewer_status: str = "PENDING"
    primary: bool = True
    derivation: str | None = None

    @model_validator(mode="after")
    def validate_verified(self) -> Self:
        if self.verification_status == VerificationStatus.VERIFIED:
            if not self.evidence_ids or not self.source_paper_ids:
                raise ValueError("Verified claims require source papers and evidence")
            if self.claim_type == ClaimType.HYPOTHESIS:
                raise ValueError("Hypotheses cannot be verified")
            if self.contradicting_evidence_ids and not self.resolved_conflict_ids:
                raise ValueError("Unresolved contradictions prevent verification")
        if self.claim_type == ClaimType.DERIVED and not self.derivation:
            raise ValueError("Derived claims require an explicit derivation")
        return self

    @property
    def supporting_evidence_ids(self) -> list[UUID]:
        return list(self.evidence_ids)


class ConflictSeverity(StrEnum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"


class ConflictResolution(StrEnum):
    OPEN = "OPEN"
    RESOLVED = "RESOLVED"
    UNRESOLVED = "UNRESOLVED"


class EvidenceConflict(Schema):
    conflict_id: UUID = Field(default_factory=uuid4)
    claim_id: UUID
    supporting: list[UUID] = Field(default_factory=list)
    contradicting: list[UUID] = Field(min_length=1)
    severity: ConflictSeverity = ConflictSeverity.HIGH
    resolution_status: ConflictResolution = ConflictResolution.OPEN
    resolution_note: str | None = None
    resolved_by: str | None = None
    created_at: datetime = Field(default_factory=utcnow)

    @model_validator(mode="after")
    def documented_resolution(self) -> Self:
        if self.resolution_status == ConflictResolution.RESOLVED and not (
            self.resolution_note and self.resolved_by
        ):
            raise ValueError("Conflict resolution requires a named reviewer and explanation")
        return self


class Gap(Schema):
    gap_id: UUID = Field(default_factory=uuid4)
    gap_type: GapType
    evidence_ids: list[UUID] = Field(min_length=1)
    claim_ids: list[UUID] = Field(default_factory=list)
    limitation: str
    consequence: str
    opportunity: str
    search_scope: str
    known_prior_approaches: list[UUID] = Field(default_factory=list)
    confidence: Score = 0
    potential_counterexample: str | None = None


class NoveltyCandidate(Schema):
    candidate_id: UUID = Field(default_factory=uuid4)
    revision: int = Field(default=1, ge=1)
    gap_ids: list[UUID] = Field(min_length=1)
    evidence_ids: list[UUID] = Field(min_length=1)
    normalized_claim: str
    keywords: list[str] = Field(min_length=1)
    what_is_new: str
    why_it_matters: str
    why_prior_methods_insufficient: str
    proposed_method: str
    validation_plan: str
    risk_level: RiskLevel = RiskLevel.BALANCED
    generation_execution_id: UUID | None = None
    generator_provider: str | None = None
    novelty_claim_id: UUID | None = None
    mathematical_change: str = ""
    implementation_change: str = ""
    falsification_test: str = ""
    revision_summary: str = ""
    change_reason: str = ""
    trigger_prior_art_ids: list[UUID] = Field(default_factory=list)
    is_negative_control: bool = False


class PriorArtMatch(Schema):
    match_id: UUID = Field(default_factory=uuid4)
    candidate_id: UUID
    paper_id: UUID
    similarity: Score
    overlap: str
    invalidates: bool = False
    evidence_ids: list[UUID] = Field(default_factory=list)
    candidate_revision: int = Field(default=1, ge=1)
    overlap_components: dict[str, str] = Field(default_factory=dict)
    severity: ConflictSeverity = ConflictSeverity.LOW


class PriorArtReport(Schema):
    candidate_id: UUID
    revision: int = Field(ge=1)
    complete: bool = False
    queries: list[str] = Field(default_factory=list)
    matches: list[PriorArtMatch] = Field(default_factory=list)
    search_failures: list[str] = Field(default_factory=list)
    discovered_candidates: list[PaperCandidate] = Field(default_factory=list)
    search_attempts: list[SearchAttempt] = Field(default_factory=list)
    model_execution_id: UUID | None = None


class ReviewReason(Schema):
    category: str
    severity: Literal["LOW", "MEDIUM", "HIGH"]
    explanation: str
    evidence_ids: list[UUID] = Field(default_factory=list)
    resolved: bool = False


class ReviewerReport(Schema):
    review_id: UUID = Field(default_factory=uuid4)
    candidate_id: UUID
    revision: int = Field(ge=1)
    complete: bool = False
    verdict: Literal["REJECT", "MAJOR_REVISION", "MINOR_REVISION", "SURVIVES"] = "MAJOR_REVISION"
    reasons: list[ReviewReason] = Field(default_factory=list)
    provider: str | None = None
    model_execution_id: UUID | None = None
    provider_independence: str = "UNKNOWN"


class NoveltyDecision(Schema):
    decision_id: UUID = Field(default_factory=uuid4)
    candidate_id: UUID
    revision: int = Field(ge=1)
    verdict: Literal["REJECT", "REVISE", "SURVIVE", "UNRESOLVED"] = "REVISE"
    novelty_confidence: Score = 0
    closest_prior_art: list[UUID] = Field(default_factory=list)
    required_followup_searches: list[str] = Field(default_factory=list)
    remaining_risks: list[str] = Field(default_factory=list)
    model_execution_id: UUID | None = None
    model_verdict: str | None = None
    policy_overrides: list[str] = Field(default_factory=list)


class HardwareAssessment(Schema):
    assessment_id: UUID = Field(default_factory=uuid4)
    paper_ids: list[UUID] = Field(default_factory=list)
    evidence_ids: list[UUID] = Field(default_factory=list)
    platform: str = "Unspecified"
    feasibility: Literal["GREEN", "YELLOW", "RED"] = "YELLOW"
    justification: str = "Insufficient verified implementation parameters."
    parameters: dict[str, str | float | None] = Field(default_factory=dict)
    unknowns: list[str] = Field(default_factory=list)
    measurement_status: Literal["ESTIMATED", "MEASURED", "UNKNOWN"] = "UNKNOWN"
    parameter_evidence: dict[str, list[UUID]] = Field(default_factory=dict)
    parameter_provenance: dict[
        str, Literal["SOURCE_REPORTED", "DERIVED", "ESTIMATED", "MEASURED"]
    ] = Field(default_factory=dict)
    parameter_assumptions: dict[str, list[str]] = Field(default_factory=dict)
    parameter_derivations: dict[str, str] = Field(default_factory=dict)


class TargetedSearchRequest(Schema):
    request_id: UUID = Field(default_factory=uuid4)
    candidate_id: UUID
    revision: int = Field(ge=1)
    queries: list[str] = Field(min_length=1, max_length=30)
    reasons: list[str] = Field(default_factory=list)
    status: Literal["PENDING", "COMPLETED", "SKIPPED"] = "PENDING"
    created_at: datetime = Field(default_factory=utcnow)


class ExperimentPlan(Schema):
    experiment_id: UUID = Field(default_factory=uuid4)
    objective: str = "Validate a hypothesis; no measured results available."
    candidate_ids: list[UUID] = Field(default_factory=list)
    candidate_revisions: dict[UUID, int] = Field(default_factory=dict)
    gap_ids: list[UUID] = Field(default_factory=list)
    claim_ids: list[UUID] = Field(default_factory=list)
    hypothesis: str = ""
    baselines: list[str] = Field(default_factory=list)
    metrics: list[str] = Field(default_factory=list)
    datasets: list[str] = Field(default_factory=list)
    procedures: list[str] = Field(default_factory=list)
    ablations: list[str] = Field(default_factory=list)
    statistical_plan: str = ""
    reproducibility: list[str] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)
    progression: list[str] = Field(default_factory=list)
    failure_cases: list[str] = Field(default_factory=list)
    acceptance_criteria: list[str] = Field(default_factory=list)


class CitationAudit(Schema):
    audit_id: UUID = Field(default_factory=uuid4)
    paper_id: UUID
    claim_ids: list[UUID] = Field(default_factory=list)
    status: VerificationStatus = VerificationStatus.UNVERIFIED
    checks: dict[str, bool | None] = Field(default_factory=dict)
    notes: list[str] = Field(default_factory=list)
    checked_at: datetime = Field(default_factory=utcnow)
    verifier: str = "automatic"


class AgentExecution(Schema):
    execution_id: UUID = Field(default_factory=uuid4)
    run_id: UUID
    agent_id: str
    task: str
    start_time: datetime = Field(default_factory=utcnow)
    end_time: datetime | None = None
    latency: float = Field(default=0, ge=0)
    status: str = "RUNNING"
    retry_count: int = Field(default=0, ge=0)
    error_type: str | None = None


class ModelExecution(AgentExecution):
    provider: str
    model: str
    input_tokens: int = Field(default=0, ge=0)
    output_tokens: int = Field(default=0, ge=0)
    estimated_cost: float | None = Field(default=None, ge=0)
    structured_output_valid: bool = False
    human_evaluation_score: Score | None = None
    cost_basis: str = "usage"
    routing_note: str | None = None
    prompt_sha256: str | None = None
    context_sha256: str | None = None


class QualityGateResult(Schema):
    gate_id: UUID = Field(default_factory=uuid4)
    gate: Literal[1, 2, 3]
    passed: bool
    reasons: list[str] = Field(default_factory=list)
    checked_ids: list[UUID] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=utcnow)
    candidate_id: UUID | None = None
    candidate_revision: int | None = Field(default=None, ge=1)


class LiteratureRow(Schema):
    paper_id: UUID
    fields: dict[str, str | None] = Field(default_factory=dict)
    evidence_ids: list[UUID] = Field(default_factory=list)


class ResearchKnowledgeMap(Schema):
    topic: str
    subtopics: list[ResearchKnowledgeMap] = Field(default_factory=list)
    paper_ids: list[UUID] = Field(default_factory=list)
    claim_ids: list[UUID] = Field(default_factory=list)
    gap_ids: list[UUID] = Field(default_factory=list)
    coverage_score: Score = 0
    coverage_basis: str = "Observed corpus membership; not universal literature coverage."


ResearchGap = Gap
