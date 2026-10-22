from __future__ import annotations

from pathlib import Path
from typing import Any
from uuid import UUID

from research_council.core.orchestration.state import WorkflowState
from research_council.core.runtime import open_repository
from research_council.schemas.models import AgentExecution, ModelExecution, ResearchRun
from research_council.studio.models import StudioProject
from research_council.studio.store import StudioStore


class StudioService:
    def __init__(self, workspace: Path) -> None:
        self.workspace = workspace.resolve()
        self.repository = open_repository(self.workspace)
        self.store = StudioStore(self.workspace)

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
