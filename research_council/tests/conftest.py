from pathlib import Path

import pytest

from research_council.core.config import Settings
from research_council.repositories.store import SQLRepository
from research_council.schemas.models import ResearchProject, ResearchQuestion, ResearchRun
from research_council.storage.database import make_engine, migrate


@pytest.fixture
def repository(tmp_path: Path):
    engine = make_engine(f"sqlite:///{tmp_path / 'test.db'}")
    migrate(engine)
    repo = SQLRepository(engine)
    question = ResearchQuestion(topic="RFSoC compressed sensing")
    project = ResearchProject(title=question.topic, question=question)
    run = ResearchRun(
        project_id=project.project_id,
        question=question,
        config_fingerprint=Settings().fingerprint(),
    )
    repo.create_run(project, run)
    yield repo, run
    engine.dispose()
