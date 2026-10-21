from __future__ import annotations

import asyncio
import os
from contextlib import suppress
from pathlib import Path
from typing import Annotated
from uuid import UUID

import typer
import yaml
from dotenv import load_dotenv
from rich.console import Console
from rich.table import Table

from research_council.cli.providers import register_provider_commands
from research_council.cli.science import register_science_commands
from research_council.core.config import Settings, load_settings
from research_council.core.orchestration.engine import WorkflowEngine
from research_council.core.orchestration.state import WorkflowState
from research_council.core.runtime import Runtime, create_run, open_repository, settings_for_run
from research_council.exporters import MarkdownExporter
from research_council.schemas.models import Mode, ModelExecution, ResearchQuestion

app = typer.Typer(
    no_args_is_help=True,
    help="Evidence-first scientific research workflows.",
    pretty_exceptions_show_locals=False,
)
models_app = typer.Typer(no_args_is_help=True)
app.add_typer(models_app, name="models")
benchmark_app = typer.Typer(no_args_is_help=True)
app.add_typer(benchmark_app, name="benchmark")
console = Console()
register_science_commands(app)
register_provider_commands(app)
WorkspaceOption = Annotated[Path, typer.Option("--workspace", "-w", help="Project data workspace.")]


def checked_uuid(value: str) -> UUID:
    try:
        return UUID(value)
    except ValueError as exc:
        raise typer.BadParameter("RUN_ID must be a UUID") from exc


@app.command()
def init(workspace: WorkspaceOption = Path("workspace")) -> None:
    """Initialize database migrations and an offline configuration."""
    repo = open_repository(workspace)
    repo.engine.dispose()
    path = workspace / "config.yaml"
    if not path.exists():
        path.write_text(
            yaml.safe_dump(Settings().model_dump(mode="json"), sort_keys=False), encoding="utf-8"
        )
    console.print(f"Initialized Research Council in {workspace.resolve()}")


def execute(run_id: UUID, workspace: Path) -> None:
    repo = open_repository(workspace)
    try:
        settings = settings_for_run(repo, run_id)
        run = repo.get_run(run_id)

        async def work() -> None:
            async with Runtime(workspace, repo, settings, run) as pipeline:
                result = await pipeline.engine(run.mode).resume(run_id)
                state = WorkflowState.model_validate(repo.artifacts(run_id).get("state", {}))
                target = MarkdownExporter(workspace, repo).export(result, state)
                console.print(
                    f"Run {run_id}: {result.status}; stage {result.stage}/{len(pipeline.stages(run.mode))}"
                )
                if state.pending_approval:
                    console.print(f"Pending approval: {state.pending_approval}")
                console.print(f"Reports: {target.resolve()}")

        with console.status("Executing bounded research workflow…"):
            asyncio.run(work())
    except (ValueError, KeyError, RuntimeError) as exc:
        console.print(
            f"[red]Run incomplete: {type(exc).__name__}. Inspect status and trace, then resume.[/red]"
        )
        raise typer.Exit(1) from exc
    finally:
        repo.engine.dispose()


