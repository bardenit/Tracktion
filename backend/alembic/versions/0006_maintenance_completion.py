"""add maintenance completion idempotency

Revision ID: 0006_maintenance_completion
Revises: 0005_storage_lifecycle
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


revision = "0006_maintenance_completion"
down_revision = "0005_storage_lifecycle"
branch_labels = None
depends_on = None


def upgrade():
    if "maintenance_completion_operations" not in inspect(op.get_bind()).get_table_names():
        op.create_table(
            "maintenance_completion_operations",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
            sa.Column("operation_id", sa.String(36), nullable=False),
            sa.Column("vehicle_id", sa.Integer(), sa.ForeignKey("vehicles.id", ondelete="CASCADE"), nullable=False),
            sa.Column("reminder_id", sa.Integer(), sa.ForeignKey("maintenance_reminders.id", ondelete="CASCADE"), nullable=False),
            sa.Column("payload_hash", sa.String(64), nullable=False),
            sa.Column("maintenance_entry_id", sa.Integer(), sa.ForeignKey("maintenance_entries.id", ondelete="CASCADE"), nullable=False, unique=True),
            sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
            sa.UniqueConstraint("user_id", "operation_id", name="uq_maintenance_completion_user_id"),
        )
        op.create_index("ix_maintenance_completion_operations_user_id", "maintenance_completion_operations", ["user_id"])
        op.create_index("ix_maintenance_completion_operations_vehicle_id", "maintenance_completion_operations", ["vehicle_id"])

    # Preserve complete legacy manual baselines as source history before derived
    # reminder fields become read-only.
    op.execute(sa.text("""
        INSERT INTO maintenance_entries (vehicle_id, date, mileage, type, cost, notes)
        SELECT r.vehicle_id, r.last_performed_date, r.last_performed_mileage,
               r.service_type, 0, 'Migrated reminder baseline'
        FROM maintenance_reminders r
        WHERE r.last_performed_date IS NOT NULL
          AND r.last_performed_mileage IS NOT NULL
          AND NOT EXISTS (
              SELECT 1 FROM maintenance_entries e
              WHERE e.vehicle_id = r.vehicle_id
                AND e.type = r.service_type
                AND e.date = r.last_performed_date
                AND e.mileage = r.last_performed_mileage
          )
    """))


def downgrade():
    op.drop_index("ix_maintenance_completion_operations_vehicle_id", table_name="maintenance_completion_operations")
    op.drop_index("ix_maintenance_completion_operations_user_id", table_name="maintenance_completion_operations")
    op.drop_table("maintenance_completion_operations")
