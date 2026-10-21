from __future__ import annotations

from collections import defaultdict
from uuid import UUID

from research_council.core.config import Settings
from research_council.schemas.models import ModelExecution, Schema, Score


class ModelHumanScore(Schema):
    execution_id: UUID
    reviewer: str
    accuracy: Score | None = None
    technical_depth: Score | None = None
    evidence_fidelity: Score | None = None
    novelty_usefulness: Score | None = None
    reviewer_strength: Score | None = None


def model_benchmark_rows(
    executions: list[ModelExecution],
    settings: Settings,
    human_scores: list[ModelHumanScore] | None = None,
) -> list[dict[str, object]]:
    groups: dict[tuple[str, str, str], list[ModelExecution]] = defaultdict(list)
    for profile, routes in settings.models.items():
        for route in routes:
            groups[profile.value, route.provider, route.model]
    for item in executions:
        groups[item.task, item.provider, item.model].append(item)
    scores = {item.execution_id: item for item in human_scores or []}
    if not set(scores).issubset({item.execution_id for item in executions}):
        raise ValueError("Human model score references an unknown execution")
    result = []
    for (profile_name, provider, model), records in sorted(groups.items()):
        complete = [item for item in records if item.status in {"SUCCESS", "FAILED", "CANCELLED"}]
        row: dict[str, object] = {
            "task_profile": profile_name,
            "provider": provider,
            "model": model,
            "attempts": len(records),
            "completed_attempts": len(complete),
            "latency_mean_seconds": sum(item.latency for item in complete) / len(complete)
            if complete
            else None,
            "input_tokens": sum(item.input_tokens for item in records) if records else None,
            "output_tokens": sum(item.output_tokens for item in records) if records else None,
            "estimated_cost_usd": sum(item.estimated_cost or 0 for item in records)
            if records and all(item.estimated_cost is not None for item in records)
            else None,
            "structured_output_validity": sum(item.structured_output_valid for item in complete)
            / len(complete)
            if complete
            else None,
            "retry_count": sum(item.retry_count > 0 for item in records),
            "failure_rate": sum(item.status != "SUCCESS" for item in complete) / len(complete)
            if complete
            else None,
            "actual_billed_cost_usd": None,
        }
        for name in (
            "accuracy",
            "technical_depth",
            "evidence_fidelity",
            "novelty_usefulness",
            "reviewer_strength",
        ):
            values = [
                getattr(scores[item.execution_id], name)
                for item in records
                if item.execution_id in scores
                and getattr(scores[item.execution_id], name) is not None
            ]
            row[name] = sum(values) / len(values) if values else None
        result.append(row)
    return result