@app.command()
def run(
    topic: Annotated[str | None, typer.Option(help="Research question.")] = None,
    mode: Annotated[Mode, typer.Option()] = Mode.REVIEW,
    workspace: WorkspaceOption = Path("workspace"),
    config: Annotated[Path | None, typer.Option(help="YAML configuration.")] = None,
    project: Annotated[
        Path | None, typer.Option(help="Project YAML, e.g. examples/fhss.yaml.")
    ] = None,
    claim: Annotated[
        str | None, typer.Option(help="Explicit normalized contribution claim for AUDIT.")
    ] = None,
    demo: Annotated[
        bool, typer.Option(help="Use visibly synthetic fixtures; never real findings.")
    ] = False,
    live: Annotated[
        bool, typer.Option(help="Enable configured network search and paid providers.")
    ] = False,
) -> None:
    """Create and execute a research run. Default: honest offline empty-evidence run."""
    load_dotenv()
    config_path = config or (
        Path(os.environ["RESEARCH_COUNCIL_CONFIG"])
        if os.environ.get("RESEARCH_COUNCIL_CONFIG")
        else None
    )
    if config_path is None and (workspace / "config.yaml").is_file():
        config_path = workspace / "config.yaml"
    settings = load_settings(config_path)
    if project:
        raw = yaml.safe_load(project.read_text(encoding="utf-8"))
        question = ResearchQuestion.model_validate(raw["question"])
    elif topic:
        question = ResearchQuestion(topic=topic, audit_claim=claim)
    else:
        raise typer.BadParameter("Supply --topic or --project")
    if claim:
        question.audit_claim = claim
    repo = open_repository(workspace)
    try:
        result = create_run(repo, question, mode, settings, demo=demo, live=live)
    except ValueError as exc:
        raise typer.BadParameter(str(exc)) from exc
    finally:
        repo.engine.dispose()
    console.print(f"Created run: {result.run_id}")
    execute(result.run_id, workspace)


@app.command()
def resume(run_id: str, workspace: WorkspaceOption = Path("workspace")) -> None:
    """Resume using the configuration pinned when the run was created."""
    load_dotenv()
    execute(checked_uuid(run_id), workspace)


@app.command(name="continue")
def continue_run(run_id: str, workspace: WorkspaceOption = Path("workspace")) -> None:
    """Continue completed approvals; this cannot bypass pending approval."""
    execute(checked_uuid(run_id), workspace)


@app.command()
def status(run_id: str, workspace: WorkspaceOption = Path("workspace")) -> None:
    repo = open_repository(workspace)
    try:
        run = repo.get_run(checked_uuid(run_id))
        state = WorkflowState.model_validate(repo.artifacts(run.run_id).get("state", {}))
        usage = repo.list_all("model_executions", ModelExecution, run.run_id)
        console.print_json(
            data={
                "run": run.model_dump(mode="json"),
                "pending_approval": state.pending_approval,
                "papers": len(state.candidates),
                "evidence": len(state.evidence),
                "claims": len(state.claims),
                "novelty_iteration": state.novelty_iteration,
                "model_calls": len(usage),
                "gates": [item.model_dump(mode="json") for item in state.gates],
                "warnings": state.warnings,
            }
        )
    finally:
        repo.engine.dispose()


@app.command()
def export(run_id: str, workspace: WorkspaceOption = Path("workspace")) -> None:
    repo = open_repository(workspace)
    try:
        run = repo.get_run(checked_uuid(run_id))
        state = WorkflowState.model_validate(repo.artifacts(run.run_id).get("state", {}))
        console.print(str(MarkdownExporter(workspace, repo).export(run, state).resolve()))
    finally:
        repo.engine.dispose()


def decision(
    run_id: str, workspace: Path, action: str, modified_question: ResearchQuestion | None = None
) -> None:
    repo = open_repository(workspace)
    try:
        identity = checked_uuid(run_id)
        settings = settings_for_run(repo, identity)
        result = WorkflowEngine(repo, settings, []).human_decision(
            identity, action, modified_question=modified_question
        )
        console.print(f"{result.run_id}: {result.status}; human action: {action}")
    finally:
        repo.engine.dispose()


@app.command()
def approve(run_id: str, workspace: WorkspaceOption = Path("workspace")) -> None:
    decision(run_id, workspace, "approve")


@app.command()
def reject(run_id: str, workspace: WorkspaceOption = Path("workspace")) -> None:
    decision(run_id, workspace, "reject")


