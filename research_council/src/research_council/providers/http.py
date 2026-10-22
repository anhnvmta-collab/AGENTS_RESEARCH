from __future__ import annotations

import json
import os
from typing import Any

import httpx

from research_council.core.retry import retry_after_seconds
from research_council.providers.base import (
    BaseLLMProvider,
    LLMRequest,
    LLMResponse,
    ProviderError,
    ToolCall,
)
from research_council.providers.schema_transport import TRANSPORT_INSTRUCTION, anthropic_schema


class HTTPProvider(BaseLLMProvider):
    key_env: str
    endpoint: str

    def __init__(self, client: httpx.AsyncClient, *, api_key: str | None = None) -> None:
        self.client = client
        self._key = api_key if api_key is not None else os.environ.get(self.key_env, "")

    async def post(
        self, endpoint: str, body: dict[str, Any], headers: dict[str, str]
    ) -> dict[str, Any]:
        if not self._key:
            raise ProviderError()
        try:
            response = await self.client.post(endpoint, json=body, headers=headers)
        except (httpx.TimeoutException, httpx.NetworkError) as exc:
            raise ProviderError(retryable=True) from exc
        if response.is_error:
            retry_after = retry_after_seconds(response.headers.get("retry-after"))
            raise ProviderError(
                retryable=response.status_code == 429 or response.status_code >= 500,
                retry_after=retry_after,
            )
        try:
            result: dict[str, Any] = response.json()
            if not isinstance(result, dict):
                raise ValueError("Provider response must be a JSON object")
            return result
        except ValueError as exc:
            raise ProviderError(retryable=True) from exc


class OpenAIProvider(HTTPProvider):
    name = "openai"
    key_env = "OPENAI_API_KEY"
    endpoint = "https://api.openai.com/v1/responses"

    async def generate(self, request: LLMRequest) -> LLMResponse:
        body: dict[str, Any] = {
            "model": request.model,
            "instructions": request.system,
            "input": request.user,
            "max_output_tokens": request.max_output_tokens,
            "store": False,
        }
        if request.output_schema:
            body["text"] = {
                "format": {
                    "type": "json_schema",
                    "name": "research_artifact",
                    "schema": request.output_schema,
                    "strict": False,
                }
            }
        if request.tools:
            body["tools"] = [{"type": "function", **tool} for tool in request.tools]
        result = await self.post(self.endpoint, body, {"Authorization": f"Bearer {self._key}"})
        text_parts: list[str] = []
        calls: list[ToolCall] = []
        for item in result.get("output", []):
            if item.get("type") == "function_call":
                calls.append(
                    ToolCall(
                        call_id=item["call_id"],
                        name=item["name"],
                        arguments=json.loads(item["arguments"]),
                    )
                )
            for part in item.get("content", []):
                if part.get("type") == "output_text":
                    text_parts.append(part["text"])
        usage = result.get("usage") or {}
        return LLMResponse(
            text="".join(text_parts),
            usage_available=bool(usage),
            input_tokens=usage.get("input_tokens", 0),
            output_tokens=usage.get("output_tokens", 0),
            tool_calls=calls,
            finish_reason=result.get("status", "unknown"),
        )


class AnthropicProvider(HTTPProvider):
    name = "anthropic"
    key_env = "ANTHROPIC_API_KEY"
    endpoint = "https://api.anthropic.com/v1/messages"

    def input_byte_bound(self, request: LLMRequest) -> int:
        codec = anthropic_schema(request.output_schema) if request.output_schema else None
        return (
            len(
                (
                    request.system
                    + request.user
                    + (TRANSPORT_INSTRUCTION if codec and codec.has_maps else "")
                    + str(codec.wire if codec else None)
                ).encode()
            )
            + 2048
        )

    async def generate(self, request: LLMRequest) -> LLMResponse:
        codec = anthropic_schema(request.output_schema) if request.output_schema else None
        body: dict[str, Any] = {
            "model": request.model,
            "system": request.system + (TRANSPORT_INSTRUCTION if codec and codec.has_maps else ""),
            "messages": [{"role": "user", "content": request.user}],
            "max_tokens": request.max_output_tokens,
        }
        if request.output_schema:
            body["output_config"] = {
                "format": {
                    "type": "json_schema",
                    "schema": codec.wire if codec else request.output_schema,
                }
            }
        if request.tools:
            body["tools"] = [
                {
                    "name": tool["name"],
                    "description": tool.get("description", ""),
                    "input_schema": tool["parameters"],
                }
                for tool in request.tools
            ]
        result = await self.post(
            self.endpoint, body, {"x-api-key": self._key, "anthropic-version": "2023-06-01"}
        )
        usage = result.get("usage") or {}
        content = result.get("content", [])
        text = "".join(part["text"] for part in content if part.get("type") == "text")
        if codec and codec.has_maps and result.get("stop_reason") == "end_turn":
            text = json.dumps(codec.convert(json.loads(text)), ensure_ascii=False)
        return LLMResponse(
            text=text,
            usage_available=bool(usage),
            input_tokens=usage.get("input_tokens", 0),
            output_tokens=usage.get("output_tokens", 0),
            tool_calls=[
                ToolCall(call_id=part["id"], name=part["name"], arguments=part["input"])
                for part in content
                if part.get("type") == "tool_use"
            ],
            finish_reason=result.get("stop_reason", "unknown"),
        )


class GeminiProvider(HTTPProvider):
    name = "google"
    key_env = "GOOGLE_API_KEY"
    endpoint = "https://generativelanguage.googleapis.com/v1beta/models/"

    async def generate(self, request: LLMRequest) -> LLMResponse:
        # Model IDs are a single path segment, never arbitrary endpoints.
        if not request.model or any(
            character not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_."
            for character in request.model
        ):
            raise ProviderError()
        config: dict[str, Any] = {"maxOutputTokens": request.max_output_tokens}
        if request.model == "gemini-4-argon":
            # Make Argon's documented default explicit; never send deprecated thinkingBudget.
            config["thinkingConfig"] = {"thinkingLevel": "MEDIUM"}
        if request.output_schema:
            config.update(
                responseMimeType="application/json", responseJsonSchema=request.output_schema
            )
        body: dict[str, Any] = {
            "systemInstruction": {"parts": [{"text": request.system}]},
            "contents": [{"role": "user", "parts": [{"text": request.user}]}],
            "generationConfig": config,
        }
        if request.tools:
            body["tools"] = [{"functionDeclarations": request.tools}]
        result = await self.post(
            f"{self.endpoint}{request.model}:generateContent", body, {"x-goog-api-key": self._key}
        )
        usage = result.get("usageMetadata") or {}
        candidates = result.get("candidates", [])
        parts = candidates[0].get("content", {}).get("parts", []) if candidates else []
        return LLMResponse(
            text="".join(part.get("text", "") for part in parts if not part.get("thought")),
            usage_available=bool(usage),
            input_tokens=usage.get("promptTokenCount", 0),
            # Gemini bills candidate and reasoning tokens together as output.
            output_tokens=usage.get("candidatesTokenCount", 0) + usage.get("thoughtsTokenCount", 0),
            tool_calls=[
                ToolCall(
                    call_id=str(index),
                    name=part["functionCall"]["name"],
                    arguments=part["functionCall"].get("args", {}),
                )
                for index, part in enumerate(parts)
                if "functionCall" in part
            ],
            finish_reason=candidates[0].get("finishReason", "unknown") if candidates else "blocked",
        )
