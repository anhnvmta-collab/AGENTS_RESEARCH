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
        for run in self.repository.list_all("research_runs", ResearchRun):
            try:
                self.project(run.project_id)
            except KeyError:
                self.save_project(
                    StudioProject(
                        id=run.project_id,
                        title=run.question.topic[:200],
                        topic=run.question.topic,
                        constraints=run.question.constraints,
                        practice=run.provenance != "live",
                        mode=run.mode,
                        budget=run.budget_usd,
                    )
                )

    def new_run(self, identity: UUID, confirmation: str = "") -> dict[str, Any]:
        project = self.project(identity)
        if project.mode.value == "audit" and not project.audit_claim:
            from research_council.studio.models import StudioError

            raise StudioError("AUDIT requires an explicit contribution claim")
        settings = Settings()
        if not project.practice:
            from research_council.studio.settings import current, preflight

            settings = current(self)
            if (
                confirmation != "START REAL RESEARCH"
                or not preflight(self, identity, settings)["ready"]
            ):
                raise ValueError("Real mode requires successful preflight and START REAL RESEARCH")
            if project.providers:
                for routes in [*settings.models.values(), *settings.role_routes.values()]:
                    for route in routes:
                        if route.provider not in project.providers:
                            route.enabled = False
            if settings.live_research_budget:
                cap = settings.live_research_budget
                cap.max_total_cost = min(cap.max_total_cost, project.budget)
                cap.max_core_papers = min(cap.max_core_papers, project.max_papers)
                settings.research.budget_usd = min(settings.research.budget_usd, cap.max_total_cost)
                settings.research.max_model_calls = min(
                    settings.research.max_model_calls, cap.max_model_calls
                )
                settings.research.max_core_papers = min(
                    settings.research.max_core_papers, cap.max_core_papers
                )
        settings.research.human_approval_required = True
        settings.research.max_core_papers = min(
            settings.research.max_core_papers, project.max_papers
        )
        settings.research.budget_usd = min(settings.research.budget_usd, project.budget)
        settings.search.local_documents = [
            item["path"]
            for item in self.store.list("document")
            if item["project_id"] == str(identity) and item["status"] == "PARSED"
        ]
        question = ResearchQuestion(
            topic=project.topic,
            audit_claim=project.audit_claim,
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
            demo=project.practice,
            live=not project.practice,
            confirm_paid_apis=not project.practice,
            project=ResearchProject(project_id=identity, title=project.title, question=question),
        )
        self.repository.checkpoint(run, {"state": WorkflowState()})
        if not project.practice:
            self.store.put(
                "real_consent",
                str(run.run_id),
                {"confirmation": "START REAL RESEARCH", "at": utcnow().isoformat()},
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
        if run.provenance == "live":
            self.store.get("real_consent", str(identity))
        if run.stage == 0 and not self.repository.list_model_executions(identity):
            settings = settings_for_run(self.repository, identity)
            settings.search.local_documents = [
                row["path"]
                for row in self.store.list("document")
                if row["project_id"] == str(run.project_id) and row["status"] == "PARSED"
            ]
            run.config_fingerprint = settings.fingerprint()
            self.repository.checkpoint(run, {"settings": settings})
        self.store.put("control", str(identity), {"command": None})
        self.store.put("worker_error", str(identity), {"run_id": str(identity), "resolved": True})
        self.jobs[identity] = asyncio.create_task(self.execute(identity))
        return self.snapshot(identity)

    async def execute(self, identity: UUID) -> None:
        run = self.repository.get_run(identity)
        try:
            settings = settings_for_run(self.repository, identity)
            async with Runtime(
                self.workspace, self.repository, settings, run, fixture_delay_seconds=0.15
            ) as pipeline:
                engine = pipeline.engine(run.mode)
                # Extra Studio review points supplement the existing engine approvals.
                stages = []
                plan_action = engine.stages[0].execute

                async def studio_plan(record: ResearchRun, current: WorkflowState) -> WorkflowState:
                    from research_council.agents.contracts import QuestionInput
                    from research_council.agents.research_director import ResearchDirector

                    await pipeline.call(
                        ResearchDirector,
                        QuestionInput(
                            task="Recommend bounded research depth; requested mode remains authoritative.",
                            question=record.question,
                            mode=record.mode,
                        ),
                    )
                    return await plan_action(record, current)

                for stage in engine.stages:
                    approvals = stage.approvals_before
                    if stage.name == "analysis":
                        approvals += ("after_core_selection",)
                    if stage.name == "audit" and run.mode.value in {"deep", "novelty"}:
                        approvals += ("after_experiment_plan",)
                    stages.append(
                        Stage(
                            stage.name,
                            studio_plan if stage.name == "plan" else stage.execute,
                            approvals,
                        )
                    )
                engine.stages = stages
                self.store.put("stages", str(identity), {"names": [stage.name for stage in stages]})
                engine.control = lambda: self.command(identity)
                result = await engine.resume(identity)
                state = engine.load_state(identity)
                MarkdownExporter(self.workspace, self.repository).export(result, state)
                for document in self.store.list("document"):
                    if document["project_id"] == str(run.project_id) and any(
                        str(c.paper.paper_id) == document.get("paper_id") for c in state.candidates
                    ):
                        document.update(job_status="COMPLETED", run_id=str(identity))
                        self.store.put("document", document["id"], document)
            if (
                run.provenance == "fixture"
                and state.pending_approval == "after_experiment_plan"
                and not state.experiments
            ):
                # Gate 2 correctly prevents canonical experiment adoption for fixtures.
                # Execute the real roles as visibly advisory learning artifacts instead.
                from research_council.studio.interactions import discuss
                from research_council.studio.models import Interaction

                previous = [
                    item
                    for item in self.store.list("practice_design")
                    if item["run_id"] == str(identity)
                    and item.get("question") == run.question.model_dump(mode="json")
                ]
                if not previous:
                    experiment = await discuss(
                        self,
                        "ExperimentDesigner",
                        Interaction(
                            run_id=identity,
                            task="Create an exploratory SYNTHETIC experiment plan. Gate 2 is blocked; do not claim accepted novelty or measured results.",
                        ),
                    )
                    paper = await discuss(
                        self,
                        "PaperArchitect",
                        Interaction(
                            run_id=identity,
                            task="Create a SYNTHETIC exploratory IEEE roadmap; no publication readiness.",
                            input={
                                "experiments": [experiment["output"]],
                                "claims": [item.model_dump(mode="json") for item in state.claims],
                                "limitations": state.limitations,
                            },
                        ),
                    )
                    self.store.put(
                        "practice_design",
                        str(identity),
                        {
                            "run_id": str(identity),
                            "question": run.question.model_dump(mode="json"),
                            "experiments": [experiment["output"]],
                            "outline": paper["output"],
                            "scope": "ADVISORY_SYNTHETIC",
                            "reason": "Canonical Gate 2 remains blocked. These real agent executions are learning artifacts, not accepted scientific contributions.",
                        },
                    )
        except Exception as exc:
            self.store.put(
                "worker_error",
                str(identity),
                {
                    "run_id": str(identity),
                    "error_type": type(exc).__name__,
                    "at": utcnow().isoformat(),
                },
            )

    def control(self, identity: UUID, command: str) -> dict[str, Any]:
        self.repository.get_run(identity)
        self.store.put(
            "control", str(identity), {"command": command, "requested_at": utcnow().isoformat()}
        )
        return {"command": command, "checkpoint_boundary": True}

    def decide(self, identity: UUID, decision: Decision) -> dict[str, Any]:
        if identity in self.jobs and not self.jobs[identity].done():
            raise RuntimeError("Wait for the active checkpoint operation")
        run = self.repository.get_run(identity)
        point = self.repository.artifacts(identity).get("state", {}).get("pending_approval")
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
                "point": point,
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
        from research_council.knowledge.mapping import build_knowledge_map

        run = self.repository.get_run(identity)
        state = WorkflowState.model_validate(self.repository.artifacts(identity).get("state", {}))
        practice_design = next(
            (
                row
                for row in self.store.list("practice_design")
                if row["run_id"] == str(identity)
                and row.get("question") == run.question.model_dump(mode="json")
            ),
            None,
        )
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
            "operations": {
                key.removeprefix("operation_"): value
                for key, value in self.repository.artifacts(identity).items()
                if key.startswith("operation_")
            },
            "control": self.command(identity),
            "worker_active": identity in self.jobs and not self.jobs[identity].done(),
            "observed_map": (
                state.knowledge_map or build_knowledge_map(run.question.topic, state)
            ).model_dump(mode="json"),
            "practice_design": practice_design,
            "worker_error": next(
                (
                    row
                    for row in self.store.list("worker_error")
                    if row.get("run_id") == str(identity) and not row.get("resolved")
                ),
                None,
            ),
        }

    def agents(self, identity: UUID) -> list[dict[str, Any]]:
        from research_council import agents
        from research_council.studio.interactions import agent_class

        snapshot = self.snapshot(identity)
        settings = settings_for_run(self.repository, identity)
        result = []
        for name in agents.__all__:
            role = agent_class(name)
            executions = [item for item in snapshot["executions"] if item["agent_id"] == name]
            models = [item for item in snapshot["models"] if item["agent_id"] == name]
            routes = [
                route.model_dump(mode="json")
                for route in settings.role_routes.get(name, settings.models[role.task_profile])
                if route.enabled
            ]
            latest = executions[-1] if executions else None
            status = (
                "COMPLETED"
                if latest and latest["status"] == "SUCCESS"
                else latest["status"]
                if latest
                else "IDLE"
            )
            try:
                stage_names = self.store.get("stages", str(identity))["names"]
            except KeyError:
                stage_names = []
            stage_index = snapshot["run"]["stage"]
            stage_name = stage_names[stage_index] if stage_index < len(stage_names) else ""
            role_stages = {
                "plan": ["ResearchDirector", "ResearchPlanner"],
                "discovery": [
                    "PerspectiveGenerator",
                    "QueryPlanner",
                    "PaperScout",
                    "CitationScout",
                    "LocalDocumentScout",
                    "PaperTriage",
                ],
                "analysis": ["DeepReader", "MathDSPAnalyst", "HardwareArchitect"],
                "gaps": ["GapMiner"],
                "novelty": ["NoveltyGenerator", "PriorArtHunter", "ReviewerTwo", "NoveltyJudge"],
                "experiments": ["ExperimentDesigner", "PaperArchitect"],
                "audit": ["CitationAuditor"],
                "synthesis": ["FinalSynthesizer"],
            }
            if snapshot["state"]["pending_approval"] and name in role_stages.get(stage_name, []):
                status = "WAITING_FOR_HUMAN"
            elif status == "RUNNING" and models and models[-1]["retry_count"] > 0:
                status = "RETRYING"
            for execution in executions:
                if not execution["end_time"]:
                    from datetime import datetime

                    execution["elapsed_seconds"] = (
                        utcnow()
                        - datetime.fromisoformat(execution["start_time"].replace("Z", "+00:00"))
                    ).total_seconds()
            result.append(
                {
                    "name": name,
                    "role": role.role,
                    "profile": role.task_profile.value,
                    "routes": routes,
                    "status": status,
                    "current_route": models[-1] if models else routes[0] if routes else {},
                    "tasks_completed": sum(item["status"] == "SUCCESS" for item in executions),
                    "average_latency": sum(item["latency"] for item in executions)
                    / max(1, len(executions)),
                    "cost": sum(item["estimated_cost"] or 0 for item in models),
                    "errors": sum(item["status"] == "FAILED" for item in executions),
                    "allowed_tools": sorted(role.allowed_tools),
                    "input_contract": role.input_schema.model_json_schema(),
                    "output_contract": role.output_schema.model_json_schema(),
                    "executions": executions,
                    "models": models,
                    "operations": {
                        item["execution_id"]: snapshot["operations"].get(item["execution_id"], {})
                        for item in executions
                    },
                    "related_evidence": [
                        item
                        for item in snapshot["state"]["evidence"]
                        if item["extraction_agent"] == name
                    ],
                }
            )
        return result

    def dashboard(self) -> dict[str, Any]:
        runs = self.repository.list_all("research_runs", ResearchRun)
        states = [self.snapshot(run.run_id) for run in runs]
        return {
            "projects": self.store.list("project"),
            "runs": [item["run"] for item in reversed(states)],
            "papers": sum(len(item["state"]["candidates"]) for item in states),
            "evidence": sum(len(item["state"]["evidence"]) for item in states),
            "novelty": sum(
                len({n["candidate_id"] for n in item["state"]["novelty_candidates"]})
                for item in states
            ),
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
