from __future__ import annotations

import asyncio
import random
from time import perf_counter
from typing import TypeVar
from uuid import UUID

from pydantic import ValidationError

from research_council.core.config import Route, Settings
from research_council.providers.base import BaseLLMProvider, LLMRequest, LLMResponse, ProviderError
from research_council.repositories.store import SQLRepository
from research_council.schemas.models import ModelExecution, Schema, TaskProfile, utcnow

T = TypeVar("T", bound=Schema)


class BudgetExceeded(RuntimeError):
    pass


class ModelRouter:
    def __init__(
        self,
        settings: Settings,
        providers: dict[str, BaseLLMProvider],
        repository: SQLRepository,
        run_id: UUID,
    ) -> None:
        self.settings = settings
        self.providers = providers
        self.repository = repository
        self.run_id = run_id
        prior = repository.list_all("model_executions", ModelExecution, run_id)
        self.calls = len(prior)
        self.cost = sum(item.estimated_cost or 0 for item in prior)
        self.reserved = 0.0
        self.lock = asyncio.Lock()

    async def generate(
        self,
        profile: TaskProfile,
        role: str,
        system: str,
        user: str,
        schema: type[T],
        *,
        retries: int | None = None,
        timeout_seconds: float | None = None,
    ) -> T:
        routes = self.settings.models.get(profile, [])
        if not routes:
            raise ValueError(f"No route for {profile}")
        last_error: Exception | None = None
        for route in routes:
            if route.model == "CONFIGURE_ME":
                raise ValueError("Configure a model ID before enabling a live route")
            provider = self.providers.get(route.provider)
            if provider is None:
                last_error = ValueError("Provider unavailable")
                continue
            limit = self.settings.retries if retries is None else retries
            for attempt in range(limit + 1):
                request = LLMRequest(
                    model=route.model,
                    role=role,
                    system=system,
                    user=user,
                    output_schema=schema.model_json_schema(),
                    max_output_tokens=route.max_output_tokens,
                )
                reservation = self._reservation(route, request)
                async with self.lock:
                    if (
                        self.calls >= self.settings.research.max_model_calls
                        or self.cost + self.reserved + reservation
                        > self.settings.research.budget_usd
                    ):
                        raise BudgetExceeded("Research run model budget exhausted")
                    self.calls += 1
                    self.reserved += reservation
                started = perf_counter()
                execution = ModelExecution(
                    run_id=self.run_id,
                    agent_id=role,
                    task=profile.value,
                    provider=provider.name,
                    model=route.model,
                    retry_count=attempt,
                )
                execution.estimated_cost = reservation
                execution.cost_basis = (
                    "known_free" if provider.name == "fake" else "reserved_upper_bound"
                )
                self.repository.save(
                    "model_executions", execution.execution_id, execution, self.run_id
                )
                response: LLMResponse | None = None
                retryable = False
                retry_after = 0.0
                result: T | None = None
                try:
                    async with asyncio.timeout(timeout_seconds or self.settings.timeout_seconds):
                        response = await provider.generate(request)
                    if response.tool_calls:
                        raise ValueError("Unexpected tool calls in structured-only request")
                    if response.finish_reason in (
                        "incomplete",
                        "max_tokens",
                        "MAX_TOKENS",
                        "blocked",
                        "content_filter",
                    ):
                        raise ProviderError()
                    result = schema.model_validate_json(response.text)
                    execution.status = "SUCCESS"
                    execution.structured_output_valid = True
                except (
                    ValidationError,
                    TimeoutError,
                    ProviderError,
                    ValueError,
                    KeyError,
                    TypeError,
                ) as exc:
                    last_error = exc
                    execution.status = "FAILED"
                    execution.error_type = type(exc).__name__
                    retryable = (
                        isinstance(exc, (ValidationError, TimeoutError))
                        or isinstance(exc, ProviderError)
                        and exc.retryable
                    )
                    retry_after = (exc.retry_after or 0) if isinstance(exc, ProviderError) else 0
                except Exception as exc:
                    last_error = exc
                    execution.status = "FAILED"
                    execution.error_type = type(exc).__name__
                finally:
                    execution.end_time = utcnow()
                    execution.latency = perf_counter() - started
                    if response:
                        execution.input_tokens = response.input_tokens
                        execution.output_tokens = response.output_tokens
                    if execution.status == "RUNNING":
                        execution.status = "CANCELLED"
                        execution.error_type = "CancelledError"
                    execution.estimated_cost = (
                        self._cost(route, response)
                        if response and response.usage_available
                        else (0 if provider.name == "fake" else reservation)
                    )
                    execution.cost_basis = (
                        "known_free"
                        if provider.name == "fake"
                        else "usage"
                        if response and response.usage_available
                        else "reserved_upper_bound"
                    )
                    async with self.lock:
                        self.reserved -= reservation
                        self.cost += execution.estimated_cost or 0
                    self.repository.save(
                        "model_executions", execution.execution_id, execution, self.run_id
                    )
                if result is not None:
                    return result
                if not retryable or attempt == limit:
                    break
                backoff = min(
                    60,
                    self.settings.retry_base_seconds * 2**attempt
                    + random.uniform(0, self.settings.retry_base_seconds),
                )
                await asyncio.sleep(max(backoff, retry_after))
        raise RuntimeError("All configured model routes failed") from last_error

    def _reservation(self, route: Route, request: LLMRequest) -> float:
        if route.provider == "fake":
            return 0
        if route.input_cost_per_million is None or route.output_cost_per_million is None:
            raise ValueError("Live routes need configured token prices for budget enforcement")
        # Bytes are a conservative text-token bound; account for schema and request overhead.
        input_bound = (
            len((request.system + request.user + str(request.output_schema)).encode()) + 1024
        )
        return (
            input_bound * route.input_cost_per_million
            + route.max_output_tokens * route.output_cost_per_million
        ) / 1_000_000

    @staticmethod
    def _cost(route: Route, response: LLMResponse | None) -> float | None:
        if route.provider == "fake":
            return 0
        if (
            response is None
            or route.input_cost_per_million is None
            or route.output_cost_per_million is None
        ):
            return None
        return (
            response.input_tokens * route.input_cost_per_million
            + response.output_tokens * route.output_cost_per_million
        ) / 1_000_000
