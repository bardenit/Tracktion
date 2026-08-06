from pathlib import Path

from alembic import command
from alembic.config import Config
from alembic.migration import MigrationContext
from sqlalchemy import create_engine

from app.data_config import get_database_url
from app.schema_bootstrap import reconcile_legacy_schema


HEAD_REVISION = "0004_offline_fuel_idempotency"


def alembic_config(database_url: str) -> Config:
    backend_root = Path(__file__).resolve().parents[1]
    config = Config(str(backend_root / "alembic.ini"))
    config.set_main_option("script_location", str(backend_root / "alembic"))
    config.set_main_option("sqlalchemy.url", database_url.replace("%", "%%"))
    return config


def upgrade_database(database_url: str | None = None) -> str:
    url = database_url or get_database_url()
    engine = create_engine(url, connect_args={"check_same_thread": False} if url.startswith("sqlite") else {})
    try:
        reconcile_legacy_schema(engine)
        with engine.begin() as connection:
            config = alembic_config(url)
            config.attributes["connection"] = connection
            command.upgrade(config, "head")
            revision = MigrationContext.configure(connection).get_current_revision()
        if revision != HEAD_REVISION:
            raise RuntimeError(f"database migration ended at {revision!r}, expected {HEAD_REVISION!r}")
        return revision
    finally:
        engine.dispose()


def require_database_current(engine) -> None:
    with engine.connect() as connection:
        revision = MigrationContext.configure(connection).get_current_revision()
        if revision != HEAD_REVISION:
            raise RuntimeError(f"database revision is {revision!r}, expected {HEAD_REVISION!r}")


if __name__ == "__main__":
    upgrade_database()
