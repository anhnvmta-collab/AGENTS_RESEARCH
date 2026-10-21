from research_council.agents.base import BaseResearchAgent
from research_council.agents.contracts import AnalysisInput, HardwareAssessment
from research_council.schemas.models import TaskProfile


class HardwareArchitect(BaseResearchAgent[AnalysisInput, HardwareAssessment]):
    name = "HardwareArchitect"
    role = "Assess FPGA/RFSoC/SDR/GPU/embedded sample rate, bandwidth, latency, throughput, LUT, FF, DSP, BRAM, DDR/AXI bandwidth, precision, clocks and streaming. Return GREEN/YELLOW/RED; unknown parameters stay unknown, not estimated measurements."
    task_profile = TaskProfile.HARDWARE_REASONING
    allowed_tools = frozenset(["evidence_read"])
    input_schema = AnalysisInput
    output_schema = HardwareAssessment
    prompt_file = "hardware_architect.md"
