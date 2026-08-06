from dataclasses import dataclass

from sqlalchemy import Column, MetaData, String, Table, inspect
from sqlalchemy.engine import Engine

from app.database import Base
from app import models  # noqa: F401


BASELINE_REVISION = "0002_legacy_compatibility"
VERSION_TABLE = "alembic_version"
OPTIONAL_LEGACY_TABLES = {"inspection_items", "tire_events", "refresh_sessions", "storage_profiles",
                          "storage_migrations", "storage_migration_objects", "storage_cleanups",
                          "fuel_idempotency_operations", "maintenance_completion_operations",
                          "bulk_import_operations", "installation_state"}
KNOWN_ADDITIVE_COLUMNS = {
    "users": {"failed_login_attempts", "last_failed_login_at", "locked_until", "is_admin"},
    "maintenance_reminders": {"target_mileage", "reminder_miles"},
    "vehicles": {"license_plate", "tank_size_gallons", "recalls_seen", "recalls_cache", "primary_photo_id"},
    "expenses": {"expires_on"},
    "vehicle_parts": {"needs_order", "order_status"},
    "fuel_entries": {"octane", "missed_fillup", "partial_fillup"},
    "documents": {"maintenance_entry_id", "storage_profile_id", "content_type", "byte_length", "sha256"},
}
KNOWN_RETIRED_COLUMNS = {
    "vehicles": {
        "smartcar_vehicle_id",
        "smartcar_user_id",
        "smartcar_access_token",
        "smartcar_refresh_token",
        "smartcar_token_expires_at",
        "smartcar_last_synced_at",
    },
}


class UnknownSchemaError(RuntimeError):
    pass


@dataclass(frozen=True)
class ReconciliationResult:
    variant: str
    stamped_revision: str | None


def _expected_columns():
    return {table.name: set(table.columns.keys()) for table in Base.metadata.sorted_tables}


def reconcile_legacy_schema(engine: Engine) -> ReconciliationResult:
    inspector = inspect(engine)
    tables = set(inspector.get_table_names())
    if VERSION_TABLE in tables:
        return ReconciliationResult("versioned", None)
    if not tables:
        return ReconciliationResult("fresh", None)

    expected = _expected_columns()
    required_tables = set(expected) - OPTIONAL_LEGACY_TABLES
    missing_tables = required_tables - tables
    unknown_tables = tables - set(expected)
    if missing_tables or unknown_tables:
        raise UnknownSchemaError(
            f"unknown schema tables; missing={sorted(missing_tables)}, unknown={sorted(unknown_tables)}"
        )

    missing_by_table = {}
    for table_name in tables:
        actual_columns = {column["name"] for column in inspector.get_columns(table_name)}
        unknown_columns = actual_columns - expected[table_name] - KNOWN_RETIRED_COLUMNS.get(table_name, set())
        missing_columns = expected[table_name] - actual_columns
        if unknown_columns:
            raise UnknownSchemaError(f"unknown columns on {table_name}: {sorted(unknown_columns)}")
        unsupported_missing = missing_columns - KNOWN_ADDITIVE_COLUMNS.get(table_name, set())
        if unsupported_missing:
            raise UnknownSchemaError(f"missing required columns on {table_name}: {sorted(unsupported_missing)}")
        if missing_columns:
            missing_by_table[table_name] = missing_columns

        primary_key = inspector.get_pk_constraint(table_name).get("constrained_columns") or []
        if "id" in actual_columns and primary_key != ["id"]:
            raise UnknownSchemaError(f"unexpected primary key on {table_name}: {primary_key}")

    if missing_by_table or OPTIONAL_LEGACY_TABLES - tables:
        # Known partial states are stamped at the pre-compatibility revision;
        # Alembic performs the portable, observable reconciliation.
        stamp_revision = "0001_legacy_baseline"
        variant = "legacy-partial"
    else:
        stamp_revision = BASELINE_REVISION
        variant = "current"

    version_table = Table(
        VERSION_TABLE,
        MetaData(),
        Column("version_num", String(32), nullable=False, primary_key=True),
    )
    with engine.begin() as connection:
        version_table.create(connection)
        connection.execute(version_table.insert().values(version_num=stamp_revision))

    return ReconciliationResult(variant, stamp_revision)
