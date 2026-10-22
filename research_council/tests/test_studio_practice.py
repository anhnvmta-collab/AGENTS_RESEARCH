from uuid import UUID

from research_council.studio.interactions import discuss
from research_council.studio.models import Decision, Interaction, StudioProject
from research_council.studio.service import StudioService


async def test_full_practice_preserves_gates_and_uses_real_agents(tmp_path, monkeypatch):
    async def forbidden(*args, **kwargs):
        raise AssertionError("Practice must never send a network request")

    monkeypatch.setattr("httpx.AsyncClient.send", forbidden)
    service = StudioService(tmp_path)
    project = StudioProject(
        title="Compressed Sensing for FHSS Detection and DOA",
        topic="Compressed Sensing for FHSS Detection and DOA",
    )
    service.save_project(project)
    identity = UUID(service.new_run(project.id)["run"]["run_id"])
    gates = []
    for _ in range(15):
        await service.start(identity)
        await service.jobs[identity]
        snapshot = service.snapshot(identity)
        if snapshot["run"]["status"] == "COMPLETED":
            break
        point = snapshot["state"]["pending_approval"]
        assert point, snapshot
        gates.append(point)
        service.decide(
            identity,
            Decision(
                action="approve",
                reviewer="Offline practice reviewer",
                comment="Synthetic training only",
            ),
        )
    assert snapshot["run"]["status"] == "COMPLETED"
    state = snapshot["state"]
    for field in [
        "candidates",
        "evidence",
        "claims",
        "gaps",
        "novelty_candidates",
        "prior_art",
        "reviews",
        "decisions",
    ]:
        assert state[field], field
    assert not state["experiments"]  # Canonical Gate 2 is never bypassed for synthetic data.
    assert snapshot["practice_design"]["experiments"]
    assert snapshot["practice_design"]["outline"]["sections"]
    assert any(not gate["passed"] for gate in state["gates"])
    assert all(item["verification_status"] != "VERIFIED" for item in state["evidence"])
    assert snapshot["srl"] == "SRL-0"
    assert {
        "after_plan",
        "after_core_selection",
        "after_experiment_plan",
        "before_final_report",
    }.issubset(gates)
    records = service.repository.list_model_executions(identity)
    assert all(row.provider == "fake" and row.estimated_cost == 0 for row in records)
    names = {row["agent_id"] for row in snapshot["executions"]}
    assert {
        "PaperScout",
        "DeepReader",
        "GapMiner",
        "NoveltyGenerator",
        "PriorArtHunter",
        "ReviewerTwo",
        "NoveltyJudge",
        "ExperimentDesigner",
        "PaperArchitect",
        "CitationAuditor",
        "FinalSynthesizer",
    }.issubset(names)
    before = service.repository.artifacts(identity)["state"]
    for name in [
        "ResearchPlanner",
        "PaperScout",
        "DeepReader",
        "MathDSPAnalyst",
        "HardwareArchitect",
        "GapMiner",
        "NoveltyGenerator",
        "PriorArtHunter",
        "ReviewerTwo",
        "NoveltyJudge",
        "ExperimentDesigner",
        "PaperArchitect",
        "CitationAuditor",
    ]:
        result = await discuss(
            service,
            name,
            Interaction(
                run_id=identity, task="Inspect the synthetic evidence and report limitations"
            ),
        )
        assert result["status"] == "EXECUTED_ADVISORY", name
    assert service.repository.artifacts(identity)["state"] == before
    service.repository.engine.dispose()
