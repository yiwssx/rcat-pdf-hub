"""T90 attempt fencing and durable storage write-ahead journal.

Revision ID: 0006_t90_write_journal
Revises: 0005_t90_output_artifacts
"""
from alembic import op
import sqlalchemy as sa

revision = "0006_t90_write_journal"
down_revision = "0005_t90_output_artifacts"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("jobs", sa.Column("lease_epoch", sa.Integer(), nullable=False, server_default="0"))
    op.add_column("jobs", sa.Column("lease_token", sa.String(36), nullable=True))
    op.add_column("jobs", sa.Column("lease_expires_at", sa.DateTime(timezone=True), nullable=True))
    op.create_table(
        "artifact_write_journal",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("job_id", sa.String(36), nullable=False),
        sa.Column("lease_epoch", sa.Integer(), nullable=False),
        sa.Column("lease_token", sa.String(36), nullable=False),
        sa.Column("stored_name", sa.String(255), nullable=False, unique=True),
        sa.Column("role", sa.String(12), nullable=False),
        sa.Column("state", sa.String(20), nullable=False),
        sa.Column("file_id", sa.String(36), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "state IN ('planned','committed','compensated','needs_review')",
            name="ck_artifact_write_journal_state",
        ),
        sa.CheckConstraint("role IN ('result','bundle','part')", name="ck_artifact_write_journal_role"),
    )
    op.create_index("ix_artifact_write_journal_job_id", "artifact_write_journal", ["job_id"])


def downgrade() -> None:
    # Explicit rollback DISCARDs journal evidence. Never run on a real
    # environment without exporting it and signing off recovery candidates.
    op.drop_index("ix_artifact_write_journal_job_id", table_name="artifact_write_journal")
    op.drop_table("artifact_write_journal")
    op.drop_column("jobs", "lease_expires_at")
    op.drop_column("jobs", "lease_token")
    op.drop_column("jobs", "lease_epoch")
