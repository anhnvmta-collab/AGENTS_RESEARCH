from research_council.agents.base import BaseResearchAgent
from research_council.agents.contracts import AuditInput, AuditsOutput
from research_council.schemas.models import TaskProfile


class CitationAuditor(BaseResearchAgent[AuditInput, AuditsOutput]):
    name = "CitationAuditor"
    role = "Audit existence, title/authors/year/venue/DOI, claim consistency, locations, quartile and retractions where supported. Never equate metadata verification with scientific entailment."
    task_profile = TaskProfile.CITATION_VERIFICATION
    allowed_tools = frozenset(["metadata_verify", "evidence_read"])
    input_schema = AuditInput
    output_schema = AuditsOutput
    prompt_file = "citation_auditor.md"

    async def execute(self, value: AuditInput) -> AuditsOutput:
        return AuditsOutput.model_validate(await self.invoke_tool("metadata_verify", value))
