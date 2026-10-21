from research_council.agents.base import BaseResearchAgent
from research_council.agents.contracts import CandidatesOutput, SearchInput
from research_council.schemas.models import TaskProfile


class CitationScout(BaseResearchAgent[SearchInput, CandidatesOutput]):
    name = "CitationScout"
    role = "Explore backward, forward, author-chain and related papers from explicit seeds; retain provenance."
    task_profile = TaskProfile.SEARCH_PLANNING
    allowed_tools = frozenset(["citation_search"])
    input_schema = SearchInput
    output_schema = CandidatesOutput
    prompt_file = "citation_scout.md"

    async def execute(self, value: SearchInput) -> CandidatesOutput:
        return CandidatesOutput.model_validate(await self.invoke_tool("citation_search", value))
