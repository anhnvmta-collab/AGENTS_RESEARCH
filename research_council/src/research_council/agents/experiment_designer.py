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

    async def execute(self, value: ExperimentInput) -> ExperimentPlan:
        output = await super().execute(value)
        allowed = {item.candidate_id: item.revision for item in value.candidates}
        if not set(output.candidate_ids).issubset(allowed):
            raise ValueError("Experiment references unknown candidate")
        output.candidate_ids = list(allowed)
        output.candidate_revisions = allowed
        output.gap_ids = [item.gap_id for item in value.gaps]
        output.claim_ids = [item.claim_id for item in value.claims]
        return output
