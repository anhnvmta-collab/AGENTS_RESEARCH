import json
from pathlib import Path
from uuid import UUID

import pytest
import yaml
from test_novelty import candidate_and_evidence
from test_regressions import human_ready_state
from typer.testing import CliRunner

from research_council.cli import app
from research_council.core.config import Route, Settings, load_settings
from research_council.core.orchestration.engine import Stage, WorkflowEngine
from research_council.core.orchestration.novelty import NoveltyLoop
from research_council.core.orchestration.state import WorkflowState
from research_council.core.routing import ModelRouter
from research_council.core.runtime import settings_for_run
from research_council.providers.fake import FakeProvider
from research_council.schemas.models import (
    Gap,
    GapType,
    ModelExecution,
    NoveltyDecision,
    PriorArtReport,
    ResearchPlan,
    ResearchRun,
    ReviewerReport,
    TaskProfile,
)
from research_council.studio.models import Decision, StudioProject
from research_council.studio.service import StudioService
from research_council.studio.settings import preflight, readiness, validate
from research_council.validation.preflight import provider_preflight


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    async def forbidden(*args, **kwargs):
        raise AssertionError("Pilot preparation must remain offline")

    monkeypatch.setattr("httpx.AsyncClient.send", forbidden)


@pytest.mark.parametrize("verdict", ["REVISE", "REJECT"])
async def test_pilot_reviews_every_revision_and_resume_does_not_repeat_work(repository, verdict):
    repo, run = repository
    settings = Settings.model_validate(
        {"research": {"human_approval_required": True, "novelty_review_each_revision": True}}
    )
    run.config_fingerprint = settings.fingerprint()
    repo.save_run(run)
    candidate, _ = candidate_and_evidence()
    state = human_ready_state()
    state.pending_approval = None
    gap = Gap(
        gap_type=GapType.ALGORITHMIC,
        evidence_ids=[state.evidence[0].evidence_id],
        limitation="Fixture limitation",
        consequence="Fixture consequence",
        opportunity="Fixture opportunity",
        search_scope="Offline fixture only",
    )
    state.gaps = [gap]
    candidate.gap_ids = [gap.gap_id]
    candidate.evidence_ids = [state.evidence[0].evidence_id]
    repo.checkpoint(run, {"state": state})
    generated, searched = [], []

    class Operations:
        async def generate(self, state, iteration):
            generated.append(iteration)
            return [candidate.model_copy(update={"revision": iteration})]

        async def prior_art(self, candidate, state):
            return PriorArtReport(candidate_id=candidate.candidate_id, revision=candidate.revision)

        async def review(self, candidate, state):
            return ReviewerReport(candidate_id=candidate.candidate_id, revision=candidate.revision)

        async def judge(self, candidate, prior, review, state):
            return NoveltyDecision(
                candidate_id=candidate.candidate_id,
                revision=candidate.revision,
                verdict=verdict,
                required_followup_searches=["targeted"] if verdict == "REVISE" else [],
            )

        async def targeted_search(self, queries, state):
            searched.append(list(queries))
            return state

    async def novelty(run, state):
        return await NoveltyLoop(Operations(), review_each_revision=True).run(state)

    engine = WorkflowEngine(repo, settings, [Stage("novelty", novelty)])
    revisions = [1, 2, 3] if verdict == "REVISE" else [1]
    for revision in revisions:
        result = await engine.resume(run.run_id)
        assert result.status == "PAUSED" and result.stage == 0
        state = engine.load_state(run.run_id)
        point = f"novelty_{'candidate' if revision == 1 else 'revision'}_review_{revision}"
        assert state.pending_approval == point
        assert generated == list(range(1, revision + 1))
        assert len(searched) == revision - 1
        await engine.resume(run.run_id)
        assert generated == list(range(1, revision + 1))
        engine.human_decision(run.run_id, "approve")
    assert (await engine.resume(run.run_id)).status == "COMPLETED"
    assert generated == revisions and len(searched) == len(revisions) - 1
    expected = "UNRESOLVED" if verdict == "REVISE" else "REJECT"
    assert all(d.verdict == expected for d in engine.load_state(run.run_id).decisions)
    assert not any(g.passed for g in engine.load_state(run.run_id).gates)


@pytest.mark.parametrize("unavailable", [True, False])
async def test_fallback_reason_is_persisted_without_provider_error_payload(repository, unavailable):
    repo, run = repository
    settings = Settings(retries=0)
    settings.models[TaskProfile.SEARCH_PLANNING] = [Route(provider="missing"), Route()]
    providers = {"fake": FakeProvider()}
    if not unavailable:
        failing = FakeProvider([ValueError("secret-provider-payload")])
        providers["missing"] = failing
        settings.models[TaskProfile.SEARCH_PLANNING][0].provider = "failing"
        providers["failing"] = failing
        settings.models[TaskProfile.SEARCH_PLANNING][0].input_cost_per_million = 0
        settings.models[TaskProfile.SEARCH_PLANNING][0].output_cost_per_million = 0
    router = ModelRouter(settings, providers, repo, run.run_id)
    await router.generate(
        TaskProfile.SEARCH_PLANNING, "ResearchPlanner", "rules", "input", ResearchPlan
    )
    records = repo.list_model_executions(run.run_id)
    expected = (
        "ROUTE_FALLBACK:missing:PROVIDER_UNAVAILABLE"
        if unavailable
        else "ROUTE_FALLBACK:failing:ValueError"
    )
    assert router.last_success["ResearchPlanner"].routing_note == expected
    assert "secret-provider-payload" not in "".join(r.model_dump_json() for r in records)


