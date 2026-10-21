from research_council.agents.base import BaseResearchAgent
from research_council.agents.contracts import ReadingInput, ReadingOutput
from research_council.schemas.models import TaskProfile


class DeepReader(BaseResearchAgent[ReadingInput, ReadingOutput]):
    name = "DeepReader"
    role = "Extract problem, motivation, assumptions, signal model, mathematical formulation, algorithm, dataset, hardware, sampling parameters, bandwidth, baselines, metrics, results, complexity, author limitations, inferred limitations, real-time capability, implementation and reproducibility. Every extraction needs short exact source evidence and location. Do not mark scientific entailment verified."
    task_profile = TaskProfile.PAPER_EXTRACTION
    allowed_tools = frozenset(["paper_read"])
    input_schema = ReadingInput
    output_schema = ReadingOutput
    prompt_file = "deep_reader.md"
