"""Scientific retrieval ports owned by Research Council, independent of frameworks."""

from __future__ import annotations

from typing import Protocol

from research_council.schemas.models import Paper, PaperMetadata, SearchQuery


class PaperSearchProvider(Protocol):
    name: str

    async def search(self, query: SearchQuery, limit: int) -> list[Paper]: ...


class MetadataProvider(Protocol):
    name: str

    async def resolve(self, doi: str) -> PaperMetadata | None: ...


class CitationProvider(Protocol):
    name: str

    async def explore(self, paper: Paper, direction: str, limit: int) -> list[Paper]: ...


class FullTextProvider(Protocol):
    name: str

    async def retrieve(self, paper: Paper) -> Paper | None: ...
