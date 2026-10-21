import asyncio

import httpx
import pytest
from pypdf.errors import PdfReadError

from research_council.agents.contracts import SearchInput
from research_council.schemas.models import Paper, PaperCandidate, PaperMetadata, SearchQuery
from research_council.tools.discovery import DiscoveryService, PaperDeduplicator
from research_council.tools.local import LocalDocumentAdapter
from research_council.tools.search import CrossrefAdapter, OpenAlexAdapter


def paper(title="FPGA sparse sensing", doi=None):
    return Paper(
        metadata=PaperMetadata(
            title=title, doi=doi, authors=["A. Example"], year=2020, metadata_source="test"
        )
    )


def test_deduplication():
    a = PaperCandidate(paper=paper(doi="10.1234/A"), discovery_sources=["a"])
    b = PaperCandidate(paper=paper(doi="https://doi.org/10.1234/a"), discovery_sources=["b"])
    c = PaperCandidate(paper=paper(doi="10.1234/b"))
    result = PaperDeduplicator().deduplicate([a, b, c])
    assert len(result) == 2
    assert result[0].discovery_sources == ["a", "b"]
    conflicting_author = paper()
    conflicting_author.metadata.authors = ["Different author"]
    assert not PaperDeduplicator.same(paper(), conflicting_author)
    assert PaperDeduplicator.same(paper("FPGA Sparse Sensing!"), paper())
    assert not PaperDeduplicator.same(paper(), paper().model_copy(update={"provenance": "fixture"}))


async def test_metadata_adapters():
    def handler(request):
        if request.url.host == "api.crossref.org":
            return httpx.Response(
                200,
                json={
                    "message": {
                        "items": [
                            {
                                "title": ["RF sensing"],
                                "DOI": "10.1234/test",
                                "author": [{"given": "A", "family": "Example"}],
                                "issued": {"date-parts": [[2024]]},
                                "abstract": "<jats:p>Bounded source text.</jats:p>",
                            }
                        ]
                    }
                },
            )
        return httpx.Response(
            200,
            json={
                "results": [
                    {
                        "id": "https://openalex.org/W1",
                        "title": "RF sensing",
                        "publication_year": 2024,
                        "abstract_inverted_index": {"Bounded": [0], "text": [1]},
                        "authorships": [],
                    }
                ]
            },
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        query = SearchQuery(text="RF sensing")
        crossref = await CrossrefAdapter(client).search(query, 2)
        openalex = await OpenAlexAdapter(client).search(query, 2)
    assert crossref[0].metadata.doi == "10.1234/test"
    assert crossref[0].source_text == "Bounded source text."
    assert openalex[0].source_text == "Bounded text"


async def test_failed_scout_does_not_kill_other_scout(tmp_path):
    class Adapter:
        name = "good"

        async def search(self, query, limit):
            return [paper()]

    class Broken(Adapter):
        name = "broken"

        async def search(self, query, limit):
            raise RuntimeError("failure")

    service = DiscoveryService(
        [Adapter(), Broken()], [], LocalDocumentAdapter(tmp_path), asyncio.Semaphore(2)
    )
    result = await service.search(SearchInput(task="discover", queries=[SearchQuery(text="RF")]))
    assert len(result.candidates) == 1 and len(result.failures) == 1


async def test_local_documents_and_escape(tmp_path):
    (tmp_path / "paper.txt").write_text("Untrusted instructions are source data.", encoding="utf-8")
    adapter = LocalDocumentAdapter(tmp_path)
    result = await adapter.read("paper.txt")
    assert result.page_texts[1] == result.source_text
    with pytest.raises(ValueError):
        await adapter.read("../outside.txt")
    (tmp_path / "bad.pdf").write_bytes(b"not a pdf")
    with pytest.raises(PdfReadError):
        await adapter.read("bad.pdf")
