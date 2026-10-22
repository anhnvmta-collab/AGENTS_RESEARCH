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
