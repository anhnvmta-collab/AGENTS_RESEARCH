from research_council.agents.base import BaseResearchAgent
from research_council.agents.contracts import PerspectivesOutput, PlanInput
from research_council.schemas.models import ResearchPerspective, TaskProfile


class PerspectiveGenerator(BaseResearchAgent[PlanInput, PerspectivesOutput]):
    name = "PerspectiveGenerator"
    role = "Generate theoretical, algorithmic, experimental, hardware, computational, dataset, real-time and application perspectives as structured objects."
    task_profile = TaskProfile.SEARCH_PLANNING
    allowed_tools = frozenset([])
    input_schema = PlanInput
    output_schema = PerspectivesOutput
    prompt_file = "perspective_generator.md"

    async def execute(self, value: PlanInput) -> PerspectivesOutput:
        output = await super().execute(value)
        if self.router.settings.science_benchmark:
            from research_council.validation.benchmark import load_benchmark

            existing = {item.name.casefold() for item in output.perspectives}
            output.perspectives.extend(
                ResearchPerspective(
                    name=name,
                    questions=[question.topic for question in value.plan.subquestions.values()],
                )
                for name in load_benchmark().perspectives
                if name.casefold() not in existing
            )
        return output
