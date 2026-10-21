from __future__ import annotations

import asyncio
import re
from difflib import SequenceMatcher

from research_council.agents.contracts import CandidatesOutput, SearchInput
from research_council.repositories.store import normalized_title
from research_council.schemas.models import (
    CitationObservation,
    Paper,
    PaperCandidate,
    SearchAttempt,
)
from research_council.tools.local import LocalDocumentAdapter
from research_council.tools.search import CitationAdapter, SearchAdapter


class PaperDeduplicator:
    @staticmethod
    def same(left: Paper, right: Paper) -> bool:
        a, b = left.metadata, right.metadata
        if (
            left.provenance == "fixture"
            and right.provenance != "fixture"
            or right.provenance == "fixture"
            and left.provenance != "fixture"
        ):
            return False
        if a.doi and b.doi:
            return a.doi == b.doi
        if a.year and b.year and a.year != b.year:
            return False
        title_a, title_b = normalized_title(a.title), normalized_title(b.title)
        authors_a = {normalized_title(author) for author in a.authors}
        authors_b = {normalized_title(author) for author in b.authors}
        if title_a == title_b:
            return not (authors_a and authors_b and not authors_a & authors_b)
        if re.findall(r"\d+", title_a) != re.findall(r"\d+", title_b):
            return False
        return (
            bool(authors_a & authors_b)
            and a.year is not None
            and a.year == b.year
            and SequenceMatcher(None, title_a, title_b).ratio() >= 0.94
        )

    def deduplicate(self, candidates: list[PaperCandidate]) -> list[PaperCandidate]:
        output: list[PaperCandidate] = []
        for candidate in candidates:
            match = next((item for item in output if self.same(item.paper, candidate.paper)), None)
            if match:
                match.query_ids = list(dict.fromkeys(match.query_ids + candidate.query_ids))
                match.discovery_sources = list(
                    dict.fromkeys(match.discovery_sources + candidate.discovery_sources)
                )
                if len(candidate.paper.source_text or "") > len(match.paper.source_text or ""):
                    original_id = match.paper.paper_id
                    match.paper = candidate.paper.model_copy(update={"paper_id": original_id})
            else:
                output.append(candidate.model_copy(deep=True))
        return output


class DiscoveryService:
    def __init__(
        self,
        adapters: list[SearchAdapter],
        citations: list[CitationAdapter],
        local: LocalDocumentAdapter,
        semaphore: asyncio.Semaphore,
        *,
        limit: int = 10,
    ) -> None:
        self.adapters, self.citations, self.local, self.semaphore, self.limit = (
            adapters,
            citations,
            local,
            semaphore,
            limit,
        )

    async def search(self, value: SearchInput) -> CandidatesOutput:
        result = CandidatesOutput()

        async def one(adapter: SearchAdapter, index: int) -> None:
            query = value.queries[index]
            async with self.semaphore:
                try:
                    papers = await adapter.search(query, self.limit)
                    result.attempts.append(
                        SearchAttempt(
                            adapter=adapter.name,
                            query=query,
                            status="SUCCESS",
                            result_count=len(papers),
                        )
                    )
                    result.candidates.extend(
                        PaperCandidate(
                            paper=paper,
                            query_ids=[query.query_id],
                            discovery_sources=[adapter.name],
                        )
                        for paper in papers
                    )
                except Exception as exc:
                    result.attempts.append(
                        SearchAttempt(
                            adapter=adapter.name,
                            query=query,
                            status="FAILED",
                            error_type=type(exc).__name__,
                        )
                    )
                    result.failures.append(f"{adapter.name}:{query.query_id}:{type(exc).__name__}")

        await asyncio.gather(
            *(
                one(adapter, index)
                for adapter in self.adapters
                for index, query in enumerate(value.queries)
                if query.adapter in ("all", adapter.name)
            )
        )
        if not self.adapters and value.queries:
            result.failures.append("No search adapters enabled; no literature findings available.")
        return result

    async def citation_search(self, value: SearchInput) -> CandidatesOutput:
        result = CandidatesOutput()
        if value.seed_papers and not self.citations:
            result.failures.append(
                "No citation adapters enabled; citation-chain coverage unavailable."
            )

        async def one(adapter: CitationAdapter, paper: Paper) -> None:
            async with self.semaphore:
                try:
                    papers = await adapter.explore(paper, value.direction, self.limit)
                    seed = paper.metadata.doi or paper.metadata.url
                    for target in papers:
                        identifier = target.metadata.doi or target.metadata.url
                        if seed and identifier:
                            result.citation_observations.append(
                                CitationObservation(
                                    seed_identifier=seed,
                                    target_identifier=identifier,
                                    direction=value.direction,
                                    adapter=adapter.name,
                                    relation_verified=(
                                        value.direction == "backward"
                                        and adapter.name in {"crossref", "openalex"}
                                    )
                                    or (
                                        value.direction == "forward" and adapter.name == "openalex"
                                    ),
                                )
                            )
                    result.attempts.append(
                        SearchAttempt(
                            adapter=adapter.name,
                            operation=value.direction,
                            seed_paper_id=paper.paper_id,
                            status="SUCCESS",
                            result_count=len(papers),
                        )
                    )
                    result.candidates.extend(
                        PaperCandidate(
                            paper=item, discovery_sources=[f"{adapter.name}:{value.direction}"]
                        )
                        for item in papers
                    )
                except Exception as exc:
                    result.attempts.append(
                        SearchAttempt(
                            adapter=adapter.name,
                            operation=value.direction,
                            seed_paper_id=paper.paper_id,
                            status="FAILED",
                            error_type=type(exc).__name__,
                        )
                    )
                    result.failures.append(f"{adapter.name}:{value.direction}:{type(exc).__name__}")

        await asyncio.gather(
            *(one(adapter, paper) for adapter in self.citations for paper in value.seed_papers)
        )
        return result

    async def local_read(self, value: SearchInput) -> CandidatesOutput:
        result = CandidatesOutput()
        for path in value.local_paths:
            try:
                async with self.semaphore:
                    paper = await self.local.read(path)
                result.candidates.append(PaperCandidate(paper=paper, discovery_sources=["local"]))
            except Exception as exc:
                result.failures.append(f"local:{type(exc).__name__}")
        return result
