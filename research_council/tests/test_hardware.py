from uuid import uuid4

import pytest

from research_council.core.hardware import (
    PlatformBudget,
    StreamRequirements,
    estimate_streaming,
    validate_hardware,
)
from research_council.knowledge import InMemoryVectorStore
from research_council.schemas.models import HardwareAssessment


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
