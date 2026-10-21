from __future__ import annotations

from pathlib import Path
from typing import Annotated
from uuid import UUID

import typer
import yaml
from dotenv import load_dotenv
from rich.console import Console

from research_council.schemas.models import Mode, ResearchQuestion
from research_council.validation.service import review_readiness, validate_science


def register_science_commands(app: typer.Typer) -> None:
    console = Console()

    @app.command(name="validate-science")
    def validate_science_command(
        workspace: Annotated[Path, typer.Option("--workspace", "-w")] = Path("workspace"),
        project: Annotated[Path | None, typer.Option()] = None,
        config: Annotated[Path | None, typer.Option()] = None,
        live: Annotated[
            bool, typer.Option(help="Request real scientific service execution.")
        ] = False,
        confirm_paid_apis: Annotated[
            bool,
            typer.Option(help="Explicitly authorize the configured bounded paid API operations."),
        ] = False,
        resume: Annotated[
            UUID | None,
            typer.Option(
                help="Resume a scientific run, or refresh reports without both execution flags."
            ),
        ] = None,
        human_reviews: Annotated[
            str | None,
            typer.Option(help="Workspace-relative independently completed JSON review bundle."),
        ] = None,
        mode: Annotated[Mode, typer.Option()] = Mode.NOVELTY,
    ) -> None:
        """Prepare scientific validation; execute only with BOTH paid opt-in flags."""
        if live and confirm_paid_apis:
            load_dotenv()
        question = (
            ResearchQuestion.model_validate(
                yaml.safe_load(project.read_text(encoding="utf-8"))["question"]
            )
            if project
            else None
        )
        try:
            run_id, target = validate_science(
                workspace,
                question=question,
                config=config,
                live=live,
                confirm_paid_apis=confirm_paid_apis,
                resume_id=resume,
                human_reviews=human_reviews,
                mode=mode,
            )
        except (ValueError, RuntimeError, KeyError) as exc:
            raise typer.BadParameter(str(exc)) from exc
        console.print(f"PHASE_11_IMPLEMENTED; run {run_id}; reports: {target.resolve()}")
        if not (live and confirm_paid_apis):
            console.print(
                "No live execution requested. Preparation/report refresh only; SRL is never advanced automatically."
            )

    @app.command(name="science-readiness")
    def science_readiness_command(
        run_id: UUID,
        workspace: Annotated[Path, typer.Option("--workspace", "-w")] = Path("workspace"),
        proof: Annotated[
            str | None,
            typer.Option(help="Workspace-relative evidence request; omission reads current SRL."),
        ] = None,
    ) -> None:
        """Inspect SRL or request one evidence-backed operator-reviewed advancement."""
        try:
            record = review_readiness(workspace, run_id, proof)
        except (ValueError, RuntimeError, KeyError) as exc:
            raise typer.BadParameter(str(exc)) from exc
        console.print_json(record.model_dump_json())
