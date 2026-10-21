from research_council.agents.base import BaseResearchAgent
from research_council.agents.contracts import (
    CandidatesOutput,
    PriorArtReport,
    ReviewInput,
    SearchInput,
)
from research_council.schemas.models import SearchQuery, TaskProfile


class PriorArtHunter(BaseResearchAgent[ReviewInput, PriorArtReport]):
    name = "PriorArtHunter"
    role = "Find work that INVALIDATES the normalized claim. Attack exact concepts, synonyms, component combinations, older terminology, recent work, citations and author chains. Rank closest prior art. Missing results do not prove novelty."
    task_profile = TaskProfile.ADVERSARIAL_REVIEW
    allowed_tools = frozenset(["search", "evidence_read"])
    input_schema = ReviewInput
    output_schema = PriorArtReport
    prompt_file = "prior_art_hunter.md"

    async def execute(self, value: ReviewInput) -> PriorArtReport:
        strategies = [value.normalized_claim, " ".join(value.technical_keywords)]
        strategies += [f"{keyword} prior method" for keyword in value.technical_keywords[:3]]
        queries = [
            SearchQuery(text=text, strategy="targeted") for text in dict.fromkeys(strategies)
        ]
        discovered = CandidatesOutput.model_validate(
            await self.invoke_tool(
                "search", SearchInput(task="Find invalidating prior art", queries=queries)
            )
        )
        isolated = value.model_copy(deep=True)
        isolated.prior_art_papers = [
            item.paper.model_copy(update={"source_text": None, "page_texts": {}})
            for item in discovered.candidates[:20]
        ]
        report = await super().execute(isolated)
        if report.candidate_id != value.candidate_id or report.revision != value.revision:
            raise ValueError("Prior-art candidate mismatch")
        allowed = {item.paper.paper_id for item in discovered.candidates}
        if any(
            match.paper_id not in allowed or match.candidate_id != value.candidate_id
            for match in report.matches
        ):
            raise ValueError("Prior-art report references undiscovered work")
        report.complete = (
            not discovered.failures
            and bool(discovered.attempts)
            and all(item.status == "SUCCESS" for item in discovered.attempts)
        )
        report.queries = [query.text for query in queries]
        report.search_failures = discovered.failures
        report.discovered_candidates = discovered.candidates
        report.search_attempts = discovered.attempts
        report.matches.sort(key=lambda item: item.similarity, reverse=True)
        return report
