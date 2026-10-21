from research_council.agents.base import BaseResearchAgent
from research_council.agents.contracts import PerspectivesOutput, PlanInput
from research_council.schemas.models import TaskProfile


class PerspectiveGenerator(BaseResearchAgent[PlanInput, PerspectivesOutput]):
    name = "PerspectiveGenerator"
    role = "Generate theoretical, algorithmic, experimental, hardware, computational, dataset, real-time and application perspectives as structured objects."
    task_profile = TaskProfile.SEARCH_PLANNING
    allowed_tools = frozenset([])
    input_schema = PlanInput
    output_schema = PerspectivesOutput
    prompt_file = "perspective_generator.md"
