from __future__ import annotations

from pydantic import Field

from research_council.schemas.models import HardwareAssessment, Schema


class StreamRequirements(Schema):
    sample_rate_hz: float = Field(gt=0)
    channels: int = Field(ge=1)
    bits_per_component: int = Field(ge=1, le=64)
    complex_samples: bool = True
    hops_per_second: float | None = Field(default=None, gt=0)


class PlatformBudget(Schema):
    clock_hz: float = Field(gt=0)
    axi_bits: int = Field(ge=1)
    utilization: float = Field(default=0.8, gt=0, le=1)
    sustained_ddr_bytes_per_second: float | None = Field(default=None, gt=0)


class StreamingEstimate(Schema):
    """Derived traffic lower bounds, not measured implementation performance."""

    input_bits_per_second: float
    minimum_input_bytes_per_second: float
    axi_capacity_bits_per_second: float
    axi_utilization: float
    clock_cycles_per_channel_sample: float
    hop_deadline_seconds: float | None
    bus_feasibility: str
    assumptions: list[str]


def estimate_streaming(
    requirements: StreamRequirements, platform: PlatformBudget
) -> StreamingEstimate:
    bits = (
        requirements.sample_rate_hz
        * requirements.channels
        * requirements.bits_per_component
        * (2 if requirements.complex_samples else 1)
    )
    capacity = platform.clock_hz * platform.axi_bits * platform.utilization
    feasible = bits <= capacity
    if platform.sustained_ddr_bytes_per_second is not None:
        feasible = feasible and bits / 8 <= platform.sustained_ddr_bytes_per_second
    return StreamingEstimate(
        input_bits_per_second=bits,
        minimum_input_bytes_per_second=bits / 8,
        axi_capacity_bits_per_second=capacity,
        axi_utilization=bits / capacity,
        clock_cycles_per_channel_sample=platform.clock_hz / requirements.sample_rate_hz,
        hop_deadline_seconds=1 / requirements.hops_per_second
        if requirements.hops_per_second
        else None,
        bus_feasibility="GREEN" if feasible else "RED",
        assumptions=[
            "DERIVED from explicit input assumptions; not a measured hardware result.",
            "DDR bound counts input traffic only; buffers, reads and intermediates increase traffic.",
            "Bus feasibility does not establish algorithm, timing closure, resource or fixed-point feasibility.",
        ],
    )


def validate_hardware(
    assessment: HardwareAssessment, evidence_ids: set[object], paper_ids: set[object]
) -> HardwareAssessment:
    if not set(assessment.evidence_ids).issubset(evidence_ids) or not set(
        assessment.paper_ids
    ).issubset(paper_ids):
        raise ValueError("Hardware assessment references unknown source artifacts")
    required = {
        "sample_rate_hz",
        "bandwidth_hz",
        "latency_seconds",
        "throughput_samples_per_second",
        "lut",
        "ff",
        "dsp_slices",
        "bram",
        "ddr_bytes_per_second",
        "axi_bits_per_second",
        "fixed_point_bits",
        "clock_hz",
    }
    unknown = [name for name in sorted(required) if assessment.parameters.get(name) is None]
    assessment.unknowns = list(dict.fromkeys(assessment.unknowns + unknown))
    if assessment.feasibility == "GREEN" and (unknown or not assessment.evidence_ids):
        assessment.feasibility = "YELLOW"
        assessment.justification += (
            " Missing sourced implementation parameters prevent a GREEN assessment."
        )
    return assessment
