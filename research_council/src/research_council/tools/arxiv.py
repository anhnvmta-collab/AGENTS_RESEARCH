from __future__ import annotations

import asyncio
from time import monotonic
from uuid import NAMESPACE_URL, uuid5
from xml.etree import ElementTree

import httpx

from research_council.core.retry import retry_after_seconds
from research_council.schemas.models import Paper, PaperMetadata, SearchQuery
from research_council.tools.search import SearchError, plain_text


class ArxivAdapter:
    """Official Atom API, one connection and at least three seconds between requests."""

    name = "arxiv"
    endpoint = "https://export.arxiv.org/api/query"

    def __init__(self, client: httpx.AsyncClient, *, minimum_interval: float = 3) -> None:
        self.client, self.minimum_interval = client, max(3, minimum_interval)
        self._lock = asyncio.Lock()
        self._last_request = 0.0
        self._cache: dict[tuple[str, str, int], list[Paper]] = {}

    async def search(self, query: SearchQuery, limit: int) -> list[Paper]:
        key = (query.text, query.strategy, limit)
        async with self._lock:
            if key in self._cache:
                return [paper.model_copy(deep=True) for paper in self._cache[key]]
            params: dict[str, str | int] = {
                "search_query": query.text
                if "all:" in query.text or "ti:" in query.text
                else "all:" + query.text,
                "start": 0,
                "max_results": min(limit, 100),
            }
            if query.strategy == "recent":
                params.update(sortBy="submittedDate", sortOrder="descending")
            for attempt in range(3):
                await asyncio.sleep(
                    max(0, self.minimum_interval - (monotonic() - self._last_request))
                )
                self._last_request = monotonic()
                try:
                    response = await self.client.get(
                        self.endpoint, params=params, headers={"User-Agent": "ResearchCouncil/1.0"}
                    )
                    if response.status_code == 429 or response.status_code >= 500:
                        if attempt < 2:
                            await asyncio.sleep(
                                max(
                                    0.5 * 2**attempt,
                                    retry_after_seconds(response.headers.get("retry-after")) or 0,
                                )
                            )
                            continue
                        raise SearchError("arXiv rate limit/service failure")
                    if response.is_error or len(response.content) > 2_000_000:
                        raise SearchError("arXiv response rejected")
                    text = response.content.decode("utf-8-sig")
                    if "<!DOCTYPE" in text.upper() or "<!ENTITY" in text.upper() or "\x00" in text:
                        raise SearchError("Unsafe XML declarations rejected")
                    papers = self.parse(text)
                    self._cache[key] = papers
                    return [paper.model_copy(deep=True) for paper in papers]
                except (httpx.TimeoutException, httpx.NetworkError):
                    if attempt == 2:
                        raise SearchError("arXiv request failed after retries") from None
            raise SearchError("arXiv search incomplete")

    @staticmethod
    def parse(text: str) -> list[Paper]:
        root = ElementTree.fromstring(text)
        namespace = {
            "atom": "http://www.w3.org/2005/Atom",
            "arxiv": "http://arxiv.org/schemas/atom",
        }
        papers: list[Paper] = []
        for entry in root.findall("atom:entry", namespace):
            url = entry.findtext("atom:id", "", namespace).strip().replace("http://", "https://", 1)
            if not url.startswith("https://arxiv.org/abs/"):
                raise SearchError("Invalid arXiv record identity")
            title = plain_text(entry.findtext("atom:title", "", namespace))
            abstract = plain_text(entry.findtext("atom:summary", "", namespace)) or None
            year = int(entry.findtext("atom:published", "", namespace)[:4])
            meta = PaperMetadata(
                title=title,
                authors=[
                    plain_text(author.findtext("atom:name", "", namespace))
                    for author in entry.findall("atom:author", namespace)
                ],
                year=year,
                doi=entry.findtext("arxiv:doi", None, namespace),
                url=url,
                abstract=abstract,
                metadata_source="arxiv",
                metadata_verified=True,
                venue=entry.findtext("arxiv:journal_ref", None, namespace),
            )
            papers.append(
                Paper(
                    paper_id=uuid5(NAMESPACE_URL, meta.doi or url),
                    metadata=meta,
                    source_text=abstract,
                    source_kind="abstract" if abstract else "metadata",
                )
            )
        return papers
