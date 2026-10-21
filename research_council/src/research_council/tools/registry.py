from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

from research_council.schemas.models import Schema


class ToolRegistry:
    def __init__(self) -> None:
        self._tools: dict[str, tuple[type[Schema], Callable[..., Awaitable[Any]]]] = {}

    def register(
        self, name: str, input_schema: type[Schema], handler: Callable[..., Awaitable[Any]]
    ) -> None:
        if name in self._tools:
            raise ValueError("Tool already registered")
        self._tools[name] = (input_schema, handler)

    async def invoke(
        self, name: str, payload: Schema | dict[str, Any], *, allowlist: frozenset[str]
    ) -> Any:
        if name not in allowlist:
            raise PermissionError(f"Tool {name} is not permitted for this agent")
        schema, handler = self._tools[name]
        validated = schema.model_validate(
            payload.model_dump() if isinstance(payload, Schema) else payload
        )
        return await handler(validated)