@app.command()
def modify(
    run_id: str,
    topic: Annotated[str, typer.Option()],
    workspace: WorkspaceOption = Path("workspace"),
) -> None:
    """Modify the question and invalidate dependent stages/approvals."""
    repo = open_repository(workspace)
    try:
        question = repo.get_run(checked_uuid(run_id)).question
        updated = ResearchQuestion.model_validate({**question.model_dump(), "topic": topic})
    finally:
        repo.engine.dispose()
    decision(run_id, workspace, "modify", updated)


@models_app.command()
def benchmark(
    workspace: WorkspaceOption = Path("workspace"),
    config: Annotated[Path | None, typer.Option()] = None,
    live: Annotated[bool, typer.Option(help="Opt in to billable configured routes.")] = False,
) -> None:
    """Measure route validity/latency/usage without altering routing configuration."""
    from research_council.schemas.models import ResearchPlan, TaskProfile

    settings = load_settings(config)
    repo = open_repository(workspace)
    try:
        # A benchmark does not need literature adapters, but still requires explicit live opt-in.
        providers = {route.provider for routes in settings.models.values() for route in routes}
        if providers - {"fake"} and not live:
            raise typer.BadParameter("Paid benchmark routes require --live")
        question = ResearchQuestion(
            topic="Benchmark structured output only; no scientific findings"
        )
        offline_settings = settings.model_copy(deep=True)
        offline_settings.search.adapters = ["crossref"] if live else []
        result = create_run(repo, question, Mode.QUICK, offline_settings, live=live)

        async def work() -> None:
            async with Runtime(workspace, repo, offline_settings, result) as pipeline:
                for profile in TaskProfile:
                    configured_routes = list(pipeline.router.settings.models.get(profile, []))
                    for route in configured_routes:
                        pipeline.router.settings.models[profile] = [route]
                        try:
                            await pipeline.router.generate(
                                profile,
                                "benchmark",
                                "Return a concise plan in the requested schema.",
                                "Benchmark only.",
                                ResearchPlan,
                            )
                        except (ValueError, RuntimeError):
                            pass
                    pipeline.router.settings.models[profile] = configured_routes

        asyncio.run(work())
        result.status = "COMPLETED"
        result.stage = 2
        repo.save_run(result)
        rows = repo.list_all("model_executions", ModelExecution, result.run_id)
        table = Table("Profile", "Provider/model", "Status", "Latency", "Tokens", "Cost")
        for item in rows:
            table.add_row(
                item.task,
                f"{item.provider}/{item.model}",
                item.status,
                f"{item.latency:.3f}s",
                str(item.input_tokens + item.output_tokens),
                str(item.estimated_cost),
            )
        console.print(table)
        console.print(f"Benchmark run: {result.run_id}")
    finally:
        repo.engine.dispose()


@app.command(name="attest-claim")
def attest_claim_command(
    run_id: str,
    attestation: Annotated[str, typer.Option(help="Workspace-relative JSON attestation file.")],
    workspace: WorkspaceOption = Path("workspace"),
) -> None:
    """Record explicit source/entailment review at the final or scientific after-gaps pause."""
    from research_council.core.human_review import ScientificAttestation, attest_claim
    from research_council.core.security import workspace_path

    repo = open_repository(workspace)
    try:
        source = workspace_path(workspace, attestation)
        if source.stat().st_size > 10_000:
            raise typer.BadParameter("Attestation file is too large")
        review = ScientificAttestation.model_validate_json(source.read_text(encoding="utf-8"))
        state = attest_claim(repo, checked_uuid(run_id), review)
        console.print(
            f"Human review recorded; Gate 3: {'PASS' if state.gates[-1].passed else 'FAIL'}"
        )
    finally:
        repo.engine.dispose()


