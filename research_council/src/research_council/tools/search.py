from __future__ import annotations

import asyncio
import os
import random
import re
from html import unescape
from typing import Any, Protocol
from urllib.parse import quote
from uuid import NAMESPACE_URL, uuid5

import httpx

from research_council.core.security import sanitize_text
from research_council.schemas.models import Paper, PaperMetadata, SearchQuery


class SearchAdapter(Protocol):
    name: str

    async def search(self, query: SearchQuery, limit: int) -> list[Paper]: ...


class CitationAdapter(Protocol):
    name: str

    async def explore(self, paper: Paper, direction: str, limit: int) -> list[Paper]: ...


class MetadataAdapter(Protocol):
    name: str

    async def resolve(self, doi: str) -> PaperMetadata | None: ...


class SearchError(RuntimeError):
    pass


def plain_text(value: str) -> str:
    return sanitize_text(unescape(re.sub(r"<[^>]*>", " ", value)), 100_000).strip()


class MetadataHTTP:
    def __init__(
        self,
        client: httpx.AsyncClient,
        contact_email: str | None = None,
        *,
        retry_base: float = 0.5,
    ) -> None:
        self.client = client
        self.contact_email = contact_email
        self.retry_base = retry_base

    async def get(self, url: str, params: dict[str, str | int] | None = None) -> dict[str, Any]:
        for attempt in range(3):
            delay = self.retry_base * 2**attempt + random.uniform(0, self.retry_base)
            try:
                response = await self.client.get(
                    url,
                    params=params,
                    headers={
                        "User-Agent": "ResearchCouncil/1.0"
                        + (f" (mailto:{self.contact_email})" if self.contact_email else "")
                    },
                )
                if response.status_code == 404:
                    return {}
                if response.status_code == 429 or response.status_code >= 500:
                    try:
                        delay = max(delay, min(60, float(response.headers.get("retry-after", "0"))))
                    except ValueError:
                        pass
                    raise SearchError("Transient metadata search failure")
                if response.is_error:
                    raise ValueError("Metadata adapter rejected the request")
                result: dict[str, Any] = response.json()
                return result
            except (httpx.TimeoutException, httpx.NetworkError, SearchError):
                if attempt == 2:
                    raise SearchError("Metadata search failed after retries") from None
                await asyncio.sleep(delay)
        raise SearchError("Metadata search did not complete")


class CrossrefAdapter(MetadataHTTP):
    name = "crossref"
    base_url = "https://api.crossref.org/works"

    @staticmethod
    def parse(item: dict[str, Any]) -> Paper:
        date = item.get("published", item.get("issued", {})).get("date-parts", [[]])
        year = date[0][0] if date and date[0] else None
        abstract = plain_text(item.get("abstract", "")) or None
        doi = item.get("DOI")
        title = plain_text((item.get("title") or ["Untitled record"])[0])
        authors = [
            " ".join(filter(None, [author.get("given"), author.get("family")]))
            or author.get("name", "")
            for author in item.get("author", [])
        ]
        meta = PaperMetadata(
            title=title,
            authors=[name for name in authors if name],
            year=year,
            venue=(item.get("container-title") or [None])[0],
            doi=doi,
            url=item.get("URL") or (f"https://doi.org/{doi}" if doi else None),
            abstract=abstract,
            citation_count=item.get("is-referenced-by-count"),
            metadata_source="crossref",
            metadata_verified=True,
            retracted=True
            if any(
                update.get("type") in ("retraction", "withdrawal")
                for update in item.get("update-to", [])
            )
            else None,
        )
        identity = meta.doi or f"crossref:{title}:{year}"
        return Paper(
            paper_id=uuid5(NAMESPACE_URL, identity),
            metadata=meta,
            source_text=abstract,
            source_kind="abstract" if abstract else "metadata",
        )

    async def search(self, query: SearchQuery, limit: int) -> list[Paper]:
        params: dict[str, str | int] = {"query.bibliographic": query.text, "rows": limit}
        if query.strategy == "recent":
            params.update(sort="published", order="desc")
        if self.contact_email:
            params["mailto"] = self.contact_email
        result = await self.get(self.base_url, params)
        return [self.parse(item) for item in result.get("message", {}).get("items", [])]

    async def resolve(self, doi: str) -> PaperMetadata | None:
        result = await self.get(f"{self.base_url}/{quote(doi, safe='')}")
        return self.parse(result["message"]).metadata if result.get("message") else None

    async def explore(self, paper: Paper, direction: str, limit: int) -> list[Paper]:
        if direction == "backward" and paper.metadata.doi:
            data = await self.get(f"{self.base_url}/{quote(paper.metadata.doi, safe='')}")
            references = data.get("message", {}).get("reference", [])
            output: list[Paper] = []
            for reference in references[:limit]:
                if reference.get("DOI"):
                    record = await self.get(f"{self.base_url}/{quote(reference['DOI'], safe='')}")
                    if record.get("message"):
                        output.append(self.parse(record["message"]))
            return output
        # Crossref does not provide a public complete forward-citation endpoint.
        if direction == "forward":
            raise SearchError("Forward citation exploration requires OpenAlex")
        text = (
            paper.metadata.authors[0]
            if direction == "author" and paper.metadata.authors
            else paper.metadata.title
        )
        return await self.search(SearchQuery(text=text), limit)