async def test_checkpointed_review_restores_paused_status_after_interruption(repository):
    repo, run = repository
    run.status = "RUNNING"
    repo.checkpoint(run, {"state": WorkflowState(pending_approval="novelty_candidate_review_1")})
    engine = WorkflowEngine(repo, Settings(), [])
    assert (await engine.resume(run.run_id)).status == "PAUSED"
    assert engine.load_state(run.run_id).pending_approval == "novelty_candidate_review_1"
    assert engine.human_decision(run.run_id, "reject").status == "REJECTED"


def test_preflight_discloses_role_overrides_and_six_unverified_services(tmp_path):
    service = StudioService(tmp_path)
    project = StudioProject(title="Pilot 01", topic="Pilot 01", practice=False)
    service.save_project(project)
    settings = Settings(
        role_routes={"PaperScout": [Route(provider="openai", model="operator-model")]}
    )
    report = preflight(service, project.id, settings)
    assert report["role_routes"]["PaperScout"][0]["provider"] == "openai"
    blocked = {row["agent"]: row for row in report["anthropic_blocked_roles"]}
    assert set(blocked) == {"PaperScout", "CitationScout", "LocalDocumentScout", "PriorArtHunter"}
    assert blocked["PaperScout"]["routes"][0]["provider"] == "openai"
    assert {r["service"] for r in report["readiness"]} == {
        "openai",
        "anthropic",
        "google",
        "crossref",
        "openalex",
        "arxiv",
    }
    assert all(r["access_status"] == "NOT_TESTED" for r in report["readiness"])
    assert report["human_approval_required"] is False
    service.repository.engine.dispose()


ROOT = Path(__file__).resolve().parents[1]


def test_pilot_template_has_explicit_routes_caps_and_account_model_placeholders(tmp_path):
    env = {
        p.upper() + "_MODEL_ID": "offline-contract-" + p for p in ("openai", "anthropic", "google")
    }
    settings = load_settings(ROOT / "config/pilot01.example.yaml", environ=env)
    expected = {
        "SEARCH_PLANNING": ["openai", "google"],
        "PAPER_EXTRACTION": ["anthropic", "openai"],
        "MATH_REASONING": ["openai", "anthropic"],
        "HARDWARE_REASONING": ["openai", "google"],
        "SYNTHESIS": ["openai", "anthropic"],
        "NOVELTY_GENERATION": ["openai"],
        "ADVERSARIAL_REVIEW": ["google"],
        "CITATION_VERIFICATION": ["openai", "google"],
    }
    assert {
        p.value: [r.provider for r in routes] for p, routes in settings.models.items()
    } == expected
    assert [r.provider for r in settings.role_routes["NoveltyJudge"]] == [
        "anthropic",
        "google",
        "openai",
    ]
    for role in ("PaperScout", "CitationScout", "LocalDocumentScout", "PriorArtHunter"):
        assert [r.provider for r in settings.role_routes[role]] == ["openai", "google"]
    assert settings.live_research_budget.model_dump() == {
        "max_total_cost": 5,
        "max_model_calls": 80,
        "max_search_calls": 500,
        "max_core_papers": 12,
        "max_deep_reads": 10,
        "max_novelty_iterations": 3,
    }
    assert (
        settings.research.human_approval_required and settings.research.novelty_review_each_revision
    )
    assert "Both token prices are required" in validate(settings)
    # Account IDs and prices below are offline sentinels only, never suggested live models.
    for group in settings.route_groups():
        for route in group:
            route.input_cost_per_million = route.output_cost_per_million = 1
    path = tmp_path / "operator.yaml"
    path.write_text(yaml.safe_dump(settings.model_dump(mode="json")), encoding="utf-8")
    fake_credentials = {
        p.upper() + "_API_KEY": "offline-sentinel" for p in ("openai", "anthropic", "google")
    }
    assert provider_preflight(path, environ=fake_credentials).ready
    workspace = tmp_path / "studio"
    imported = CliRunner().invoke(
        app,
        [
            "studio",
            "prepare-pilot",
            "--workspace",
            str(workspace),
            "--project",
            str(ROOT / "config/pilot01.project.yaml"),
            "--config",
            str(path),
        ],
    )
    assert imported.exit_code == 0, imported.output
    assert json.loads(imported.output)["settings_status"] == "APPLIED_CONFIGURATION_ONLY"
    service = StudioService(workspace)
    assert (
        service.store.get("settings", "operator")["role_routes"]["PaperScout"][0]["provider"]
        == "openai"
    )
    assert not service.repository.list_all("research_runs", ResearchRun)
    service.repository.engine.dispose()


