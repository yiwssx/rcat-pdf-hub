"""Add Phase 6 file-library query indexes.

Revision ID: 0004_phase6_file_library_indexes
Revises: 0003_phase4_webhook_deliveries
"""

from alembic import op
import sqlalchemy as sa

revision = "0004_phase6_file_library_indexes"
down_revision = "0003_phase4_webhook_deliveries"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # These indexes mirror the server-side library query shape introduced in
    # Phase 6F.1: ownership is the leading predicate for normal human/service
    # principals, followed by the selected sort/filter column and deterministic
    # id tie-breaker.
    op.create_index(
        "ix_files_library_source_created_id",
        "files",
        ["source_system", "created_at", "id"],
        unique=False,
    )
    op.create_index(
        "ix_files_library_source_size_id",
        "files",
        ["source_system", "size", "id"],
        unique=False,
    )
    op.create_index(
        "ix_files_library_source_expires_id",
        "files",
        ["source_system", "expires_at", "id"],
        unique=False,
    )
    op.create_index(
        "ix_files_library_source_kind_created_id",
        "files",
        ["source_system", "content_type", "created_at", "id"],
        unique=False,
    )

    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        # Contains filename search cannot use a normal B-tree. pg_trgm keeps
        # case-insensitive contains-search responsive at Phase 6 target scale.
        op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")
        op.execute(
            "CREATE INDEX ix_files_library_name_trgm "
            "ON files USING gin (lower(original_name) gin_trgm_ops)"
        )
        op.execute(
            "CREATE INDEX ix_files_library_source_name_id "
            "ON files (source_system, lower(original_name), id)"
        )
    else:
        # SQLite is used by the repository fresh/adopted migration gate.
        op.execute(
            "CREATE INDEX ix_files_library_source_name_id "
            "ON files (source_system, lower(original_name), id)"
        )


def downgrade() -> None:
    op.drop_index("ix_files_library_source_name_id", table_name="files")
    if op.get_bind().dialect.name == "postgresql":
        op.drop_index("ix_files_library_name_trgm", table_name="files")
    op.drop_index("ix_files_library_source_kind_created_id", table_name="files")
    op.drop_index("ix_files_library_source_expires_id", table_name="files")
    op.drop_index("ix_files_library_source_size_id", table_name="files")
    op.drop_index("ix_files_library_source_created_id", table_name="files")
