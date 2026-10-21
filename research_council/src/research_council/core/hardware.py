from __future__ import annotations

import re

from pydantic import Field

from research_council.schemas.models import Evidence, HardwareAssessment, Schema, VerificationStatus


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
    assessment: HardwareAssessment,
    evidence_ids: set[object],
    paper_ids: set[object],
    evidence_records: list[Evidence] | None = None,
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
    sources = {item.evidence_id: item for item in evidence_records or []}
    for key, identities in assessment.parameter_evidence.items():
        if (
            key not in assessment.parameters
            or not identities
            or not set(identities).issubset(set(assessment.evidence_ids) & evidence_ids)
        ):
            raise ValueError("Hardware parameter has unknown or missing evidence")
    for key in required:
        value = assessment.parameters.get(key)
        if value is not None and (
            not isinstance(value, (int, float)) or isinstance(value, bool) or value < 0
        ):
            raise ValueError("Hardware numeric parameters must be explicit nonnegative numbers")
    supported = all(
        assessment.parameter_evidence.get(key)
        and all(
            identity in sources
            and sources[identity].verification_status == VerificationStatus.VERIFIED
            and numeric_quote_support(float(value), sources[identity].verbatim_excerpt)
            for identity in assessment.parameter_evidence[key]
        )
        for key, value in assessment.parameters.items()
        if key in required and value is not None
    ) and bool(assessment.parameters)
    if assessment.measurement_status == "MEASURED" and not supported:
        assessment.measurement_status = "ESTIMATED" if assessment.parameters else "UNKNOWN"
        assessment.unknowns.append(
            "Measured parameter provenance is incomplete; values are estimates only."
        )
    unknown = [name for name in sorted(required) if assessment.parameters.get(name) is None]
    assessment.unknowns = list(dict.fromkeys(assessment.unknowns + unknown))
    if assessment.feasibility == "GREEN" and (
        unknown or not supported or assessment.measurement_status != "MEASURED"
    ):
        assessment.feasibility = "YELLOW"
        assessment.justification += (
            " Missing sourced implementation parameters prevent a GREEN assessment."
        )
    return assessment


def numeric_quote_support(value: float, quote: str) -> bool:
    """Conservative numeric anchor only; semantic correctness still needs review."""
    for match in re.finditer(
        r"(?<![\w.])([0-9]+(?:\.[0-9]+)?(?:e[+-]?[0-9]+)?)\s*(GHz|MHz|kHz|Hz|ms|us|ns|GB/s|MB/s|kB/s)?",
        quote,
        re.I,
    ):
        scale = {
            "ghz": 1e9,
            "mhz": 1e6,
            "khz": 1e3,
            "ms": 1e-3,
            "us": 1e-6,
            "ns": 1e-9,
            "gb/s": 1e9,
            "mb/s": 1e6,
            "kb/s": 1e3,
        }.get((match[2] or "").casefold(), 1)
        if abs(float(match[1]) * scale - value) <= max(1e-12, abs(value) * 1e-9):
            return True
    return False
