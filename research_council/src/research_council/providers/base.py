from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import AsyncIterator
from typing import Any, TypeVar

from pydantic import Field

from research_council.schemas.models import Schema

T = TypeVar("T", bound=Schema)


class ToolCall(Schema):
    call_id: str
    name: str
    arguments: dict[str, Any]


class LLMRequest(Schema):
    model: str
    system: str
    user: str
    role: str = ""
    output_schema: dict[str, Any] | None = None
    max_output_tokens: int = 4096
    tools: list[dict[str, Any]] = Field(default_factory=list)


class LLMResponse(Schema):
    text: str
    input_tokens: int = Field(default=0, ge=0)
    output_tokens: int = Field(default=0, ge=0)
    usage_available: bool = True
    tool_calls: list[ToolCall] = Field(default_factory=list)
    finish_reason: str = "complete"


class ProviderError(Exception):
    def __init__(self, *, retryable: bool = False, retry_after: float | None = None) -> None:
        super().__init__("Provider request failed")
        self.retryable = retryable
        self.retry_after = retry_after


class BaseLLMProvider(ABC):
    name: str
    native_streaming = False

    @abstractmethod
    async def generate(self, request: LLMRequest) -> LLMResponse: ...

    async def generate_structured(
        self, request: LLMRequest, schema: type[T]
    ) -> tuple[T, LLMResponse]:
        response = await self.generate(
            request.model_copy(update={"output_schema": schema.model_json_schema()})
        )
        return schema.model_validate_json(response.text), response

    async def stream(self, request: LLMRequest) -> AsyncIterator[str]:
        """Buffered fallback; native_streaming advertises this limitation."""
        yield (await self.generate(request)).text
