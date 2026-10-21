from research_council.agents.base import BaseResearchAgent
from research_council.agents.contracts import DirectorOutput, QuestionInput
from research_council.schemas.models import TaskProfile


class ResearchDirector(BaseResearchAgent[QuestionInput, DirectorOutput]):
    name = "ResearchDirector"
    role = "Classify research depth and recommend bounded budget and mode; never fabricate conclusions."
    task_profile = TaskProfile.SEARCH_PLANNING
    allowed_tools = frozenset([])
    input_schema = QuestionInput
    output_schema = DirectorOutput
    prompt_file = "research_director.md"
