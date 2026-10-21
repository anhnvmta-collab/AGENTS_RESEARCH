from datetime import UTC, datetime, timedelta, timezone
from uuid import uuid4

import pytest
from sqlalchemy import insert, select, update
from sqlalchemy.exc import IntegrityError

from research_council.agents.contracts import PaperOutline
from research_council.core.integrity import validate_graph
from research_council.core.orchestration import WorkflowState
from research_council.core.orchestration.engine import RunLease
from research_council.schemas.models import (
    CitationAudit,
    Evidence,
    ExperimentPlan,
    Gap,
    NoveltyCandidate,
    NoveltyDecision,
    Paper,
    PaperCandidate,
    PaperMetadata,
    PriorArtMatch,
    PriorArtReport,
    ResearchClaim,
    ResearchProject,
    ResearchRun,
    ReviewerReport,
    ReviewReason,
    VerificationStatus,
)
from research_council.storage.database import downgrade, make_engine, migrate, tables


def graph():
    paper = Paper(
        metadata=PaperMetadata(
            title="Unit-test source, not literature",
            authors=["Unit-test author"],
            year=2024,
            url="https://example.invalid/unit",
            metadata_source="unit-test",
            metadata_verified=True,
        ),
        source_text="Unit evidence. Additional evidence.",
    )
    evidence = Evidence(
        paper_id=paper.paper_id,
        evidence_type="test",
        source_location="text",
        verbatim_excerpt="Unit evidence.",
        normalized_statement="Unit test statement",
        extraction_agent="test",
        verification_status=VerificationStatus.PARTIALLY_VERIFIED,
    )
    claim = ResearchClaim(
        statement="Unit test statement",
        claim_type="AUTHOR_REPORTED",
        evidence_ids=[evidence.evidence_id],
        source_paper_ids=[paper.paper_id],
    )
    gap = Gap(
        gap_type="EXPERIMENTAL",
        evidence_ids=[evidence.evidence_id],
        claim_ids=[claim.claim_id],
        limitation="Unit-test limitation",
        consequence="Unit-test consequence",
        opportunity="Unit-test opportunity",
        search_scope="Unit tests only",
    )
    candidate = NoveltyCandidate(
        gap_ids=[gap.gap_id],
        evidence_ids=[evidence.evidence_id],
        normalized_claim="Unit-test hypothesis",
        keywords=["test"],
        what_is_new="Test",
        why_it_matters="Test",
        why_prior_methods_insufficient="Test",
        proposed_method="Test",
        validation_plan="Test",
    )
    prior = PriorArtReport(candidate_id=candidate.candidate_id, revision=1)
    review = ReviewerReport(candidate_id=candidate.candidate_id, revision=1)
    decision = NoveltyDecision(candidate_id=candidate.candidate_id, revision=1)
    plan = ExperimentPlan(
        candidate_ids=[candidate.candidate_id],
        candidate_revisions={candidate.candidate_id: 1},
        gap_ids=[gap.gap_id],
        claim_ids=[claim.claim_id],
    )
    return WorkflowState(
        candidates=[PaperCandidate(paper=paper)],
        evidence=[evidence],
        claims=[claim],
        gaps=[gap],
        novelty_candidates=[candidate],
        prior_art=[prior],
        reviews=[review],
        decisions=[decision],
        experiments=[plan],
        outline=PaperOutline(experiment_ids=[plan.experiment_id], claim_ids=[claim.claim_id]),
    )


@pytest.mark.parametrize(
    "broken_edge",
    [
        "gap_evidence",
        "gap_claim",
        "novelty_gap",
        "novelty_evidence",
        "report_revision",
        "prior_paper",
        "review_evidence",
        "decision_prior",
        "experiment_revision",
        "roadmap_experiment",
        "roadmap_claim",
        "duplicate_evidence",
    ],
)
def test_every_scientific_edge_is_validated(broken_edge):
    state = graph()
    validate_graph(state)
    missing = uuid4()
    if broken_edge == "gap_evidence":
        state.gaps[0].evidence_ids = [missing]
    elif broken_edge == "gap_claim":
        state.gaps[0].claim_ids = [missing]
    elif broken_edge == "novelty_gap":
        state.novelty_candidates[0].gap_ids = [missing]
    elif broken_edge == "novelty_evidence":
        state.novelty_candidates[0].evidence_ids = [missing]
    elif broken_edge == "report_revision":
        state.decisions[0].revision = 2
    elif broken_edge == "prior_paper":
        state.prior_art[0].matches = [
            PriorArtMatch(
                candidate_id=state.novelty_candidates[0].candidate_id,
                paper_id=missing,
                similarity=1,
                overlap="Test",
            )
        ]
    elif broken_edge == "review_evidence":
        state.reviews[0].reasons = [
            ReviewReason(
                category="test", severity="HIGH", explanation="Test", evidence_ids=[missing]
            )
        ]
    elif broken_edge == "decision_prior":
        state.decisions[0].closest_prior_art = [missing]
    elif broken_edge == "experiment_revision":
        state.experiments[0].candidate_revisions[state.novelty_candidates[0].candidate_id] = 2
    elif broken_edge == "roadmap_experiment":
        state.outline.experiment_ids = [missing]
    elif broken_edge == "roadmap_claim":
        state.outline.claim_ids = [missing]
    elif broken_edge == "duplicate_evidence":
        state.evidence.append(state.evidence[0].model_copy())
    with pytest.raises(ValueError):
        validate_graph(state)


