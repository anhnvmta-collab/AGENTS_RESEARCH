import json
from uuid import UUID

from typer.testing import CliRunner

from research_council.cli import app
from research_council.core.runtime import open_repository
from research_council.schemas.models import ResearchRun

runner = CliRunner()


def test_cli_lifecycle(tmp_path):
    workspace = str(tmp_path)
    assert runner.invoke(app, ["init", "--workspace", workspace]).exit_code == 0
    result = runner.invoke(
        app,
        [
            "run",
            "--topic",
            "Synthetic CLI workflow",
            "--mode",
            "deep",
            "--demo",
            "--workspace",
            workspace,
        ],
    )
    assert result.exit_code == 0, result.output
    repo = open_repository(tmp_path)
    run = repo.list_all("research_runs", ResearchRun)[0]
    repo.engine.dispose()
    for command in ("status", "resume", "audit", "export", "evaluate"):
        output = runner.invoke(app, [command, str(run.run_id), "--workspace", workspace])
        assert output.exit_code == 0, output.output
    repo = open_repository(tmp_path)
    state = repo.artifacts(run.run_id)["state"]
    assert state["events"][-1]["event"] == "AUDIT_COMPLETED"
    assert len(state["audits"]) == 4  # Initial and repeated audits retained.
    repo.engine.dispose()
    manifest = next((tmp_path / "outputs").glob("*/run_manifest.json"))
    assert not json.loads(manifest.read_text())["publication_ready"]
    benchmark = runner.invoke(app, ["models", "benchmark", "--workspace", workspace])
    assert benchmark.exit_code == 0, benchmark.output
    prepared = runner.invoke(app, ["benchmark", "prepare", "--workspace", workspace])
    assert prepared.exit_code == 0, prepared.output
    payload = json.loads((tmp_path / "benchmarks/fhss/preparation.json").read_text())
    assert payload["status"] == "BENCHMARK_READY_BUT_NOT_EXECUTED"
    assert not payload["findings"] and not payload["measured_results"]


def test_cli_human_approval_flow(tmp_path):
    from research_council.core.config import Settings

    settings = Settings()
    settings.research.human_approval_required = True
    config = tmp_path / "config.yaml"
    config.write_text(json.dumps(settings.model_dump(mode="json")))
    result = runner.invoke(
        app,
        [
            "run",
            "--topic",
            "Human review system test",
            "--mode",
            "quick",
            "--config",
            str(config),
            "--workspace",
            str(tmp_path),
        ],
    )
    assert result.exit_code == 0, result.output
    repo = open_repository(tmp_path)
    run_id = repo.list_all("research_runs", ResearchRun)[0].run_id
    assert isinstance(run_id, UUID)
    repo.engine.dispose()
    for expected in ("after_plan", "before_final_report"):
        paused = runner.invoke(app, ["continue", str(run_id), "--workspace", str(tmp_path)])
        assert expected in paused.output
        assert (
            runner.invoke(app, ["approve", str(run_id), "--workspace", str(tmp_path)]).exit_code
            == 0
        )
        assert (
            runner.invoke(app, ["continue", str(run_id), "--workspace", str(tmp_path)]).exit_code
            == 0
        )
