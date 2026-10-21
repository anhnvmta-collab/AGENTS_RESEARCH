from research_council.agents.base import BaseResearchAgent
from research_council.agents.contracts import PaperInput, PaperOutline
from research_council.schemas.models import TaskProfile


class PaperArchitect(BaseResearchAgent[PaperInput, PaperOutline]):
    name = "PaperArchitect"
    role = "Create an IEEE engineering paper roadmap with supported related work, methods, experiments, limitations and reproducibility. Journal ranking is unknown unless sourced; do not promise acceptance."
    task_profile = TaskProfile.SYNTHESIS
    allowed_tools = frozenset(["evidence_read"])
    input_schema = PaperInput
    output_schema = PaperOutline
    prompt_file = "paper_architect.md"