def test_cross_run_and_revision_snapshots_are_preserved(repository):
    repo, run = repository
    state = graph()
    second_revision = state.novelty_candidates[0].model_copy(update={"revision": 2})
    state.novelty_candidates.append(second_revision)
    repo.checkpoint(run, {"state": state})
    project = ResearchProject(title="Second run", question=run.question)
    other = ResearchRun(
        project_id=project.project_id,
        question=run.question,
        config_fingerprint=run.config_fingerprint,
    )
    repo.create_run(project, other)
    repo.checkpoint(other, {"state": state})
    assert len(repo.list_all("novelty_candidates", NoveltyCandidate, run.run_id)) == 2
    assert len(repo.list_all("novelty_candidates", NoveltyCandidate, other.run_id)) == 2
    assert len(repo.list_all("evidence", Evidence, run.run_id)) == 1
    assert repo.get_candidate(second_revision.candidate_id, run.run_id, 1).revision == 1
    with repo.engine.connect() as connection:
        assert connection.execute(select(tables["scientific_links"].c.id)).first()


def test_database_rejects_cross_run_foreign_key_link(repository):
    repo, run = repository
    state = graph()
    repo.checkpoint(run, {"state": state})
    project = ResearchProject(title="Other run", question=run.question)
    other = ResearchRun(
        project_id=project.project_id,
        question=run.question,
        config_fingerprint=run.config_fingerprint,
    )
    repo.create_run(project, other)
    with repo.engine.connect() as connection:
        node = connection.execute(
            select(tables["scientific_artifacts"].c.id).where(
                tables["scientific_artifacts"].c.run_id == str(run.run_id)
            )
        ).first()[0]
    with pytest.raises(IntegrityError), repo.engine.begin() as connection:
        connection.execute(
            insert(tables["scientific_links"]).values(
                id=str(uuid4()),
                run_id=str(other.run_id),
                source_id=node,
                target_id=node,
                relation="invalid_cross_run",
            )
        )


def test_stale_worker_cannot_checkpoint(repository):
    repo, run = repository
    lease = RunLease(repo, run.run_id)
    lease.acquire()
    with repo.engine.begin() as connection:
        connection.execute(
            update(tables["research_runs"])
            .where(tables["research_runs"].c.id == str(run.run_id))
            .values(lease_owner="new-worker")
        )
    with pytest.raises(RuntimeError, match="Stale"):
        repo.checkpoint(run, {"state": WorkflowState()})
    lease.release()


def test_migrations_up_down_from_empty_database(tmp_path):
    engine = make_engine(f"sqlite:///{tmp_path / 'migrations.db'}")
    migrate(engine)
    downgrade(engine, "0001")
    migrate(engine)
    downgrade(engine)
    migrate(engine)
    engine.dispose()


def test_utc_and_persistence_revalidation(repository):
    with pytest.raises(ValueError, match="timezone-aware"):
        CitationAudit(paper_id=uuid4(), checked_at=datetime(2024, 1, 1))
    value = CitationAudit(
        paper_id=uuid4(), checked_at=datetime(2024, 1, 1, tzinfo=timezone(timedelta(hours=7)))
    )
    assert value.checked_at.tzinfo == UTC
    repo, run = repository
    state = graph()
    state.claims[0] = state.claims[0].model_copy(
        update={"verification_status": VerificationStatus.VERIFIED, "evidence_ids": []}
    )
    with pytest.raises(ValueError):
        repo.checkpoint(run, {"state": state})
