from research_council.agents.base import BaseResearchAgent
from research_council.agents.contracts import AnalysisInput, MathOutput
from research_council.schemas.models import TaskProfile


class MathDSPAnalyst(BaseResearchAgent[AnalysisInput, MathOutput]):
    name = "MathDSPAnalyst"
    role = "Analyze only sourced equations, models, optimization, time/memory complexity, numerical stability, parallelization and fixed-point suitability. New derivations must be DERIVED with premises and explicit derivation, never invented source equations."
    task_profile = TaskProfile.MATH_REASONING
    allowed_tools = frozenset(["evidence_read"])
    input_schema = AnalysisInput
    output_schema = MathOutput
    prompt_file = "math_dsp_analyst.md"
