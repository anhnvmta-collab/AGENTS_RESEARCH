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
        validate_experiment(output, hardware_required=bool(value.hardware))
        allowed = {item.candidate_id: item.revision for item in value.candidates}
        if not set(output.candidate_ids).issubset(allowed):
            raise ValueError("Experiment references unknown candidate")
        output.candidate_ids = list(allowed)
        output.candidate_revisions = allowed
        output.gap_ids = [item.gap_id for item in value.gaps]
        output.claim_ids = [item.claim_id for item in value.claims]
        return output


def validate_experiment(plan: ExperimentPlan, *, hardware_required: bool = False) -> None:
    if not all(
        (
            plan.hypothesis,
            plan.baselines,
            plan.metrics,
            plan.procedures,
            plan.ablations,
            plan.statistical_plan,
            plan.failure_cases,
            plan.acceptance_criteria,
            plan.reproducibility,
        )
    ):
        raise ValueError(
            "Experiment needs a falsifiable hypothesis, baselines, metrics, ablations, statistics, failure cases, acceptance criteria and reproducibility"
        )
    if hardware_required:
        required = ["Simulation", "Synthetic IQ", "Recorded IQ", "SDR", "FPGA/RFSoC"]
        progression = [item.casefold() for item in plan.progression]
        if any(item.casefold() not in progression for item in required):
            raise ValueError(
                "Hardware experiments require staged simulation-to-FPGA/RFSoC progression"
            )
        if [progression.index(item.casefold()) for item in required] != sorted(
            progression.index(item.casefold()) for item in required
        ):
            raise ValueError("Experiment progression stages must be ordered")
