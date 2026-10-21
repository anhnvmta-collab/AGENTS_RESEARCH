from research_council.agents.base import BaseResearchAgent
from research_council.agents.contracts import GapInput, GapsOutput
from research_council.schemas.models import TaskProfile


class GapMiner(BaseResearchAgent[GapInput, GapsOutput]):
    name = "GapMiner"
    role = "For each gap link existing evidence to limitation, consequence and opportunity. Scope absence claims to searched literature. Never say no one has studied a topic."
    task_profile = TaskProfile.NOVELTY_GENERATION
    allowed_tools = frozenset(["evidence_read", "matrix_read"])
    input_schema = GapInput
    output_schema = GapsOutput
    prompt_file = "gap_miner.md"

    async def execute(self, value: GapInput) -> GapsOutput:
        output = await super().execute(value)
        evidence = {item.evidence_id for item in value.evidence}
        claims = {item.claim_id for item in value.claims}
        for gap in output.gaps:
            if not set(gap.evidence_ids).issubset(evidence) or not set(gap.claim_ids).issubset(
                claims
            ):
                raise ValueError("Gap references unknown evidence/claims")
            if any(
                phrase in gap.opportunity.lower()
                for phrase in ("no one has", "nobody has", "never been studied")
            ):
                raise ValueError("Unbounded absence claim")
            gap.search_scope = value.search_scope
            if self.router.settings.science_benchmark:
                if not gap.potential_counterexample:
                    raise ValueError("Scientific gaps require an explicit potential counterexample")
                if not set(gap.known_prior_approaches).issubset(
                    {paper.paper_id for paper in value.papers}
                ):
                    raise ValueError("Gap references an unknown prior approach")
                for text in (gap.limitation, gap.consequence, gap.opportunity):
                    if any(
                        phrase in text.casefold()
                        for phrase in ("no one has", "nobody has", "never been studied")
                    ):
                        raise ValueError("Unbounded scientific absence claim")
        return output
