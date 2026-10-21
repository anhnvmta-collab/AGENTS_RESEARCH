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
