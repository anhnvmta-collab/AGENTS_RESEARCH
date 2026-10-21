from research_council.agents.base import BaseResearchAgent
from research_council.agents.contracts import AnalysisInput, HardwareAssessment
from research_council.core.hardware import validate_hardware
from research_council.schemas.models import TaskProfile


class HardwareArchitect(BaseResearchAgent[AnalysisInput, HardwareAssessment]):
    name = "HardwareArchitect"
    role = "Assess FPGA/RFSoC/SDR/GPU/embedded sample rate, bandwidth, latency, throughput, LUT, FF, DSP, BRAM, DDR/AXI bandwidth, precision, clocks and streaming. Return GREEN/YELLOW/RED; unknown parameters stay unknown, not estimated measurements."
    task_profile = TaskProfile.HARDWARE_REASONING
    allowed_tools = frozenset(["evidence_read"])
    input_schema = AnalysisInput
    output_schema = HardwareAssessment
    prompt_file = "hardware_architect.md"

    async def execute(self, value: AnalysisInput) -> HardwareAssessment:
        output = validate_hardware(
            await super().execute(value),
            {item.evidence_id for item in value.evidence},
            {paper.paper_id for paper in value.papers},
            value.evidence,
        )
        if self.router.settings.science_benchmark:
            from research_council.validation.quality import hardware_parameter_rows

            for row in hardware_parameter_rows([output], value.evidence):
                output.parameter_provenance[str(row["parameter"])] = str(row["provenance"])  # type: ignore[assignment]
                if row["notes"]:
                    output.unknowns.append(str(row["notes"]))
            if output.measurement_status == "MEASURED":
                output.measurement_status = "ESTIMATED"
                if output.feasibility == "GREEN":
                    output.feasibility = "YELLOW"
                output.unknowns.append(
                    "Scientific validation has not ingested independent measurements."
                )
        return output
