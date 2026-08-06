import pytest
from sqlalchemy import create_engine, inspect, text


def test_current_schema_is_recognized_and_stamped(db_url):
    from app.database import Base
    from app import models  # noqa: F401
    from app.schema_bootstrap import BASELINE_REVISION, reconcile_legacy_schema

    engine = create_engine(db_url)
    Base.metadata.create_all(engine)

    result = reconcile_legacy_schema(engine)

    assert result.variant == "current"
    assert result.stamped_revision == BASELINE_REVISION
    assert inspect(engine).get_table_names().count("alembic_version") == 1


def test_unknown_schema_drift_is_rejected_without_stamp(db_url):
    from app.database import Base
    from app import models  # noqa: F401
    from app.schema_bootstrap import UnknownSchemaError, reconcile_legacy_schema

    engine = create_engine(db_url)
    Base.metadata.create_all(engine)
    with engine.begin() as connection:
        connection.execute(text("ALTER TABLE users ADD COLUMN unexplained_drift VARCHAR(20)"))

    with pytest.raises(UnknownSchemaError, match="unexplained_drift"):
        reconcile_legacy_schema(engine)

    assert "alembic_version" not in inspect(engine).get_table_names()


def test_retired_smartcar_columns_are_accepted_and_preserved(db_url):
    from app.database import Base
    from app import models  # noqa: F401
    from app.migrations import HEAD_REVISION, upgrade_database

    engine = create_engine(db_url)
    Base.metadata.create_all(engine)
    retired_columns = {
        "smartcar_vehicle_id": "VARCHAR(255)",
        "smartcar_user_id": "VARCHAR(255)",
        "smartcar_access_token": "TEXT",
        "smartcar_refresh_token": "TEXT",
        "smartcar_token_expires_at": "TIMESTAMP",
        "smartcar_last_synced_at": "TIMESTAMP",
    }
    with engine.begin() as connection:
        for column_name, column_type in retired_columns.items():
            connection.execute(text(f"ALTER TABLE vehicles ADD COLUMN {column_name} {column_type}"))

    assert upgrade_database(db_url) == HEAD_REVISION
    actual_columns = {column["name"] for column in inspect(engine).get_columns("vehicles")}
    assert retired_columns.keys() <= actual_columns


def test_pre_partial_fill_schema_is_reconciled_by_alembic(db_url):
    from app.database import Base
    from app import models  # noqa: F401
    from app.migrations import HEAD_REVISION, upgrade_database
    from app.schema_bootstrap import reconcile_legacy_schema

    engine = create_engine(db_url)
    Base.metadata.create_all(engine)
    with engine.begin() as connection:
        connection.execute(text("ALTER TABLE fuel_entries DROP COLUMN partial_fillup"))

    result = reconcile_legacy_schema(engine)
    assert result.variant == "legacy-partial"
    assert result.stamped_revision == "0001_legacy_baseline"

    assert upgrade_database(db_url) == HEAD_REVISION
    assert "partial_fillup" in {column["name"] for column in inspect(engine).get_columns("fuel_entries")}
