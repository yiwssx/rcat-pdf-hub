"""T90 job output association table: preserve legacy primary pointer.

Revision ID: 0005_t90_output_artifacts
Revises: 0004_phase6_file_library_indexes
"""
from alembic import op
import sqlalchemy as sa

revision = "0005_t90_output_artifacts"
down_revision = "0004_phase6_file_library_indexes"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "job_output_artifacts",
        sa.Column("job_id", sa.String(36), sa.ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("file_id", sa.String(36), sa.ForeignKey("files.id", ondelete="CASCADE"), nullable=False),
        sa.Column("role", sa.String(12), nullable=False),
        sa.Column("ordinal", sa.Integer(), nullable=True),
        sa.PrimaryKeyConstraint("job_id", "file_id"),
        sa.UniqueConstraint("job_id", "role", "ordinal", name="uq_job_output_artifact_order"),
        sa.CheckConstraint(
            "(role = 'part' AND ordinal >= 1 AND ordinal <= 200) OR "
            "(role IN ('result', 'bundle') AND ordinal IS NULL)",
            name="ck_job_output_artifact_role_ordinal",
        ),
    )
    op.create_index("ix_job_output_artifacts_file_id", "job_output_artifacts", ["file_id"])
    # Backfill only historically completed jobs with an existing, same-owner
    # FileRecord; never create a cross-service association from stale metadata.
    op.execute(sa.text(
        "INSERT INTO job_output_artifacts (job_id, file_id, role, ordinal) "
        "SELECT j.id, j.output_file_id, "
        "CASE WHEN j.operation = 'pdf-to-images' THEN 'bundle' ELSE 'result' END, NULL "
        "FROM jobs AS j JOIN files AS f ON f.id = j.output_file_id "
        "WHERE j.status = 'completed' AND j.output_file_id IS NOT NULL "
        "AND f.source_system = j.requested_by"
    ))


def downgrade() -> None:
    # Drops the association table only; legacy jobs.output_file_id remains intact.
    op.drop_index("ix_job_output_artifacts_file_id", table_name="job_output_artifacts")
    op.drop_table("job_output_artifacts")
