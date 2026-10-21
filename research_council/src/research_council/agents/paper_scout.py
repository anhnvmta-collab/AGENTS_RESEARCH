from research_council.agents.base import BaseResearchAgent
from research_council.agents.contracts import CandidatesOutput, SearchInput
from research_council.schemas.models import TaskProfile


class PaperScout(BaseResearchAgent[SearchInput, CandidatesOutput]):
    name = "PaperScout"
    role = "Discover candidates through compliant metadata adapters; preserve query/source provenance; do not scrape restricted sites."
    task_profile = TaskProfile.SEARCH_PLANNING
    allowed_tools = frozenset(["search"])
    input_schema = SearchInput
    output_schema = CandidatesOutput
    prompt_file = "paper_scout.md"
