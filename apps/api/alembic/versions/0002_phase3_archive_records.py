"""Add Phase 3 archive integration tracking.

Revision ID: 0002_phase3_archive_records
Revises: 0001_phase2_baseline
"""

from alembic import op
import sqlalchemy as sa

revision = "0002_phase3_archive_records"
down_revision = "0001_phase2_baseline"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "archive_records",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("file_id", sa.String(length=36), nullable=False),
        sa.Column("integration_name", sa.String(length=40), nullable=False),
        sa.Column("external_id", sa.String(length=255), nullable=True),
        sa.Column("status", sa.String(length=24), nullable=False),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("file_id", "integration_name", name="uq_archive_file_integration"),
    )
    op.create_index("ix_archive_records_file_id", "archive_records", ["file_id"], unique=False)
    op.create_index("ix_archive_records_integration_name", "archive_records", ["integration_name"], unique=False)
    op.create_index("ix_archive_records_status", "archive_records", ["status"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_archive_records_status", table_name="archive_records")
    op.drop_index("ix_archive_records_integration_name", table_name="archive_records")
    op.drop_index("ix_archive_records_file_id", table_name="archive_records")
    op.drop_table("archive_records")
