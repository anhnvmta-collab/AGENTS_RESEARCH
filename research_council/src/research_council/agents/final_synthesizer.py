from research_council.agents.base import BaseResearchAgent
from research_council.agents.contracts import SynthesisInput, SynthesisOutput
from research_council.core.context import validate_synthesis_input
from research_council.schemas.models import TaskProfile


class FinalSynthesizer(BaseResearchAgent[SynthesisInput, SynthesisOutput]):
    name = "FinalSynthesizer"
    role = "Synthesize only supplied verified claims with traceable evidence IDs. Explicitly report failed gates and insufficient evidence. Do not introduce additional scientific conclusions."
    task_profile = TaskProfile.SYNTHESIS
    allowed_tools = frozenset(["verified_read"])
    input_schema = SynthesisInput
    output_schema = SynthesisOutput
    prompt_file = "final_synthesizer.md"

    async def execute(self, value: SynthesisInput) -> SynthesisOutput:
        validate_synthesis_input(value)
        output = await super().execute(value)
        claims = {item.claim_id: item for item in value.verified_claims}
        if not set(output.claim_ids).issubset(claims):
            raise ValueError("Synthesis introduced an unsupported claim")
        # Model selects/order claims; rendered conclusions retain audited wording.
        output.summary = (
            "\n".join(claims[identity].statement for identity in output.claim_ids)
            or "No verified scientific conclusions are available."
        )
        return output
