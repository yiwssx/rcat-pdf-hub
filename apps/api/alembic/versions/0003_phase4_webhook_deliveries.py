"""Add Phase 4 persistent webhook delivery tracking.

Revision ID: 0003_phase4_webhook_deliveries
Revises: 0002_phase3_archive_records
"""

from alembic import op
import sqlalchemy as sa

revision = "0003_phase4_webhook_deliveries"
down_revision = "0002_phase3_archive_records"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "webhook_deliveries",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("job_id", sa.String(length=36), nullable=False),
        sa.Column("service_name", sa.String(length=120), nullable=False),
        sa.Column("url", sa.String(length=2048), nullable=False),
        sa.Column("event", sa.String(length=80), nullable=False),
        sa.Column("status", sa.String(length=24), nullable=False),
        sa.Column("attempt_count", sa.Integer(), nullable=False),
        sa.Column("max_attempts", sa.Integer(), nullable=False),
        sa.Column("next_attempt_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("last_status_code", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("delivered_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_webhook_deliveries_job_id", "webhook_deliveries", ["job_id"], unique=False)
    op.create_index("ix_webhook_deliveries_service_name", "webhook_deliveries", ["service_name"], unique=False)
    op.create_index("ix_webhook_deliveries_event", "webhook_deliveries", ["event"], unique=False)
    op.create_index("ix_webhook_deliveries_status", "webhook_deliveries", ["status"], unique=False)
    op.create_index("ix_webhook_deliveries_next_attempt_at", "webhook_deliveries", ["next_attempt_at"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_webhook_deliveries_next_attempt_at", table_name="webhook_deliveries")
    op.drop_index("ix_webhook_deliveries_status", table_name="webhook_deliveries")
    op.drop_index("ix_webhook_deliveries_event", table_name="webhook_deliveries")
    op.drop_index("ix_webhook_deliveries_service_name", table_name="webhook_deliveries")
    op.drop_index("ix_webhook_deliveries_job_id", table_name="webhook_deliveries")
    op.drop_table("webhook_deliveries")
