from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect


API_ROOT = Path(__file__).resolve().parents[1]


def _config(url: str) -> Config:
    config = Config(str(API_ROOT / "alembic.ini"))
    config.set_main_option("sqlalchemy.url", url)
    return config


def test_phase6_file_library_indexes_migrate_on_sqlite(tmp_path):
    db_path = tmp_path / "file-library-indexes.db"
    url = f"sqlite+pysqlite:///{db_path}"
    command.upgrade(_config(url), "head")

    engine = create_engine(url)
    index_names = {row["name"] for row in inspect(engine).get_indexes("files")}
    assert {
        "ix_files_library_source_created_id",
        "ix_files_library_source_size_id",
        "ix_files_library_source_expires_id",
        "ix_files_library_source_kind_created_id",
        "ix_files_library_source_name_id",
    } <= index_names


def test_postgres_migration_defines_trigram_search_index():
    source = (API_ROOT / "alembic" / "versions" / "0004_phase6_file_library_indexes.py").read_text()
    assert "CREATE EXTENSION IF NOT EXISTS pg_trgm" in source
    assert "USING gin (lower(original_name) gin_trgm_ops)" in source
