from __future__ import annotations

from abc import ABC
from pathlib import Path
from time import perf_counter
from typing import Any, ClassVar, Generic, TypeVar

from research_council.core.context import build_context
from research_council.core.routing import ModelRouter
from research_council.core.tracing import TraceEvent, TraceSink
from research_council.schemas.models import AgentExecution, Schema, TaskProfile, utcnow
from research_council.tools.registry import ToolRegistry

InputT = TypeVar("InputT", bound=Schema)
OutputT = TypeVar("OutputT", bound=Schema)


class BaseResearchAgent(ABC, Generic[InputT, OutputT]):
    name: ClassVar[str]
    role: ClassVar[str]
    allowed_tools: ClassVar[frozenset[str]] = frozenset()
    task_profile: ClassVar[TaskProfile]
    max_retries: ClassVar[int] = 2
    timeout: ClassVar[float] = 60
    provider_policy: ClassVar[str] = "configured_ordered_routes"
    input_schema: type[InputT]
    output_schema: type[OutputT]
    prompt_file: ClassVar[str]

    def __init__(
        self, router: ModelRouter, tools: ToolRegistry | None = None, trace: TraceSink | None = None
    ) -> None:
        self.router = router
        self.tools = tools or ToolRegistry()
        self.trace = trace

    def validate_input(self, value: InputT) -> InputT:
        return self.input_schema.model_validate(value.model_dump())

    def validate_output(self, value: OutputT) -> OutputT:
        return self.output_schema.model_validate(value.model_dump())

    def prompt(self) -> str:
        package_root = Path(__file__).parents[1]
        packaged = package_root / "prompts" / self.prompt_file
        development = Path(__file__).parents[3] / "prompts" / self.prompt_file
        path = packaged if packaged.is_file() else development
        return path.read_text(encoding="utf-8")

    async def execute(self, value: InputT) -> OutputT:
        return await self.router.generate(
            self.task_profile,
            self.name,
            self.prompt(),
            build_context(value),
            self.output_schema,
            retries=min(self.max_retries, self.router.settings.retries),
            timeout_seconds=min(self.timeout, self.router.settings.timeout_seconds),
        )

    async def run(self, value: InputT) -> OutputT:
        started = perf_counter()
        execution = AgentExecution(run_id=self.router.run_id, agent_id=self.name, task=self.role)
        self.router.repository.save(
            "agent_executions", execution.execution_id, execution, self.router.run_id
        )
        try:
            validated = self.validate_input(value)
            result = self.validate_output(await self.execute(validated))
            model_execution = self.router.last_success.get(self.name)
            if model_execution and "model_execution_id" in result.__class__.model_fields:
                result = result.model_copy(
                    update={"model_execution_id": model_execution.execution_id}
                )
            execution.status = "SUCCESS"
            return result
        except Exception as exc:
            execution.status = "FAILED"
            execution.error_type = type(exc).__name__
            raise
        finally:
            execution.end_time = utcnow()
            execution.latency = perf_counter() - started
            self.router.repository.save(
                "agent_executions", execution.execution_id, execution, self.router.run_id
            )
            if self.trace:
                self.trace.emit(
                    TraceEvent(
                        run_id=str(self.router.run_id),
                        agent_id=self.name,
                        event="agent_end",
                        status=execution.status,
                        latency=execution.latency,
                        error_type=execution.error_type,
                    )
                )

    async def invoke_tool(self, name: str, value: Schema) -> Any:
        return await self.tools.invoke(name, value, allowlist=self.allowed_tools)
