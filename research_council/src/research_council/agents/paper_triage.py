from research_council.agents.base import BaseResearchAgent
from research_council.agents.contracts import ScoresOutput, TriageInput
from research_council.schemas.models import TaskProfile


class PaperTriage(BaseResearchAgent[TriageInput, ScoresOutput]):
    name = "PaperTriage"
    role = "Score relevance, venue quality, methodology, novelty relevance, hardware relevance, citation influence and freshness separately. Citation counts alone are insufficient."
    task_profile = TaskProfile.PAPER_EXTRACTION
    allowed_tools = frozenset([])
    input_schema = TriageInput
    output_schema = ScoresOutput
    prompt_file = "paper_triage.md"
