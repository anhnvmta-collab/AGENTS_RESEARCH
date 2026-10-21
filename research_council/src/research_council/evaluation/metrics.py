from __future__ import annotations

from uuid import UUID

from pydantic import Field

from research_council.core.grounding import grounded_excerpt
from research_council.core.orchestration.state import WorkflowState
from research_council.schemas.models import AgentExecution, ModelExecution, Schema, Score


class GoldLabels(Schema):
    paper_exists: dict[UUID, bool] = Field(default_factory=dict)
    paper_identity_correct: dict[UUID, bool] = Field(default_factory=dict)
    candidate_is_novel: dict[UUID, bool] = Field(default_factory=dict)
    annotated_by: str = ""


class HumanScores(Schema):
    reviewer: str
    research_quality: Score | None = None
    technical_depth: Score | None = None
    novelty_usefulness: Score | None = None
    hardware_feasibility: Score | None = None
    notes: str = ""


class EvaluationReport(Schema):
    metrics: dict[str, float | None]
    denominators: dict[str, int]
    definitions: dict[str, str]
    human_scores: HumanScores | None = None
    limitations: list[str] = Field(default_factory=list)


def ratio(numerator: int, denominator: int) -> float | None:
    return numerator / denominator if denominator else None


def evaluate(
    state: WorkflowState,
    model_executions: list[ModelExecution],
    agent_executions: list[AgentExecution],
    gold: GoldLabels | None = None,
    human: HumanScores | None = None,
) -> EvaluationReport:
    labels = gold or GoldLabels()
    papers = {item.paper.paper_id: item.paper for item in state.candidates}
    evidence = {item.evidence_id: item for item in state.evidence}
    primary = [item for item in state.claims if item.primary]
    references = {identity for claim in primary for identity in claim.source_paper_ids}
    evaluated_refs = references & labels.paper_exists.keys()
    evaluated_identities = papers.keys() & labels.paper_identity_correct.keys()
    complete = sum(
        bool(claim.evidence_ids)
        and all(
            identity in evidence and evidence[identity].paper_id in claim.source_paper_ids
            for identity in claim.evidence_ids
        )
        for claim in primary
    )
    grounded = sum(
        item.paper_id in papers and grounded_excerpt(papers[item.paper_id], item)
        for item in state.evidence
    )
    accepted = {item.candidate_id for item in state.decisions if item.verdict == "SURVIVE"}
    non_novel = {identity for identity, novel in labels.candidate_is_novel.items() if not novel}
    model_count = len(model_executions)
    cost_complete = all(item.estimated_cost is not None for item in model_executions)
    metrics = {
        "citation_precision": ratio(
            sum(labels.paper_exists[identity] for identity in evaluated_refs), len(evaluated_refs)
        ),
        "citation_completeness": ratio(complete, len(primary)),
        "paper_identity_accuracy": ratio(
            sum(labels.paper_identity_correct[identity] for identity in evaluated_identities),
            len(evaluated_identities),
        ),
        "evidence_grounding_rate": ratio(grounded, len(state.evidence)),
        "hallucinated_reference_rate": ratio(
            sum(not labels.paper_exists[identity] for identity in evaluated_refs),
            len(evaluated_refs),
        ),
        "structured_output_success": ratio(
            sum(item.structured_output_valid for item in model_executions), model_count
        ),
        "novelty_false_positive_rate": ratio(len(accepted & non_novel), len(non_novel)),
        "agent_latency_mean_seconds": sum(item.latency for item in agent_executions)
        / len(agent_executions)
        if agent_executions
        else None,
        "cost_per_run_usd": sum(item.estimated_cost or 0 for item in model_executions)
        if cost_complete
        else None,
    }
    denominators = {
        "citation_precision": len(evaluated_refs),
        "citation_completeness": len(primary),
        "paper_identity_accuracy": len(evaluated_identities),
        "evidence_grounding_rate": len(state.evidence),
        "hallucinated_reference_rate": len(evaluated_refs),
        "structured_output_success": model_count,
        "novelty_false_positive_rate": len(non_novel),
        "agent_latency_mean_seconds": len(agent_executions),
    }
    definitions = {
        "citation_precision": "Existing unique primary cited paper IDs / gold-labelled primary cited IDs. Existence does not measure entailment.",
        "citation_completeness": "Primary claims with resolvable evidence-to-paper edges / primary claims. Structural metric, not semantic correctness.",
        "paper_identity_accuracy": "Correct identity annotations / gold-labelled discovered papers.",
        "evidence_grounding_rate": "Evidence excerpts found at the stated source location / evidence objects.",
        "hallucinated_reference_rate": "Nonexistent gold-labelled primary references / gold-labelled primary references.",
        "structured_output_success": "Locally valid model attempts / all model attempts, including retries.",
        "novelty_false_positive_rate": "Accepted gold-labelled non-novel candidates / all labelled non-novel candidates.",
        "agent_latency_mean_seconds": "Mean recorded agent execution duration, including failed executions.",
        "cost_per_run_usd": "Sum of configured-price provider estimates; null if any attempt cost is unknown.",
    }
    return EvaluationReport(
        metrics=metrics,
        denominators=denominators,
        definitions=definitions,
        human_scores=human,
        limitations=[
            "Missing gold annotations and zero denominators produce null, not perfect scores.",
            "Quotation matching does not establish semantic entailment.",
            f"Existence labels cover {len(evaluated_refs)} of {len(references)} primary cited papers.",
            "Fixture metrics validate software behavior only.",
        ],
    )
