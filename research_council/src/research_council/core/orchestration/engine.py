from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable, Sequence
from contextlib import suppress
from dataclasses import dataclass
from datetime import timedelta
from typing import Protocol, TypeVar
from uuid import UUID, uuid4

from research_council.core.config import Settings
from research_council.core.orchestration.state import WorkflowState
from research_council.core.tracing import TraceEvent, TraceSink
from research_council.repositories.store import SQLRepository
from research_council.schemas.models import ResearchQuestion, ResearchRun, WorkflowEvent, utcnow

T = TypeVar("T")
R = TypeVar("R")


class Workflow(Protocol):
    async def resume(self, run_id: UUID) -> ResearchRun: ...


class Concurrency:
    def __init__(self, settings: Settings) -> None:
        self.agents = asyncio.Semaphore(settings.concurrency.agents)
        self.searches = asyncio.Semaphore(settings.concurrency.searches)
        self.paper_reads = asyncio.Semaphore(settings.concurrency.paper_reads)

    async def agent(self, action: Callable[[], Awaitable[T]]) -> T:
        async with self.agents:
            return await action()


async def parallel_map(
    items: Sequence[T], action: Callable[[T], Awaitable[R]], semaphore: asyncio.Semaphore
) -> list[R | BaseException]:
    async def execute(item: T) -> R:
        async with semaphore:
            return await action(item)

    return await asyncio.gather(*(execute(item) for item in items), return_exceptions=True)


@dataclass(frozen=True)
class Stage:
    name: str
    execute: Callable[[ResearchRun, WorkflowState], Awaitable[WorkflowState]]
    approvals_before: tuple[str, ...] = ()


class RunLease:
    def __init__(self, repository: SQLRepository, run_id: UUID) -> None:
        self.repository = repository
        self.run_id = run_id
        self.owner = str(uuid4())

    def acquire(self) -> None:
        until = (utcnow() + timedelta(seconds=45)).isoformat()
        self.repository.acquire_lease(self.run_id, self.owner, until)

    async def heartbeat(self) -> None:
        while True:
            await asyncio.sleep(10)
            self.repository.renew_lease(
                self.run_id, self.owner, (utcnow() + timedelta(seconds=45)).isoformat()
            )

    def release(self) -> None:
        self.repository.release_lease(self.run_id, self.owner)


class WorkflowEngine:
    def __init__(
        self,
        repository: SQLRepository,
        settings: Settings,
        stages: list[Stage],
        trace: TraceSink | None = None,
    ) -> None:
        self.repository = repository
        self.settings = settings
        self.stages = stages
        self.trace = trace

    def load_state(self, run_id: UUID) -> WorkflowState:
        state = WorkflowState.model_validate(self.repository.artifacts(run_id).get("state", {}))
        if state.schema_version != 1:
            raise ValueError("Unsupported checkpoint state schema version")
        return state

    async def resume(self, run_id: UUID) -> ResearchRun:
        lease = RunLease(self.repository, run_id)
        lease.acquire()
        heartbeat = asyncio.create_task(lease.heartbeat())
        try:
            run = self.repository.get_run(run_id)
            if run.workflow_version != 1 or run.config_fingerprint != self.settings.fingerprint():
                raise ValueError(
                    "Run configuration/workflow mismatch; use its original configuration"
                )
            if run.status in ("COMPLETED", "REJECTED"):
                return run
            state = self.load_state(run_id)
            if state.pending_approval:
                return run
            run.status = "RUNNING"
            self.repository.save_run(run)
            state.events.append(WorkflowEvent(run_id=run_id, stage="workflow", event="RESUMED"))
            self.repository.checkpoint(run, {"state": state})
            while run.stage < len(self.stages):
                stage = self.stages[run.stage]
                if heartbeat.done():
                    await heartbeat
                if self.settings.research.human_approval_required:
                    pending = next(
                        (
                            key
                            for key in stage.approvals_before
                            if key not in state.completed_approvals
                        ),
                        None,
                    )
                    if pending:
                        state.pending_approval = pending
                        run.status = "PAUSED"
                        state.events.append(
                            WorkflowEvent(run_id=run_id, stage=stage.name, event="PAUSED")
                        )
                        self.repository.checkpoint(run, {"state": state})
                        return run
                try:
                    state.events.append(
                        WorkflowEvent(run_id=run_id, stage=stage.name, event="STAGE_STARTED")
                    )
                    self.repository.checkpoint(run, {"state": state})
                    next_state = await stage.execute(run, state.model_copy(deep=True))
                except asyncio.CancelledError:
                    run.status = "FAILED"
                    run.warnings.append(
                        f"Stage {stage.name} was cancelled; resume from its checkpoint."
                    )
                    interrupted = self.load_state(run_id)
                    interrupted.events.append(
                        WorkflowEvent(run_id=run_id, stage=stage.name, event="STAGE_FAILED")
                    )
                    self.repository.checkpoint(run, {"state": interrupted})
                    raise
                except Exception as exc:
                    run.status = "FAILED"
                    run.warnings.append(f"Stage {stage.name} failed: {type(exc).__name__}")
                    # Preserve finer checkpoints written within a long-running stage.
                    interrupted = self.load_state(run_id)
                    interrupted.events.append(
                        WorkflowEvent(run_id=run_id, stage=stage.name, event="STAGE_FAILED")
                    )
                    self.repository.checkpoint(run, {"state": interrupted})
                    raise
                state = next_state
                if heartbeat.done():
                    await heartbeat
                run.stage += 1
                state.events.append(
                    WorkflowEvent(run_id=run_id, stage=stage.name, event="STAGE_COMPLETED")
                )
                run.updated_at = utcnow()
                self.repository.checkpoint(run, {"state": state})
                if self.trace:
                    self.trace.emit(
                        TraceEvent(run_id=str(run_id), event=stage.name, status="CHECKPOINTED")
                    )
            run.status = "COMPLETED"
            state.events.append(WorkflowEvent(run_id=run_id, stage="workflow", event="COMPLETED"))
            self.repository.checkpoint(run, {"state": state})
            return run
        finally:
            heartbeat.cancel()
            try:
                with suppress(asyncio.CancelledError):
                    await heartbeat
            finally:
                lease.release()

    def human_decision(
        self, run_id: UUID, action: str, *, modified_question: ResearchQuestion | None = None
    ) -> ResearchRun:
        lease = RunLease(self.repository, run_id)
        lease.acquire()
        try:
            run = self.repository.get_run(run_id)
            state = self.load_state(run_id)
            pending = state.pending_approval
            if not pending or run.status != "PAUSED":
                raise ValueError("Run has no pending human approval")
            if action == "approve":
                state.completed_approvals.append(pending)
                state.pending_approval = None
                run.status = "CREATED"
            elif action == "reject":
                run.status = "REJECTED"
                state.pending_approval = None
            elif action == "modify" and modified_question:
                run.question = modified_question
                run.stage = 0
                run.status = "CREATED"
                state = WorkflowState(
                    warnings=["Human modified the question; dependent stages invalidated."]
                )
            else:
                raise ValueError("Expected approve, reject or modify with a question")
            from research_council.schemas.models import Schema

            class ApprovalRecord(Schema):
                point: str
                action: str
                recorded_at: str
                modified_question: ResearchQuestion | None = None

            record = ApprovalRecord(
                point=pending,
                action=action,
                recorded_at=utcnow().isoformat(),
                modified_question=modified_question,
            )
            self.repository.save("approvals", uuid4(), record, run_id)
            self.repository.checkpoint(run, {"state": state})
            return run
        finally:
            lease.release()
