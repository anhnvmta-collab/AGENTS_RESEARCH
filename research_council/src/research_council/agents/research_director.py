from uuid import UUID

from research_council.agents.base import BaseResearchAgent
from research_council.agents.contracts import DirectorOutput, QuestionInput
from research_council.schemas.models import Mode, ResearchQuestion, ResearchRun, TaskProfile


class ResearchDirector(BaseResearchAgent[QuestionInput, DirectorOutput]):
    name = "ResearchDirector"
    role = "Classify research depth and recommend bounded budget and mode; never fabricate conclusions."
    task_profile = TaskProfile.SEARCH_PLANNING
    allowed_tools = frozenset([])
    input_schema = QuestionInput
    output_schema = DirectorOutput
    prompt_file = "research_director.md"

    @staticmethod
    def create_research_run(
        project_id: UUID,
        question: ResearchQuestion,
        mode: Mode,
        config_fingerprint: str,
        budget_usd: float,
        provenance: str,
    ) -> ResearchRun:
        return ResearchRun.model_validate(
            {
                "project_id": project_id,
                "question": question,
                "mode": mode,
                "config_fingerprint": config_fingerprint,
                "budget_usd": budget_usd,
                "provenance": provenance,
            }
        )
