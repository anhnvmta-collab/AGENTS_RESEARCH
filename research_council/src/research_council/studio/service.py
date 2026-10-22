from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any
from uuid import UUID, uuid4

from research_council.core.config import Settings
from research_council.core.orchestration.engine import Stage, WorkflowEngine
from research_council.core.orchestration.state import WorkflowState
from research_council.core.runtime import Runtime, create_run, open_repository, settings_for_run
from research_council.exporters import MarkdownExporter
from research_council.schemas.models import (
    AgentExecution,
    ModelExecution,
    ResearchProject,
    ResearchQuestion,
    ResearchRun,
    utcnow,
)
from research_council.studio.models import Decision, StudioProject
from research_council.studio.store import StudioStore


class StudioService:
    def __init__(self, workspace: Path) -> None:
        self.workspace = workspace.resolve()
        self.repository = open_repository(self.workspace)
        self.store = StudioStore(self.workspace)
        self.jobs: dict[UUID, asyncio.Task[None]] = {}

    def new_run(self, identity: UUID, confirmation: str = "") -> dict[str, Any]:
        project = self.project(identity)
        if not project.practice:
            raise ValueError("Real mode requires provider preflight and explicit confirmation")
        settings = Settings()
        settings.research.human_approval_required = True
        settings.research.max_core_papers = project.max_papers
        settings.research.budget_usd = project.budget
        settings.search.local_documents = [
            item["path"]
            for item in self.store.list("document")
            if item["project_id"] == str(identity) and item["status"] == "PARSED"
        ]
        question = ResearchQuestion(
            topic=project.topic,
            constraints=[
                *project.constraints,
                *project.questions,
                project.objective,
                project.hardware_constraints,
                project.notes,
                f"Domain: {project.domain}; keywords: {', '.join(project.keywords)}; dates: {project.date_range}",
                f"Target: {project.target_journal}; publication: {project.publication_type}",
            ],
        )
        run = create_run(
            self.repository,
            question,
            project.mode,
            settings,
            demo=True,
            project=ResearchProject(project_id=identity, title=project.title, question=question),
        )
        return self.snapshot(run.run_id)

    def command(self, identity: UUID) -> str | None:
        try:
            return self.store.get("control", str(identity)).get("command")
        except KeyError:
            return None

    async def start(self, identity: UUID) -> dict[str, Any]:
        run = self.repository.get_run(identity)
        if identity in self.jobs and not self.jobs[identity].done():
            raise RuntimeError("Run is already executing")
        if run.status in {"COMPLETED", "REJECTED", "BUDGET_EXHAUSTED"}:
            raise ValueError("Terminal run cannot resume")
        self.store.put("control", str(identity), {"command": None})
        self.jobs[identity] = asyncio.create_task(self.execute(identity))
        return self.snapshot(identity)

    async def execute(self, identity: UUID) -> None:
        run = self.repository.get_run(identity)
        try:
            settings = settings_for_run(self.repository, identity)
            async with Runtime(self.workspace, self.repository, settings, run) as pipeline:
                engine = pipeline.engine(run.mode)
                # Extra Studio review points supplement the existing engine approvals.
                stages = []
                for stage in engine.stages:
                    approvals = stage.approvals_before
                    if stage.name == "analysis":
                        approvals += ("after_core_selection",)
                    if stage.name == "audit" and run.mode.value in {"deep", "novelty"}:
                        approvals += ("after_experiment_plan",)
                    stages.append(Stage(stage.name, stage.execute, approvals))
                engine.stages = stages
                engine.control = lambda: self.command(identity)
                result = await engine.resume(identity)
                state = engine.load_state(identity)
                MarkdownExporter(self.workspace, self.repository).export(result, state)
        except Exception as exc:
            self.store.put(
                "worker_error",
                str(identity),
                {"error_type": type(exc).__name__, "at": utcnow().isoformat()},
            )

    def control(self, identity: UUID, command: str) -> dict[str, Any]:
        self.repository.get_run(identity)
        self.store.put(
            "control", str(identity), {"command": command, "requested_at": utcnow().isoformat()}
        )
        return {"command": command, "checkpoint_boundary": True}

    def decide(self, identity: UUID, decision: Decision) -> dict[str, Any]:
        run = self.repository.get_run(identity)
        settings = settings_for_run(self.repository, identity)
        question = None
        if decision.action == "revise":
            if not decision.comment.strip():
                raise ValueError("Revision requires instructions")
            question = run.question.model_copy(deep=True)
            question.constraints.append("Human revision request: " + decision.comment)
        WorkflowEngine(self.repository, settings, []).human_decision(
            identity,
            "modify" if decision.action == "revise" else decision.action,
            modified_question=question,
        )
        self.store.put(
            "decision",
            str(uuid4()),
            {
                **decision.model_dump(mode="json"),
                "run_id": str(identity),
                "at": utcnow().isoformat(),
            },
        )
        return self.snapshot(identity)

    def project(self, identity: UUID) -> StudioProject:
        return StudioProject.model_validate(self.store.get("project", str(identity)))

    def save_project(self, project: StudioProject) -> dict[str, Any]:
        return self.store.put("project", str(project.id), project.model_dump(mode="json"))

    def snapshot(self, identity: UUID) -> dict[str, Any]:
        run = self.repository.get_run(identity)
        state = WorkflowState.model_validate(self.repository.artifacts(identity).get("state", {}))
        return {
            "run": run.model_dump(mode="json"),
            "state": state.model_dump(mode="json"),
            "executions": [
                item.model_dump(mode="json")
                for item in self.repository.list_all("agent_executions", AgentExecution, identity)
            ],
            "models": [
                item.model_dump(mode="json")
                for item in self.repository.list_model_executions(identity)
            ],
            "srl": "SRL-0",  # Studio cannot attest scientific readiness.
        }

    def dashboard(self) -> dict[str, Any]:
        runs = self.repository.list_all("research_runs", ResearchRun)
        states = [self.snapshot(run.run_id) for run in runs]
        return {
            "projects": self.store.list("project"),
            "runs": [item["run"] for item in reversed(states)],
            "papers": sum(len(item["state"]["candidates"]) for item in states),
            "evidence": sum(len(item["state"]["evidence"]) for item in states),
            "novelty": sum(len(item["state"]["novelty_candidates"]) for item in states),
            "reviews": sum(bool(item["state"]["pending_approval"]) for item in states),
            "running_agents": sum(
                row["status"] == "RUNNING" for item in states for row in item["executions"]
            ),
            "cost": sum(
                row.estimated_cost or 0
                for run in runs
                for row in self.repository.list_all("model_executions", ModelExecution, run.run_id)
            ),
            "srl": "SRL-0",
        }
