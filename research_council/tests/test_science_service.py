import hashlib
import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from research_council.cli import app
from research_council.validation.report import REPORT_SECTIONS
from research_council.validation.service import live_validation_settings, validate_science


@pytest.mark.parametrize("flags", [{}, {"live": True}, {"confirm_paid_apis": True}])
def test_scientific_preparation_never_instantiates_live_runtime(tmp_path, monkeypatch, flags):
    from research_council.validation import service

    def forbidden(*args, **kwargs):
        raise AssertionError("Preparation may not instantiate providers or a network runtime")

    monkeypatch.setattr(service, "Runtime", forbidden)
    run_id, target = validate_science(tmp_path, **flags)
    report = (target / "LIVE_SCIENTIFIC_VALIDATION.md").read_text(encoding="utf-8")
    assert "LIVE_VALIDATION_NOT_YET_EXECUTED" in report
    assert all(f"{index} {name}" in report for index, name in enumerate(REPORT_SECTIONS, 1))
    metrics = json.loads((target / "scientific_metrics.json").read_text())
    assert metrics["scientific_readiness"]["level"] == 0
    assert metrics["coverage_values"]["seed_paper_recall"] is None
    manifest = json.loads((target / "run_manifest.json").read_text())
    assert all(
        hashlib.sha256((target / name).read_bytes()).hexdigest() == digest
        for name, digest in manifest["files"].items()
    )
    provenance = json.loads((target / "scientific_reproducibility.json").read_text())
    assert len(provenance["prompt_versions"]) == 20
    assert not provenance["model_executions"] and not provenance["live_execution"]
    assert len(provenance["commit_sha"]) == 40
    assert not provenance["curation_is_benchmark_execution"]


def test_prepare_with_unresolved_model_config_does_not_load_keys(tmp_path, monkeypatch):
    from research_council.validation import service

    config = tmp_path / "planned.yaml"
    config.write_text("models: ${UNSET_MODEL}\n")
    monkeypatch.setattr(
        service,
        "load_settings",
        lambda *args: (_ for _ in ()).throw(AssertionError("No execution confirmation")),
    )
    _, target = validate_science(tmp_path, config=config)
    provenance = json.loads((target / "scientific_reproducibility.json").read_text())
    assert provenance["planned_config_sha256"] == hashlib.sha256(config.read_bytes()).hexdigest()


def test_scientific_live_config_and_cli_preparation(tmp_path):
    settings = live_validation_settings(Path("config/phase11.live.example.yaml"))
    assert settings.science_benchmark == "CS_FHSS_DOA_FPGA"
    assert settings.live_research_budget.max_novelty_iterations <= 3
    cli = CliRunner()
    result = cli.invoke(app, ["validate-science", "--workspace", str(tmp_path)])
    assert result.exit_code == 0, result.output
    assert "No live execution requested" in result.output
    report = next((tmp_path / "outputs").glob("*/LIVE_SCIENTIFIC_VALIDATION.md"))
    identity = report.parent.name
    status = cli.invoke(app, ["science-readiness", identity, "--workspace", str(tmp_path)])
    assert status.exit_code == 0 and '"level": 0' in status.output


def test_confirmed_live_requires_real_routes_not_fake_fallback(tmp_path):
    config = tmp_path / "fake.yaml"
    config.write_text("{}")
    with pytest.raises(ValueError, match="real provider"):
        live_validation_settings(config)
