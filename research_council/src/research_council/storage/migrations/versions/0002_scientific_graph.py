"""Run/revision-scoped scientific snapshots and foreign-key provenance edges."""

import sqlalchemy as sa
from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "scientific_artifacts",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("run_id", sa.String(36), sa.ForeignKey("research_runs.id"), nullable=False),
        sa.Column("artifact_type", sa.String(40), nullable=False),
        sa.Column("artifact_id", sa.String(36), nullable=False),
        sa.Column("revision", sa.Integer, nullable=False),
        sa.Column("payload", sa.JSON, nullable=False),
        sa.UniqueConstraint(
            "run_id", "artifact_type", "artifact_id", "revision", name="uq_scientific_identity"
        ),
        sa.UniqueConstraint("id", "run_id", name="uq_scientific_run_identity"),
    )
    op.create_index("ix_scientific_artifacts_run_id", "scientific_artifacts", ["run_id"])
    op.create_table(
        "scientific_links",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("run_id", sa.String(36), sa.ForeignKey("research_runs.id"), nullable=False),
        sa.Column("source_id", sa.String(36), nullable=False),
        sa.Column("target_id", sa.String(36), nullable=False),
        sa.Column("relation", sa.String(64), nullable=False),
        sa.ForeignKeyConstraint(
            ["source_id", "run_id"], ["scientific_artifacts.id", "scientific_artifacts.run_id"]
        ),
        sa.ForeignKeyConstraint(
            ["target_id", "run_id"], ["scientific_artifacts.id", "scientific_artifacts.run_id"]
        ),
    )
    op.create_index("ix_scientific_links_run_id", "scientific_links", ["run_id"])


def downgrade() -> None:
    op.drop_table("scientific_links")
    op.drop_table("scientific_artifacts")
