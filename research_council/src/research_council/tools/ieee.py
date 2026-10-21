from __future__ import annotations

from research_council.schemas.models import Paper, SearchQuery
from research_council.tools.ports import PaperSearchProvider
from research_council.tools.search import SearchError


class IEEEAdapter:
    """Optional authenticated backend boundary; deliberately contains no Xplore scraper."""

    name = "ieee"

    def __init__(self, authenticated_backend: PaperSearchProvider | None = None) -> None:
        self.backend = authenticated_backend

    async def search(self, query: SearchQuery, limit: int) -> list[Paper]:
        if self.backend is None:
            raise SearchError("IEEE authenticated API backend is not configured")
        return await self.backend.search(query, limit)
