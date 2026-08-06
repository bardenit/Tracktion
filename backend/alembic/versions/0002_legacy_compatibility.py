"""Reconcile the known ad-hoc compatibility additions.

Revision ID: 0002_legacy_compatibility
Revises: 0001_legacy_baseline

Forward-only: removing compatibility columns can destroy deployment data.
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect


revision = "0002_legacy_compatibility"
down_revision = "0001_legacy_baseline"
branch_labels = None
depends_on = None


ADDITIVE_COLUMNS = {
    "users": [
        sa.Column("failed_login_attempts", sa.Integer(), server_default="0", nullable=True),
        sa.Column("last_failed_login_at", sa.DateTime(), nullable=True),
        sa.Column("locked_until", sa.DateTime(), nullable=True),
    ],
    "maintenance_reminders": [
        sa.Column("target_mileage", sa.Float(), nullable=True),
        sa.Column("reminder_miles", sa.Integer(), nullable=True),
    ],
    "vehicles": [
        sa.Column("license_plate", sa.String(20), nullable=True),
        sa.Column("tank_size_gallons", sa.Float(), nullable=True),
        sa.Column("recalls_seen", sa.JSON(), nullable=True),
        sa.Column("recalls_cache", sa.JSON(), nullable=True),
    ],
    "expenses": [sa.Column("expires_on", sa.Date(), nullable=True)],
    "vehicle_parts": [
        sa.Column("needs_order", sa.Boolean(), server_default=sa.false(), nullable=True),
        sa.Column("order_status", sa.String(20), nullable=True),
    ],
    "fuel_entries": [
        sa.Column("octane", sa.Integer(), nullable=True),
        sa.Column("missed_fillup", sa.Boolean(), server_default=sa.false(), nullable=True),
        sa.Column("partial_fillup", sa.Boolean(), server_default=sa.false(), nullable=True),
    ],
    "documents": [sa.Column("maintenance_entry_id", sa.Integer(), nullable=True)],
}


def _column_names(table_name):
    return {column["name"] for column in inspect(op.get_bind()).get_columns(table_name)}


def upgrade():
    inspector = inspect(op.get_bind())
    tables = set(inspector.get_table_names())
    for table_name, columns in ADDITIVE_COLUMNS.items():
        present = _column_names(table_name)
        for column in columns:
            if column.name not in present:
                op.add_column(table_name, column)

    if "inspection_items" not in tables:
        op.create_table(
            "inspection_items",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("vehicle_id", sa.Integer(), sa.ForeignKey("vehicles.id"), nullable=False),
            sa.Column("name", sa.String(255), nullable=False),
            sa.Column("category", sa.String(100), server_default="general", nullable=False),
            sa.Column("last_checked_at", sa.DateTime()),
            sa.Column("order_index", sa.Integer(), server_default="0"),
            sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
        )
    if "tire_events" not in tables:
        op.create_table(
            "tire_events",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("vehicle_id", sa.Integer(), sa.ForeignKey("vehicles.id"), nullable=False),
            sa.Column("event_type", sa.String(50), nullable=False),
            sa.Column("date", sa.Date(), nullable=False),
            sa.Column("mileage", sa.Float(), nullable=False),
            sa.Column("brand", sa.String(100)),
            sa.Column("size", sa.String(50)),
            sa.Column("pressure_fl", sa.Float()),
            sa.Column("pressure_fr", sa.Float()),
            sa.Column("pressure_rl", sa.Float()),
            sa.Column("pressure_rr", sa.Float()),
            sa.Column("tread_fl", sa.Float()),
            sa.Column("tread_fr", sa.Float()),
            sa.Column("tread_rl", sa.Float()),
            sa.Column("tread_rr", sa.Float()),
            sa.Column("notes", sa.Text()),
            sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
        )

    op.execute("UPDATE maintenance_reminders SET is_overdue = false WHERE is_overdue IS NULL")
    op.execute(
        "UPDATE vehicle_parts SET order_status = 'needs_order' "
        "WHERE needs_order = true AND order_status IS NULL"
    )


def downgrade():
    raise RuntimeError("0002_legacy_compatibility is forward-only")