@app.command(name="evaluate")
def evaluate_command(
    run_id: str,
    workspace: WorkspaceOption = Path("workspace"),
    gold: Annotated[Path | None, typer.Option()] = None,
    human: Annotated[Path | None, typer.Option()] = None,
) -> None:
    """Evaluate measured software metrics and optional independent gold/human labels."""
    from research_council.evaluation import GoldLabels, HumanScores, evaluate
    from research_council.schemas.models import AgentExecution

    repo = open_repository(workspace)
    try:
        identity = checked_uuid(run_id)
        state = WorkflowState.model_validate(repo.artifacts(identity).get("state", {}))
        result = evaluate(
            state,
            repo.list_all("model_executions", ModelExecution, identity),
            repo.list_all("agent_executions", AgentExecution, identity),
            GoldLabels.model_validate_json(gold.read_text(encoding="utf-8")) if gold else None,
            HumanScores.model_validate_json(human.read_text(encoding="utf-8")) if human else None,
        )
        console.print_json(result.model_dump_json())
    finally:
        repo.engine.dispose()


@app.command()
def audit(run_id: str, workspace: WorkspaceOption = Path("workspace")) -> None:
    """Recheck stored evidence/citations and gates without generating model conclusions."""
    from research_council.core.integrity import validate_graph
    from research_council.core.orchestration.engine import RunLease
    from research_council.schemas.models import WorkflowEvent

    load_dotenv()
    repo = open_repository(workspace)
    identity = checked_uuid(run_id)
    lease = RunLease(repo, identity)
    try:
        lease.acquire()
        record = repo.get_run(identity)
        state = WorkflowState.model_validate(repo.artifacts(identity).get("state", {}))
        validate_graph(state)

        async def work() -> None:
            heartbeat = asyncio.create_task(lease.heartbeat())
            try:
                async with Runtime(
                    workspace, repo, settings_for_run(repo, identity), record
                ) as pipeline:
                    await pipeline.audit(record, state)
                if heartbeat.done():
                    await heartbeat
            finally:
                heartbeat.cancel()
                with suppress(asyncio.CancelledError):
                    await heartbeat

        asyncio.run(work())
        state.events.append(
            WorkflowEvent(
                run_id=identity,
                stage="citation_audit",
                event="AUDIT_COMPLETED",
            )
        )
        repo.checkpoint(record, {"state": state})
        target = MarkdownExporter(workspace, repo).export(record, state)
        console.print(
            f"Audit complete; Gate 3: {'PASS' if state.gates[-1].passed else 'FAIL'}; Reports: {target}"
        )
    finally:
        lease.release()
        repo.engine.dispose()


@app.command(name="resolve-conflict")
def resolve_conflict_command(
    run_id: str,
    resolution: Annotated[str, typer.Option(help="Workspace-relative JSON review file.")],
    workspace: WorkspaceOption = Path("workspace"),
) -> None:
    """Record named human conflict resolution while preserving all evidence."""
    from research_council.core.conflict_review import (
        ConflictResolutionRequest,
        resolve_evidence_conflict,
    )
    from research_council.core.security import workspace_path

    repo = open_repository(workspace)
    try:
        path = workspace_path(workspace, resolution)
        if path.stat().st_size > 10_000:
            raise typer.BadParameter("Resolution file is too large")
        request = ConflictResolutionRequest.model_validate_json(path.read_text(encoding="utf-8"))
        resolve_evidence_conflict(repo, checked_uuid(run_id), request)
        console.print(
            "Conflict review recorded; scientific verification remains a separate review."
        )
    finally:
        repo.engine.dispose()


@benchmark_app.command(name="prepare")
def benchmark_prepare(
    workspace: WorkspaceOption = Path("workspace"),
    project: Annotated[Path | None, typer.Option(help="Optional project YAML.")] = None,
) -> None:
    """Prepare the FHSS benchmark without inventing or executing research."""
    from research_council.core.benchmark import prepare_benchmark

    question = (
        ResearchQuestion.model_validate(
            yaml.safe_load(project.read_text(encoding="utf-8"))["question"]
        )
        if project
        else None
    )
    console.print(f"BENCHMARK_READY_BUT_NOT_EXECUTED: {prepare_benchmark(workspace, question)}")
