from research_council.agents.base import BaseResearchAgent
from research_council.agents.contracts import QuestionInput, ResearchPlan
from research_council.schemas.models import TaskProfile


class ResearchPlanner(BaseResearchAgent[QuestionInput, ResearchPlan]):
    name = "ResearchPlanner"
    role = (
        "Create a bounded research plan, inclusion/exclusion criteria and transparent limitations."
    )
    task_profile = TaskProfile.SEARCH_PLANNING
    allowed_tools = frozenset([])
    input_schema = QuestionInput
    output_schema = ResearchPlan
    prompt_file = "research_planner.md"

    async def execute(self, value: QuestionInput) -> ResearchPlan:
        output = await super().execute(value)
        if self.router.settings.science_benchmark:
            from research_council.validation.benchmark import load_benchmark

            output.subquestions = {**output.subquestions, **load_benchmark().subquestions}
        return output
