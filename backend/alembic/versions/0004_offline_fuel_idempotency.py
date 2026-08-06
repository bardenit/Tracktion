"""Add user-scoped offline fuel idempotency operations.

Revision ID: 0004_offline_fuel_idempotency
Revises: 0003_admin_and_refresh_sessions
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect


revision = "0004_offline_fuel_idempotency"
down_revision = "0003_admin_and_refresh_sessions"
branch_labels = None
depends_on = None


def upgrade():
    if "fuel_idempotency_operations" in inspect(op.get_bind()).get_table_names():
        return
    op.create_table(
        "fuel_idempotency_operations",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("operation_id", sa.String(36), nullable=False),
        sa.Column("vehicle_id", sa.Integer(), sa.ForeignKey("vehicles.id", ondelete="CASCADE"), nullable=False),
        sa.Column("payload_hash", sa.String(64), nullable=False),
        sa.Column("fuel_entry_id", sa.Integer(), sa.ForeignKey("fuel_entries.id", ondelete="CASCADE"), nullable=False, unique=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("user_id", "operation_id", name="uq_fuel_operation_user_id"),
    )
    op.create_index("ix_fuel_idempotency_operations_user_id", "fuel_idempotency_operations", ["user_id"])
    op.create_index("ix_fuel_idempotency_operations_vehicle_id", "fuel_idempotency_operations", ["vehicle_id"])


def downgrade():
    raise RuntimeError("0004_offline_fuel_idempotency is forward-only")
