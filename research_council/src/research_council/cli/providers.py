from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Annotated

import typer
from dotenv import load_dotenv
from rich.console import Console

from research_council.validation.preflight import provider_preflight
from research_council.validation.provider_smoke import provider_smoke


def register_provider_commands(app: typer.Typer) -> None:
    providers = typer.Typer(no_args_is_help=True)
    app.add_typer(providers, name="providers")
    console = Console()

    @providers.command(name="preflight")
    def preflight(
        config: Annotated[Path, typer.Option(help="Operator YAML; never put credentials here.")],
        workspace: Annotated[Path, typer.Option("--workspace", "-w")] = Path(
            "workspace/provider-smoke"
        ),
        live: Annotated[
            bool, typer.Option(help="Request a minimal paid provider smoke only.")
        ] = False,
        confirm_paid_apis: Annotated[
            bool,
            typer.Option(help="Explicitly confirm the separate USD 0.25 maximum smoke budget."),
        ] = False,
    ) -> None:
        """Check configuration without network; BOTH flags opt into a separate provider smoke."""
        if live != confirm_paid_apis:
            raise typer.BadParameter("Provider smoke requires BOTH --live --confirm-paid-apis")
        load_dotenv(dotenv_path=Path(".env"), override=False)
        report = provider_preflight(config)
        console.print_json(report.model_dump_json())
        if not report.ready:
            raise typer.Exit(1)
        if live and confirm_paid_apis:
            try:
                result = asyncio.run(
                    provider_smoke(
                        config, workspace, live=live, confirm_paid_apis=confirm_paid_apis
                    )
                )
            except (RuntimeError, ValueError, OSError):
                console.print(
                    "Provider smoke did not complete. No research workflow or SRL advancement was requested."
                )
                raise typer.Exit(1) from None
            console.print_json(data=result)
            if result["status"] != "COMPLETED":
                raise typer.Exit(1)
