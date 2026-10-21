from uuid import uuid4

import pytest
from pydantic import ValidationError

from research_council.core.config import Settings
from research_council.schemas.models import ModelExecution
from research_council.validation.disagreement import ModelPosition, detect_disagreements
from research_council.validation.models import model_benchmark_rows


def test_actual_cross_model_disagreement_remains_visible():
    run_id = uuid4()
    records = [
        ModelExecution(
            run_id=run_id,
            agent_id="independent-review",
            task="ADVERSARIAL_REVIEW",
            provider=provider,
            model=model,
            status="SUCCESS",
            structured_output_valid=True,
        )
        for provider, model in [("mock_A", "A"), ("mock_B", "B")]
    ]
    positions = [
        ModelPosition(
            subject_id="candidate:1",
            task="novelty",
            provider=record.provider,
            model=record.model,
            execution_id=record.execution_id,
            stance=stance,
            position=stance,
        )
        for record, stance in zip(records, ["SUPPORT", "OPPOSE"], strict=True)
    ]
    disagreements = detect_disagreements(positions, records)
    assert len(disagreements) == 1 and disagreements[0].severity == "HIGH"
    assert disagreements[0].resolution_status == "OPEN"
    with pytest.raises(ValidationError):
        disagreements[0].resolution_status = "RESOLVED"
    positions[0].model = "invented-model"
    with pytest.raises(ValueError, match="execution"):
        detect_disagreements(positions, records)


def test_model_comparison_does_not_invent_unmeasured_scores():
    settings = Settings()
    record = ModelExecution(
        run_id=uuid4(),
        agent_id="test",
        task="PAPER_EXTRACTION",
        provider="fake",
        model="offline",
        status="FAILED",
        retry_count=1,
        estimated_cost=0,
    )
    rows = model_benchmark_rows([record], settings)
    row = next(item for item in rows if item["task_profile"] == "PAPER_EXTRACTION")
    assert row["failure_rate"] == 1 and row["retry_count"] == 1
    assert row["accuracy"] is None and row["actual_billed_cost_usd"] is None
    assert len(rows) == 8
