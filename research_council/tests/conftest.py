from pathlib import Path

import pytest

from research_council.core.config import Settings
from research_council.repositories.store import SQLRepository
from research_council.schemas.models import ResearchProject, ResearchQuestion, ResearchRun
from research_council.storage.database import make_engine, migrate


def pytest_addoption(parser):
    parser.addoption(
        "--run-live",
        action="store_true",
        default=False,
        help="Explicitly enable selected real service tests.",
    )
    parser.addoption(
        "--confirm-paid-apis",
        action="store_true",
        default=False,
        help="Confirm selected live tests may use paid model APIs.",
    )


@pytest.hookimpl(trylast=True)
def pytest_collection_modifyitems(config, items):
    live = [item for item in items if item.get_closest_marker("live")]
    if live and not (config.getoption("--run-live") and config.getoption("--confirm-paid-apis")):
        raise pytest.UsageError(
            "Live tests require --run-live --confirm-paid-apis; default CI remains offline."
        )


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
