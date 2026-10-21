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
        if self.router.settings.science_benchmark and output.candidates:
            expected = {"LOW_RISK", "BALANCED", "HIGH_NOVELTY", "HIGH_RISK_HIGH_REWARD"}
            if not expected.issubset({item.risk_level.value for item in output.candidates}):
                raise ValueError(
                    "Scientific candidate set must cover all four contribution risk classes"
                )
        for candidate in output.candidates:
            if not set(candidate.gap_ids).issubset(gaps) or not set(
                candidate.evidence_ids
            ).issubset(evidence):
                raise ValueError("Novelty proposal references unknown artifacts")
            if self.router.settings.science_benchmark:
                if not (
                    candidate.mathematical_change
                    and candidate.implementation_change
                    and candidate.falsification_test
                ):
                    raise ValueError(
                        "Scientific candidates require mathematical/implementation changes and falsification"
                    )
                if not set(candidate.trigger_prior_art_ids).issubset(value.prior_art_ids):
                    raise ValueError("Candidate revision cites unknown triggering prior art")
            execution = self.router.last_success.get(self.name)
            if execution:
                candidate.generator_provider = execution.provider
                candidate.generation_execution_id = execution.execution_id
        return output
