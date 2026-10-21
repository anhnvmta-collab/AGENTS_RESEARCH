from research_council.agents.base import BaseResearchAgent
from research_council.agents.contracts import NoveltyInput, NoveltyOutput
from research_council.schemas.models import TaskProfile


class NoveltyGenerator(BaseResearchAgent[NoveltyInput, NoveltyOutput]):
    name = "NoveltyGenerator"
    role = "Propose what is new, why it matters, why prior methods fail, how to solve and test it. Assign risk levels and evidence/gap IDs. Hypotheses are not verified novelty."
    task_profile = TaskProfile.NOVELTY_GENERATION
    allowed_tools = frozenset(["evidence_read", "matrix_read"])
    input_schema = NoveltyInput
    output_schema = NoveltyOutput
    prompt_file = "novelty_generator.md"

    async def execute(self, value: NoveltyInput) -> NoveltyOutput:
        output = await super().execute(value)
        gaps = {item.gap_id for item in value.gaps}
        evidence = {item.evidence_id for item in value.evidence}
        for candidate in output.candidates:
            if not set(candidate.gap_ids).issubset(gaps) or not set(
                candidate.evidence_ids
            ).issubset(evidence):
                raise ValueError("Novelty proposal references unknown artifacts")
        return output
