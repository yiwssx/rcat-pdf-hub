from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
from types import SimpleNamespace


API_ROOT = Path(__file__).resolve().parents[1]
MIGRATION = API_ROOT / "alembic" / "versions" / "0004_phase6_file_library_indexes.py"


def _load_migration():
    spec = spec_from_file_location("phase6_file_library_indexes", MIGRATION)
    assert spec and spec.loader
    module = module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_phase6_file_library_indexes_cover_server_query_shapes(monkeypatch):
    migration = _load_migration()
    created: list[tuple[str, tuple[str, ...]]] = []
    executed: list[str] = []
    monkeypatch.setattr(migration.op, "get_bind", lambda: SimpleNamespace(dialect=SimpleNamespace(name="sqlite")))
    monkeypatch.setattr(
        migration.op,
        "create_index",
        lambda name, _table, columns, unique=False: created.append((name, tuple(columns))),
    )
    monkeypatch.setattr(migration.op, "execute", executed.append)

    migration.upgrade()

    assert dict(created) == {
        "ix_files_library_source_created_id": ("source_system", "created_at", "id"),
        "ix_files_library_source_size_id": ("source_system", "size", "id"),
        "ix_files_library_source_expires_id": ("source_system", "expires_at", "id"),
        "ix_files_library_source_kind_created_id": ("source_system", "content_type", "created_at", "id"),
    }
    assert executed == [
        "CREATE INDEX ix_files_library_source_name_id ON files (source_system, lower(original_name), id)"
    ]


def test_postgres_migration_defines_trigram_search_index(monkeypatch):
    migration = _load_migration()
    executed: list[str] = []
    monkeypatch.setattr(migration.op, "get_bind", lambda: SimpleNamespace(dialect=SimpleNamespace(name="postgresql")))
    monkeypatch.setattr(migration.op, "create_index", lambda *args, **kwargs: None)
    monkeypatch.setattr(migration.op, "execute", executed.append)

    migration.upgrade()

    assert "CREATE EXTENSION IF NOT EXISTS pg_trgm" in executed
    assert any("USING gin (lower(original_name) gin_trgm_ops)" in statement for statement in executed)
    assert any("source_system, lower(original_name), id" in statement for statement in executed)