class OpenAlexAdapter(MetadataHTTP):
    name = "openalex"
    base_url = "https://api.openalex.org/works"

    @staticmethod
    def parse(item: dict[str, Any]) -> Paper:
        index = item.get("abstract_inverted_index") or {}
        tokens = {
            position: word
            for word, positions in index.items()
            for position in positions
            if position < 15000
        }
        abstract = sanitize_text(" ".join(tokens[key] for key in sorted(tokens))) or None
        location = item.get("primary_location") or {}
        source = location.get("source") or {}
        meta = PaperMetadata(
            title=plain_text(item.get("title") or item.get("display_name") or "Untitled record"),
            authors=[
                auth.get("author", {}).get("display_name", "")
                for auth in item.get("authorships", [])
            ],
            year=item.get("publication_year"),
            venue=source.get("display_name"),
            doi=item.get("doi"),
            url=location.get("landing_page_url") or item.get("id"),
            abstract=abstract,
            citation_count=item.get("cited_by_count"),
            retracted=item.get("is_retracted"),
            metadata_source="openalex",
            metadata_verified=True,
        )
        return Paper(
            paper_id=uuid5(NAMESPACE_URL, meta.doi or item["id"]),
            metadata=meta,
            source_text=abstract,
            source_kind="abstract" if abstract else "metadata",
        )

    async def fetch(
        self, suffix: str = "", params: dict[str, str | int] | None = None
    ) -> dict[str, Any]:
        params = dict(params or {})
        key = os.environ.get("OPENALEX_API_KEY")
        if key:
            params["api_key"] = key
        return await self.get(self.base_url + suffix, params)

    async def search(self, query: SearchQuery, limit: int) -> list[Paper]:
        params: dict[str, str | int] = {"search": query.text, "per-page": limit}
        if query.strategy == "recent":
            params["sort"] = "publication_date:desc"
        data = await self.fetch(params=params)
        return [self.parse(item) for item in data.get("results", [])]

    async def resolve(self, doi: str) -> PaperMetadata | None:
        data = await self.fetch("/" + quote("https://doi.org/" + doi, safe=""))
        return self.parse(data).metadata if data.get("id") else None

    async def explore(self, paper: Paper, direction: str, limit: int) -> list[Paper]:
        if not paper.metadata.doi:
            return await self.search(SearchQuery(text=paper.metadata.title), limit)
        seed = await self.fetch("/" + quote("https://doi.org/" + paper.metadata.doi, safe=""))
        if not seed:
            return []
        if direction in ("backward", "related"):
            ids = seed.get("referenced_works" if direction == "backward" else "related_works", [])[
                :limit
            ]
            if not ids:
                return []
            data = await self.fetch(
                params={
                    "filter": "openalex:"
                    + "|".join(identity.rsplit("/", 1)[-1] for identity in ids),
                    "per-page": limit,
                }
            )
        elif direction == "forward":
            data = await self.fetch(
                params={
                    "filter": "referenced_works:" + seed["id"].rsplit("/", 1)[-1],
                    "per-page": limit,
                }
            )
        elif direction == "author":
            authors = seed.get("authorships", [])
            if not authors:
                return []
            data = await self.fetch(
                params={
                    "filter": "authorships.author.id:"
                    + authors[0]["author"]["id"].rsplit("/", 1)[-1],
                    "per-page": limit,
                }
            )
        else:
            raise ValueError("Unknown citation direction")
        return [self.parse(item) for item in data.get("results", [])]
