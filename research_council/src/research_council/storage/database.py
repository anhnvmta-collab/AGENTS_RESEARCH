from __future__ import annotations

from pathlib import Path
from typing import Any

from alembic import command
from alembic.config import Config
from sqlalchemy import JSON, Column, ForeignKey, MetaData, String, Table, create_engine, event
from sqlalchemy.engine import Engine

metadata = MetaData()


def entity_table(name: str, *, run_scoped: bool = True, paper_scoped: bool = False) -> Table:
    columns = [Column("id", String(36), primary_key=True)]
    if run_scoped:
        columns.append(Column("run_id", String(36), ForeignKey("research_runs.id"), index=True))
    if paper_scoped:
        columns.append(Column("paper_id", String(36), ForeignKey("papers.id"), index=True))
    columns.append(Column("payload", JSON, nullable=False))
    return Table(name, metadata, *columns)


projects = entity_table("projects", run_scoped=False)
runs = Table(
    "research_runs",
    metadata,
    Column("id", String(36), primary_key=True),
    Column("project_id", String(36), ForeignKey("projects.id"), nullable=False, index=True),
    Column("lease_owner", String(36)),
    Column("lease_until", String(40)),
    Column("payload", JSON, nullable=False),
)
papers = Table(
    "papers",
    metadata,
    Column("id", String(36), primary_key=True),
    Column("doi", String(512), unique=True),
    Column("normalized_title", String(2000), index=True),
    Column("payload", JSON, nullable=False),
)
tables: dict[str, Table] = {"projects": projects, "research_runs": runs, "papers": papers}
for table_name in ("paper_metadata", "paper_scores", "evidence", "citation_audits"):
    tables[table_name] = entity_table(table_name, paper_scoped=True)
for table_name in (
    "search_queries",
    "claims",
    "gaps",
    "novelty_candidates",
    "prior_art_matches",
    "reviews",
    "agent_executions",
    "model_executions",
    "quality_gate_results",
    "approvals",
):
    tables[table_name] = entity_table(table_name)
tables["artifacts"] = Table(
    "artifacts",
    metadata,
    Column("id", String(128), primary_key=True),
    Column("run_id", String(36), ForeignKey("research_runs.id"), nullable=False, index=True),
    Column("name", String(100), nullable=False),
    Column("payload", JSON, nullable=False),
)


def make_engine(url: str) -> Engine:
    engine = create_engine(
        url, connect_args={"check_same_thread": False} if url.startswith("sqlite") else {}
    )
    if url.startswith("sqlite"):

        @event.listens_for(engine, "connect")
        def configure_sqlite(connection: Any, _: Any) -> None:
            cursor = connection.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.execute("PRAGMA journal_mode=WAL")
            cursor.execute("PRAGMA busy_timeout=5000")
            cursor.close()

    return engine


def migrate(engine: Engine) -> None:
    config = Config()
    config.set_main_option("script_location", str(Path(__file__).parent / "migrations"))
    with engine.begin() as connection:
        config.attributes["connection"] = connection
        command.upgrade(config, "head")
