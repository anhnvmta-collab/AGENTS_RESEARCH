from research_council.agents.base import BaseResearchAgent
from research_council.agents.contracts import ExperimentInput, ExperimentPlan
from research_council.schemas.models import TaskProfile


class ExperimentDesigner(BaseResearchAgent[ExperimentInput, ExperimentPlan]):
    name = "ExperimentDesigner"
    role = "Design falsifiable experiments with fair baselines, metrics, datasets, ablations, statistical uncertainty, seeds, reproducibility, real-time and hardware validation. Do not write imagined results."
    task_profile = TaskProfile.HARDWARE_REASONING
    allowed_tools = frozenset(["evidence_read"])
    input_schema = ExperimentInput
    output_schema = ExperimentPlan
    prompt_file = "experiment_designer.md"
