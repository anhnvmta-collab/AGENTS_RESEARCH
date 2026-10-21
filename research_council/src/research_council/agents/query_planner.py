from research_council.agents.base import BaseResearchAgent
from research_council.agents.contracts import PlanInput, QueriesOutput
from research_council.schemas.models import TaskProfile
from research_council.tools.query import QueryExpander


class QueryPlanner(BaseResearchAgent[PlanInput, QueriesOutput]):
    name = "QueryPlanner"
    role = "Generate broad, exact terminology, synonym, algorithm, hardware, application, recent and seminal search strategies."
    task_profile = TaskProfile.SEARCH_PLANNING
    allowed_tools = frozenset([])
    input_schema = PlanInput
    output_schema = QueriesOutput
    prompt_file = "query_planner.md"

    async def execute(self, value: PlanInput) -> QueriesOutput:
        output = await super().execute(value)
        expanded = QueryExpander().expand(value.question.topic)
        unique_queries = {(query.text, query.strategy): query for query in output.queries}
        for query in expanded:
            unique_queries.setdefault((query.text, query.strategy), query)
        output.queries = list(unique_queries.values())[: self.router.settings.research.max_queries]
        return output
