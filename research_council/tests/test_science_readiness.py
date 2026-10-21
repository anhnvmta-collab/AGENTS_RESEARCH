from uuid import uuid4

import pytest
from pydantic import ValidationError

from research_council.validation.readiness import (
    ReadinessEvidence,
    ReadinessFacts,
    ScientificReadinessLevel,
    ScientificReadinessRecord,
    advance_readiness,
)


def test_srl_cannot_advance_from_software_without_live_evidence():
    run_id = uuid4()
    record = ScientificReadinessRecord(run_id=run_id)
    proof = ReadinessEvidence(
        run_id=run_id,
        target=ScientificReadinessLevel.SRL_1,
        record_ids=["actual-execution"],
        artifact_path="review.json",
        artifact_sha256="a" * 64,
        reviewer="Researcher",
        statement="Reviewed successful live model and scholarly operations.",
        source_kind="LIVE_SYSTEM",
    )
    with pytest.raises(ValueError, match="prerequisites"):
        advance_readiness(record, proof, ReadinessFacts(), {"actual-execution"}, "a" * 64)
    facts = ReadinessFacts(successful_live_model_calls=1, successful_scholarly_operations=1)
    advanced = advance_readiness(record, proof, facts, {"actual-execution"}, "a" * 64)
    assert record.level == ScientificReadinessLevel.SRL_0
    assert advanced.level.label == "SRL-1" and len(advanced.history) == 1
    with pytest.raises(ValueError, match="digest"):
        advance_readiness(record, proof, facts, {"actual-execution"}, "b" * 64)
    with pytest.raises(ValidationError):
        ScientificReadinessRecord(run_id=run_id, level=ScientificReadinessLevel.SRL_9)


def test_srl_requires_human_sample_and_never_skips_levels():
    facts = ReadinessFacts(
        successful_live_model_calls=1,
        successful_scholarly_operations=1,
        real_papers=4,
        core_papers=4,
        verified_core_identities=4,
        real_evidence=30,
        correct_human_sampled_evidence=19,
    )
    assert facts.supports(ScientificReadinessLevel.SRL_3)
    assert not facts.supports(ScientificReadinessLevel.SRL_4)
    facts.correct_human_sampled_evidence = 20
    assert facts.supports(ScientificReadinessLevel.SRL_4)
    assert not facts.supports(ScientificReadinessLevel.SRL_8)
