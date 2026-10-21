from __future__ import annotations

import asyncio
from collections.abc import Callable, Iterable

from research_council.providers.base import BaseLLMProvider, LLMRequest, LLMResponse


class FakeProvider(BaseLLMProvider):
    """Explicit offline adapter. It never invents papers or evidence by default."""

    name = "fake"

    def __init__(
        self,
        responses: Iterable[LLMResponse | Exception] = (),
        *,
        responder: Callable[[LLMRequest], LLMResponse] | None = None,
        delay: float = 0,
    ) -> None:
        self.responses = iter(responses)
        self.responder = responder
        self.delay = delay
        self.requests: list[LLMRequest] = []
        self.active = 0
        self.max_active = 0

    async def generate(self, request: LLMRequest) -> LLMResponse:
        self.requests.append(request)
        self.active += 1
        self.max_active = max(self.max_active, self.active)
        try:
            await asyncio.sleep(self.delay)
            item = (
                self.responder(request)
                if self.responder
                else next(self.responses, LLMResponse(text="{}"))
            )
            if isinstance(item, Exception):
                raise item
            return item
        finally:
            self.active -= 1
