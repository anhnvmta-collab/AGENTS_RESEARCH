from uuid import uuid4

import pytest
from pydantic import ValidationError

from research_council.core.config import Settings
from research_council.core.security import workspace_path
from research_council.repositories.store import SQLRepository
from research_council.schemas.models import (
    ClaimType,
    Evidence,
    Paper,
    PaperMetadata,
    ResearchClaim,
    ResearchProject,
    ResearchQuestion,
    ResearchRun,
    VerificationStatus,
    normalize_doi,
)
from research_council.storage.database import make_engine, migrate


@pytest.fixture
def store(tmp_path):
    engine = make_engine(f"sqlite:///{tmp_path / 'test.db'}")
    migrate(engine)
    repository = SQLRepository(engine)
    question = ResearchQuestion(topic="FPGA sensing")
    project = ResearchProject(title=question.topic, question=question)
    run = ResearchRun(
        project_id=project.project_id,
        question=question,
        config_fingerprint=Settings().fingerprint(),
    )
    repository.create_run(project, run)
    yield repository, run
    engine.dispose()


@pytest.mark.parametrize(
    "raw", ["https://doi.org/10.1234/AB.C", "DOI: 10.1234/ab.c", "10.1234/AB.C"]
)
def test_doi(raw):
    assert normalize_doi(raw) == "10.1234/ab.c"


def test_schema_guards():
    with pytest.raises(ValidationError):
        ResearchClaim(
            statement="Unsupported",
            claim_type=ClaimType.AUTHOR_REPORTED,
            verification_status=VerificationStatus.VERIFIED,
        )
    with pytest.raises(ValidationError):
        ResearchClaim(statement="Invented equation", claim_type=ClaimType.DERIVED)
    with pytest.raises(ValueError):
        normalize_doi("not a DOI")
    with pytest.raises(ValidationError):
        PaperMetadata(title="Example", metadata_source="fake", quartile="Q1")
    with pytest.raises(ValidationError):
        ResearchQuestion(topic="test", secret="ignored?")


def test_persistence_and_grounding(store):
    repo, run = store
    paper = Paper(
        metadata=PaperMetadata(title="Fixture paper", metadata_source="fixture"),
        provenance="fixture",
        source_text="The latency was not measured.",
        source_kind="fixture",
    )
    repo.save_paper(paper)
    evidence = Evidence(
        paper_id=paper.paper_id,
        evidence_type="limitation",
        source_location="fixture",
        verbatim_excerpt="latency was not measured",
        normalized_statement="Latency unknown",
        extraction_agent="test",
    )
    repo.save_evidence(evidence, run.run_id)
    claim = ResearchClaim(
        statement="Latency unknown",
        claim_type=ClaimType.AUTHOR_REPORTED,
        source_paper_ids=[paper.paper_id],
        evidence_ids=[evidence.evidence_id],
    )
    repo.save_claim(claim, run.run_id)
    assert repo.get_run(run.run_id).question.topic == "FPGA sensing"
    with pytest.raises(ValueError, match="unknown evidence"):
        repo.save_claim(claim.model_copy(update={"evidence_ids": [uuid4()]}), run.run_id)
    with pytest.raises(ValueError, match="not found"):
        repo.save_evidence(evidence.model_copy(update={"verbatim_excerpt": "invented"}), run.run_id)
    repo.checkpoint(run, {"claims": [claim]})
    assert repo.artifacts(run.run_id)["claims"][0]["statement"] == "Latency unknown"


def test_workspace_escape(tmp_path):
    with pytest.raises(ValueError):
        workspace_path(tmp_path, "../outside")
    assert workspace_path(tmp_path, "reports/file.md").is_relative_to(tmp_path)
