from research_council.agents.base import BaseResearchAgent
from research_council.agents.contracts import SynthesisInput, SynthesisOutput
from research_council.schemas.models import TaskProfile


class FinalSynthesizer(BaseResearchAgent[SynthesisInput, SynthesisOutput]):
    name = "FinalSynthesizer"
    role = "Synthesize only supplied verified claims with traceable evidence IDs. Explicitly report failed gates and insufficient evidence. Do not introduce additional scientific conclusions."
    task_profile = TaskProfile.SYNTHESIS
    allowed_tools = frozenset(["verified_read"])
    input_schema = SynthesisInput
    output_schema = SynthesisOutput
    prompt_file = "final_synthesizer.md"
