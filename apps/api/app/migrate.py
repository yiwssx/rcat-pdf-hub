from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import inspect

from app.db import engine

BASELINE_REVISION = "0001_phase2_baseline"
CORE_TABLES = {"api_keys", "service_policies", "files", "jobs"}


def _config() -> Config:
    path = Path(__file__).resolve().parent.parent / "alembic.ini"
    return Config(str(path))


def run_migrations() -> None:
    """Upgrade schema while safely adopting databases created before Alembic."""
    inspector = inspect(engine)
    tables = set(inspector.get_table_names())
    config = _config()

    if "alembic_version" not in tables and CORE_TABLES.issubset(tables):
        # Phase 2 used SQLAlchemy create_all. Adopt that exact schema as the
        # migration baseline without replaying destructive CREATE statements.
        command.stamp(config, BASELINE_REVISION)
    command.upgrade(config, "head")
