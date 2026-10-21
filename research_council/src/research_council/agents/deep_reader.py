from research_council.agents.base import BaseResearchAgent
from research_council.agents.contracts import ReadingInput, ReadingOutput
from research_council.core.grounding import validate_reading
from research_council.knowledge.retrieval import (
    LexicalEvidenceRetriever,
    LocatedChunker,
    source_hash,
)
from research_council.schemas.models import TaskProfile


class DeepReader(BaseResearchAgent[ReadingInput, ReadingOutput]):
    name = "DeepReader"
    role = "Extract problem, motivation, assumptions, signal model, mathematical formulation, algorithm, dataset, hardware, sampling parameters, bandwidth, baselines, metrics, results, complexity, author limitations, inferred limitations, real-time capability, implementation and reproducibility. Every extraction needs short exact source evidence and location. Do not mark scientific entailment verified."
    task_profile = TaskProfile.PAPER_EXTRACTION
    allowed_tools = frozenset(["paper_read"])
    input_schema = ReadingInput
    output_schema = ReadingOutput
    prompt_file = "deep_reader.md"

    async def execute(self, value: ReadingInput) -> ReadingOutput:
        bounded = value.model_copy(deep=True)
        chunks = value.chunks or LocatedChunker().chunk(value.paper)
        bounded.chunks = [
            item.chunk for item in LexicalEvidenceRetriever().rank(value.task, chunks)
        ]
        bounded.paper.source_text, bounded.paper.page_texts = None, {}
        bounded.paper.metadata.abstract = None
        output = validate_reading(value.paper, await super().execute(bounded))
        for evidence in output.evidence:
            matching = [
                chunk
                for chunk in bounded.chunks
                if " ".join(evidence.verbatim_excerpt.split()) in " ".join(chunk.text.split())
                and (evidence.page is None or evidence.page == chunk.page)
            ]
            if (
                not matching
                or evidence.chunk_id
                and evidence.chunk_id not in {chunk.chunk_id for chunk in matching}
            ):
                raise ValueError("Evidence was not found in the retrieved source chunks")
            selected = next(
                (chunk for chunk in matching if chunk.chunk_id == evidence.chunk_id), matching[0]
            )
            evidence.chunk_id, evidence.source_sha256 = selected.chunk_id, source_hash(value.paper)
            evidence.page = selected.page
            evidence.source_location = (
                "abstract"
                if value.paper.source_kind == "abstract"
                else f"source chunk {selected.chunk_id}, page {selected.page}, offsets {selected.start_offset}:{selected.end_offset}"
            )
        return output
