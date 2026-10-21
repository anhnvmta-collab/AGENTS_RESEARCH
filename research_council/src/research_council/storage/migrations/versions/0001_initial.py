"""Initial versioned artifact and provenance schema."""

import sqlalchemy as sa
from alembic import op

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "projects",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("payload", sa.JSON, nullable=False),
    )
    op.create_table(
        "research_runs",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("project_id", sa.String(36), sa.ForeignKey("projects.id"), nullable=False),
        sa.Column("lease_owner", sa.String(36)),
        sa.Column("lease_until", sa.String(40)),
        sa.Column("payload", sa.JSON, nullable=False),
    )
    op.create_index("ix_research_runs_project_id", "research_runs", ["project_id"])
    op.create_table(
        "papers",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("doi", sa.String(512), unique=True),
        sa.Column("normalized_title", sa.String(2000)),
        sa.Column("payload", sa.JSON, nullable=False),
    )
    op.create_index("ix_papers_normalized_title", "papers", ["normalized_title"])
    for name in (
        "paper_metadata",
        "paper_scores",
        "evidence",
        "citation_audits",
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
        columns = [
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("run_id", sa.String(36), sa.ForeignKey("research_runs.id")),
        ]
        if name in ("paper_metadata", "paper_scores", "evidence", "citation_audits"):
            columns.append(sa.Column("paper_id", sa.String(36), sa.ForeignKey("papers.id")))
        columns.append(sa.Column("payload", sa.JSON, nullable=False))
        op.create_table(name, *columns)
        op.create_index(f"ix_{name}_run_id", name, ["run_id"])
        if name in ("paper_metadata", "paper_scores", "evidence", "citation_audits"):
            op.create_index(f"ix_{name}_paper_id", name, ["paper_id"])
    op.create_table(
        "artifacts",
        sa.Column("id", sa.String(128), primary_key=True),
        sa.Column("run_id", sa.String(36), sa.ForeignKey("research_runs.id"), nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("payload", sa.JSON, nullable=False),
    )
    op.create_index("ix_artifacts_run_id", "artifacts", ["run_id"])


def downgrade() -> None:
    for name in (
        "artifacts",
        "approvals",
        "quality_gate_results",
        "model_executions",
        "agent_executions",
        "reviews",
        "prior_art_matches",
        "novelty_candidates",
        "gaps",
        "claims",
        "search_queries",
        "citation_audits",
        "evidence",
        "paper_scores",
        "paper_metadata",
        "papers",
        "research_runs",
        "projects",
    ):
        op.drop_table(name)
