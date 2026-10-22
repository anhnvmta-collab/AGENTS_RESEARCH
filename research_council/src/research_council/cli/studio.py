import json
from pathlib import Path
from typing import Annotated

import typer


def register_studio_commands(app: typer.Typer) -> None:
    studio = typer.Typer(invoke_without_command=True)
    app.add_typer(studio, name="studio")

    def serve(workspace: Path, port: int) -> None:
        import uvicorn
        from dotenv import load_dotenv

        from research_council.studio.app import create_app

        load_dotenv()
        uvicorn.run(
            create_app(workspace, origin=f"http://127.0.0.1:{port}"), host="127.0.0.1", port=port
        )

    @studio.callback()
    def studio_main(
        ctx: typer.Context,
        workspace: Annotated[Path, typer.Option()] = Path("workspace/studio"),
        port: Annotated[int, typer.Option(min=1024, max=65535)] = 8765,
    ) -> None:
        """Launch the local scientific workspace (build frontend first)."""
        if ctx.invoked_subcommand is None:
            serve(workspace, port)

    @studio.command()
    def backend(
        workspace: Annotated[Path, typer.Option()] = Path("workspace/studio"),
        port: Annotated[int, typer.Option(min=1024, max=65535)] = 8765,
    ) -> None:
        """Start the loopback API for the Vite development client."""
        serve(workspace, port)

    @studio.command("prepare-pilot")
    def prepare_pilot(
        workspace: Annotated[Path, typer.Option()] = Path("workspace/studio-pilot01"),
        project: Annotated[Path, typer.Option()] = Path("config/pilot01.project.yaml"),
        config: Annotated[Path | None, typer.Option()] = None,
    ) -> None:
        """Import a project and optionally validated settings offline; never create/start a run."""
        import yaml
        from dotenv import load_dotenv
        from pydantic import ValidationError

        from research_council.core.config import load_settings
        from research_council.studio.models import StudioProject
        from research_council.studio.service import StudioService
        from research_council.studio.settings import save, validate

        load_dotenv()
        try:
            prepared = StudioProject.model_validate(
                yaml.safe_load(project.read_text(encoding="utf-8"))
            )
            settings = load_settings(config) if config else None
            if settings and validate(settings):
                raise ValueError("Configuration blocked")
        except (OSError, ValueError, TypeError, ValidationError, yaml.YAMLError):
            typer.echo(
                "Project/configuration blocked; review syntax, model-ID variables and token prices."
            )
            raise typer.Exit(1) from None
        service = StudioService(workspace)
        try:
            existing = any(row["id"] == str(prepared.id) for row in service.store.list("project"))
            if not existing:
                service.save_project(prepared)
            if settings:
                save(service, settings)
            typer.echo(
                json.dumps(
                    {
                        "project_id": str(prepared.id),
                        "project_status": "EXISTS_PRESERVED" if existing else "IMPORTED",
                        "settings_status": "APPLIED_CONFIGURATION_ONLY"
                        if settings
                        else "UNCHANGED",
                        "workspace": str(service.workspace),
                        "run_created": False,
                        "paid_calls": 0,
                        "live_pilot_executed": False,
                        "srl": 0,
                    }
                )
            )
        finally:
            service.repository.engine.dispose()
