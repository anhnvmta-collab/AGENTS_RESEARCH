from uuid import uuid4

import httpx
import pytest

from research_council.core.config import TriageWeights
from research_council.core.saturation import SearchSaturationDetector
from research_council.schemas.models import PaperScore, SearchQuery
from research_council.tools.arxiv import ArxivAdapter
from research_council.tools.ieee import IEEEAdapter
from research_council.tools.query import QueryExpander
from research_council.tools.search import SearchError


def test_query_expansion_has_all_strategies():
    queries = QueryExpander().expand("FHSS DOA on FPGA")
    assert {query.strategy for query in queries} == {
        "broad",
        "exact",
        "synonym",
        "algorithm",
        "hardware",
        "application",
        "recent",
        "seminal",
    }
    assert "frequency hopping" in next(
        query.text for query in queries if query.strategy == "synonym"
    )


def test_triage_weights_are_configurable_and_validated():
    weights = TriageWeights()
    assert sum(weights.model_dump().values()) == pytest.approx(1)
    score = PaperScore(paper_id=uuid4(), relevance=1, hardware_relevance=1)
    assert score.weighted_total(weights.model_dump()) == pytest.approx(0.35)
    with pytest.raises(ValueError):
        TriageWeights(relevance=1)


def test_saturation_requires_repeated_success_not_failed_searches():
    detector = SearchSaturationDetector(patience=2)
    papers = {uuid4()}
    one = detector.observe(papers, papers, 1, 1, [], search_complete=True)
    two = detector.observe(papers, papers, 1, 1, [one], search_complete=True)
    assert two.status == "SEARCH_SATURATED"
    assert two.reasons
    failed = detector.observe(papers, papers, 1, 1, [one], search_complete=False)
    assert failed.status == "INSUFFICIENT_SEARCH"


async def test_arxiv_atom_protocol_and_query_cache():
    atom = """<feed xmlns="http://www.w3.org/2005/Atom"><entry><id>http://arxiv.org/abs/0000.00001v1</id><title>Unit-test record, not literature</title><published>2024-01-01T00:00:00Z</published><summary>Unit-test abstract only.</summary><author><name>Unit author</name></author></entry></feed>"""
    calls = []

    def handler(request):
        calls.append(request)
        assert request.url.host == "export.arxiv.org"
        return httpx.Response(200, content=atom)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        adapter = ArxivAdapter(client, minimum_interval=0)
        query = SearchQuery(text="test")
        papers = await adapter.search(query, 1)
        await adapter.search(query, 1)
    assert len(calls) == 1 and papers[0].metadata.year == 2024
    assert papers[0].source_kind == "abstract"


async def test_arxiv_rejects_entity_declarations():
    async with httpx.AsyncClient(
        transport=httpx.MockTransport(
            lambda _: httpx.Response(200, content='<!DOCTYPE feed [<!ENTITY x "unsafe">]><feed/>')
        )
    ) as client:
        with pytest.raises(SearchError, match="Unsafe XML"):
            await ArxivAdapter(client, minimum_interval=0).search(SearchQuery(text="test"), 1)


async def test_ieee_is_explicit_optional_boundary():
    with pytest.raises(SearchError, match="not configured"):
        await IEEEAdapter().search(SearchQuery(text="test"), 1)
