from research_council.agents.base import BaseResearchAgent
from research_council.agents.contracts import PaperInput, PaperOutline
from research_council.schemas.models import TaskProfile


class PaperArchitect(BaseResearchAgent[PaperInput, PaperOutline]):
    name = "PaperArchitect"
    role = "Create an IEEE engineering paper roadmap with supported related work, methods, experiments, limitations and reproducibility. Journal ranking is unknown unless sourced; do not promise acceptance."
    task_profile = TaskProfile.SYNTHESIS
    allowed_tools = frozenset(["evidence_read"])
    input_schema = PaperInput
    output_schema = PaperOutline
    prompt_file = "paper_architect.md"

    async def execute(self, value: PaperInput) -> PaperOutline:
        output = await super().execute(value)
        if not set(output.claim_ids).issubset({item.claim_id for item in value.claims}):
            raise ValueError("Paper plan references unknown claims")
        output.experiment_ids = [item.experiment_id for item in value.experiments]
        output.claim_ids = [item.claim_id for item in value.claims]
        return output
