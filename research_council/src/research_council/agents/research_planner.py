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
