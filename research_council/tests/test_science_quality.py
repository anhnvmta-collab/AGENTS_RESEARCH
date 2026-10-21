from uuid import uuid4

import pytest
from test_regressions import human_ready_state

from research_council.schemas.models import EvidenceConflict, HardwareAssessment
from research_council.validation.quality import (
    ContradictionLabel,
    EvidenceJudgment,
    hardware_parameter_rows,
    sample_real_evidence,
    scientific_quality,
)


def test_scientific_metrics_need_independent_labels():
    state = human_ready_state()
    paper = state.candidates[0].paper
    evidence, claim = state.evidence[0], state.claims[0]
    result = scientific_quality([paper], [evidence], [claim], [])
    assert result.metrics["evidence_grounding_rate"].value == 1
    assert result.metrics["evidence_entailment_accuracy"].value is None
    assert result.metrics["unsupported_claim_rate"].value is None
    conflict = EvidenceConflict(claim_id=claim.claim_id, contradicting=[evidence.evidence_id])
    reviewed = scientific_quality(
        [paper],
        [evidence],
        [claim],
        [conflict],
        [
            EvidenceJudgment(
                evidence_id=evidence.evidence_id, reviewer="Expert", human_entailment_correct=False
            )
        ],
        [
            ContradictionLabel(
                claim_id=claim.claim_id, reviewer="Expert", contradiction_present=True
            )
        ],
        {claim.claim_id: False},
    )
    assert reviewed.metrics["evidence_entailment_accuracy"].value == 0
    assert reviewed.metrics["evidence_contradiction_detection_rate"].value == 1
    assert reviewed.metrics["unsupported_claim_rate"].value == 1
    with pytest.raises(ValueError, match="absent"):
        scientific_quality(
            [paper], [evidence], [], [], [EvidenceJudgment(evidence_id=uuid4(), reviewer="Expert")]
        )


def test_random_human_sample_is_reproducible_and_excludes_fixtures():
    state = human_ready_state()
    evidence = [state.evidence[0].model_copy(update={"evidence_id": uuid4()}) for _ in range(30)]
    papers = [state.candidates[0].paper]
    sample = sample_real_evidence(papers, evidence)
    assert len(sample) == 20 and sample == sample_real_evidence(papers, evidence)
    papers[0].provenance = "fixture"
    assert not sample_real_evidence(papers, evidence)


def test_hardware_numbers_never_become_unsourced_measurements():
    state = human_ready_state()
    evidence = state.evidence[0]
    evidence.verbatim_excerpt = "ADC sampling rate 100 MHz."
    assessment = HardwareAssessment(
        parameters={"adc_rate_hz": 100e6, "latency": 0.1},
        parameter_evidence={"adc_rate_hz": [evidence.evidence_id]},
        parameter_provenance={"adc_rate_hz": "SOURCE_REPORTED", "latency": "MEASURED"},
    )
    rows = hardware_parameter_rows([assessment], [evidence])
    assert rows[0]["provenance"] == "SOURCE_REPORTED"
    assert rows[1]["provenance"] == "ESTIMATED"
