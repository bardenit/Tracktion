from sqlalchemy import create_engine, inspect, text
import pytest


def test_fresh_sqlite_database_upgrades_to_head(db_url):
    from app.migrations import HEAD_REVISION, upgrade_database

    result = upgrade_database(db_url)
    engine = create_engine(db_url)

    assert result == HEAD_REVISION
    assert "partial_fillup" in {column["name"] for column in inspect(engine).get_columns("fuel_entries")}
    with engine.connect() as connection:
        assert connection.scalar(text("SELECT version_num FROM alembic_version")) == HEAD_REVISION


def test_repeated_upgrade_is_clean(db_url):
    from app.migrations import HEAD_REVISION, upgrade_database

    assert upgrade_database(db_url) == HEAD_REVISION
    assert upgrade_database(db_url) == HEAD_REVISION


def test_unversioned_database_is_not_ready(db_url):
    from app.migrations import require_database_current

    engine = create_engine(db_url)
    with pytest.raises(RuntimeError, match="expected .*0002_legacy_compatibility"):
        require_database_current(engine)
