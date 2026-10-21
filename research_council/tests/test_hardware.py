from uuid import uuid4

import pytest

from research_council.core.hardware import (
    PlatformBudget,
    StreamRequirements,
    estimate_streaming,
    validate_hardware,
)
from research_council.knowledge import InMemoryVectorStore
from research_council.schemas.models import ExperimentPlan, HardwareAssessment, VerificationStatus


def test_derived_streaming_bounds():
    result = estimate_streaming(
        StreamRequirements(
            sample_rate_hz=10e6, channels=4, bits_per_component=16, hops_per_second=1000
        ),
        PlatformBudget(clock_hz=100e6, axi_bits=64),
    )
    assert result.input_bits_per_second == 1.28e9
    assert result.hop_deadline_seconds == 0.001
    assert result.minimum_input_bytes_per_second == 160e6
    assert "DERIVED" in result.assumptions[0]
    red = estimate_streaming(
        StreamRequirements(sample_rate_hz=100e6, channels=8, bits_per_component=16),
        PlatformBudget(clock_hz=100e6, axi_bits=32),
    )
    assert red.bus_feasibility == "RED"


def test_unknown_hardware_cannot_be_green():
    assessment = validate_hardware(HardwareAssessment(feasibility="GREEN"), set(), set())
    assert assessment.feasibility == "YELLOW" and "lut" in assessment.unknowns


def test_optional_vector_store():
    store = InMemoryVectorStore()
    a, b = uuid4(), uuid4()
    store.upsert(a, [1, 0])
    store.upsert(b, [0, 1])
    assert store.search([1, 0])[0] == (a, 1)
    with pytest.raises(ValueError):
        store.search([1])


def test_measured_parameters_need_numeric_source_anchors():
    from test_regressions import human_ready_state

    state = human_ready_state()
    evidence = state.evidence[0]
    evidence.verbatim_excerpt = "Sample rate was 100 MHz."
    evidence.verification_status = VerificationStatus.VERIFIED
    assessment = HardwareAssessment(
        measurement_status="MEASURED",
        parameters={"sample_rate_hz": 100e6},
        paper_ids=[evidence.paper_id],
        evidence_ids=[evidence.evidence_id],
        parameter_evidence={"sample_rate_hz": [evidence.evidence_id]},
    )
    checked = validate_hardware(assessment, {evidence.evidence_id}, {evidence.paper_id}, [evidence])
    assert checked.measurement_status == "MEASURED"
    checked.parameters["sample_rate_hz"] = 999e6
    assert (
        validate_hardware(
            checked, {evidence.evidence_id}, {evidence.paper_id}, [evidence]
        ).measurement_status
        == "ESTIMATED"
    )
    checked.parameter_evidence = {"sample_rate_hz": [uuid4()]}
    with pytest.raises(ValueError, match="evidence"):
        validate_hardware(checked, {evidence.evidence_id}, {evidence.paper_id}, [evidence])


def test_text_values_cannot_satisfy_numeric_hardware_envelope():
    with pytest.raises(ValueError, match="numeric"):
        validate_hardware(
            HardwareAssessment(parameters={"lut": "unknown"}, feasibility="GREEN"), set(), set()
        )


def test_experiment_requires_complete_ordered_proof_plan():
    from test_regressions import human_ready_state

    from research_council.agents.experiment_designer import validate_experiment

    with pytest.raises(ValueError, match="hypothesis"):
        validate_experiment(ExperimentPlan())
    plan = human_ready_state().experiments[0]
    with pytest.raises(ValueError, match="progression"):
        validate_experiment(plan, hardware_required=True)
    plan.progression = ["Simulation", "Synthetic IQ", "Recorded IQ", "SDR", "FPGA/RFSoC"]
    validate_experiment(plan, hardware_required=True)
    plan.progression.reverse()
    with pytest.raises(ValueError, match="ordered"):
        validate_experiment(plan, hardware_required=True)
