"""Opt-in institutional roles and irreversible Super Admin bootstrap claim.

Revision ID: 0007_institutional_roles
Revises: 0006_t90_write_journal
"""
from alembic import op
import sqlalchemy as sa

revision = "0007_institutional_roles"
down_revision = "0006_t90_write_journal"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "institutional_role_assignments",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("email", sa.String(254), nullable=False, unique=True),
        sa.Column("owner_name", sa.String(120), nullable=True, unique=True),
        sa.Column("role", sa.String(20), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False),
        sa.Column("granted_by", sa.String(120), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "role IN ('viewer', 'operator', 'admin', 'super_admin')",
            name="ck_institutional_role",
        ),
    )
    op.create_table(
        "institutional_bootstrap_claims",
        sa.Column("key", sa.String(48), primary_key=True),
        sa.Column("owner_name", sa.String(120), nullable=False),
        sa.Column("email", sa.String(254), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("institutional_bootstrap_claims")
    op.drop_table("institutional_role_assignments")
