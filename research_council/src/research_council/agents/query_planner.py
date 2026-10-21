from research_council.agents.base import BaseResearchAgent
from research_council.agents.contracts import PlanInput, QueriesOutput
from research_council.schemas.models import TaskProfile


class QueryPlanner(BaseResearchAgent[PlanInput, QueriesOutput]):
    name = "QueryPlanner"
    role = "Generate broad, exact terminology, synonym, algorithm, hardware, application, recent and seminal search strategies."
    task_profile = TaskProfile.SEARCH_PLANNING
    allowed_tools = frozenset([])
    input_schema = PlanInput
    output_schema = QueriesOutput
    prompt_file = "query_planner.md"