def test_prepare_command_imports_project_without_run_or_settings_and_preserves_operator_edits(
    tmp_path,
):
    args = [
        "studio",
        "prepare-pilot",
        "--workspace",
        str(tmp_path),
        "--project",
        str(ROOT / "config/pilot01.project.yaml"),
    ]
    result = CliRunner().invoke(app, args)
    assert result.exit_code == 0, result.output
    report = json.loads(result.output)
    assert report["run_created"] is False and report["settings_status"] == "UNCHANGED"
    service = StudioService(tmp_path)
    project = service.project(UUID(report["project_id"]))
    assert len(project.questions) == 10 and not project.practice
    assert all("USER CONSTRAINT, NOT A FINDING" in text for text in project.constraints)
    assert not service.repository.list_all("research_runs", ResearchRun)
    assert not service.store.list("settings")
    project.notes = "Operator edit retained"
    service.save_project(project)
    result = CliRunner().invoke(app, args)
    assert json.loads(result.output)["project_status"] == "EXISTS_PRESERVED"
    assert service.project(project.id).notes == "Operator edit retained"
    result = CliRunner().invoke(app, args + ["--config", str(ROOT / "config/pilot01.example.yaml")])
    assert result.exit_code == 1
    assert not service.store.list("settings")
    service.repository.engine.dispose()


def test_credential_presence_never_implies_smoke_and_smoke_is_model_specific(tmp_path, monkeypatch):
    service = StudioService(tmp_path)
    settings = Settings()
    settings.models = {
        p: [
            Route(
                provider="openai",
                model="offline-model",
                input_cost_per_million=1,
                output_cost_per_million=1,
            )
        ]
        for p in TaskProfile
    }
    monkeypatch.setenv("OPENAI_API_KEY", "secret-offline-sentinel")
    row = readiness(service, settings)[0]
    assert row["configuration_status"] == "CONFIGURED"
    assert row["credential_status"] == "CREDENTIAL_PRESENT" and row["access_status"] == "NOT_TESTED"
    assert "secret-offline-sentinel" not in json.dumps(row)
    # A persisted synthetic record cannot claim provider access.
    project = StudioProject(title="Fixture smoke provenance", topic="Fixture")
    service.save_project(project)
    run_id = UUID(service.new_run(project.id)["run"]["run_id"])
    record = ModelExecution(
        run_id=run_id,
        agent_id="ProviderPreflight_openai",
        task="SYNTHESIS",
        provider="openai",
        model="offline-model",
        status="SUCCESS",
        structured_output_valid=True,
    )
    service.repository.save("model_executions", record.execution_id, record, run_id)
    assert readiness(service, settings)[0]["access_status"] == "NOT_TESTED"
    run = service.repository.get_run(run_id)
    run.provenance = "live"  # Offline DB fixture simulates a recorded operator smoke.
    service.repository.save_run(run)
    assert readiness(service, settings)[0]["access_status"] == "SMOKE_TESTED"
    settings.models[TaskProfile.SEARCH_PLANNING][0].model = "changed-model"
    assert readiness(service, settings)[0]["access_status"] == "NOT_TESTED"
    service.repository.engine.dispose()


async def test_opt_in_reviews_reach_studio_with_fake_provider_and_keep_srl_zero(tmp_path):
    service = StudioService(tmp_path)
    project = StudioProject.model_validate(
        yaml.safe_load((ROOT / "config/pilot01.project.yaml").read_text(encoding="utf-8"))
    )
    project.practice = True
    service.save_project(project)
    identity = UUID(service.new_run(project.id)["run"]["run_id"])
    settings = settings_for_run(service.repository, identity)
    settings.research.novelty_review_each_revision = True
    run = service.repository.get_run(identity)
    run.config_fingerprint = settings.fingerprint()
    service.repository.checkpoint(run, {"settings": settings})
    gates = []
    for _ in range(20):
        await service.start(identity)
        await service.jobs[identity]
        snapshot = service.snapshot(identity)
        if snapshot["run"]["status"] == "COMPLETED":
            break
        point = snapshot["state"]["pending_approval"]
        assert point, snapshot
        gates.append(point)
        service.decide(identity, Decision(action="approve", reviewer="Offline fixture reviewer"))
    assert snapshot["run"]["status"] == "COMPLETED"
    assert {
        "after_plan",
        "after_core_selection",
        "after_gaps",
        "novelty_candidate_review_1",
        "novelty_revision_review_2",
        "novelty_revision_review_3",
        "before_accepting_novelty",
        "after_experiment_plan",
        "before_final_report",
    } <= set(gates)
    assert len(gates) == 10
    assert snapshot["srl"] == "SRL-0" and not snapshot["state"]["experiments"]
    assert all(r["provider"] == "fake" and r["estimated_cost"] == 0 for r in snapshot["models"])
    assert len({r["agent_id"] for r in snapshot["executions"]}) == 20
    service.repository.engine.dispose()
