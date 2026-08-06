"""add bulk import idempotency

Revision ID: 0007_bulk_import_operations
Revises: 0006_maintenance_completion
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

revision = "0007_bulk_import_operations"
down_revision = "0006_maintenance_completion"
branch_labels = None
depends_on = None


def upgrade():
    if "bulk_import_operations" not in inspect(op.get_bind()).get_table_names():
        op.create_table(
            "bulk_import_operations",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
            sa.Column("operation_id", sa.String(36), nullable=False),
            sa.Column("vehicle_id", sa.Integer(), sa.ForeignKey("vehicles.id", ondelete="CASCADE"), nullable=False),
            sa.Column("resource", sa.String(32), nullable=False),
            sa.Column("payload_hash", sa.String(64), nullable=False),
            sa.Column("imported_count", sa.Integer(), nullable=False),
            sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
            sa.UniqueConstraint("user_id", "operation_id", name="uq_bulk_import_user_id"),
        )
        op.create_index("ix_bulk_import_operations_user_id", "bulk_import_operations", ["user_id"])
        op.create_index("ix_bulk_import_operations_vehicle_id", "bulk_import_operations", ["vehicle_id"])


def downgrade():
    op.drop_index("ix_bulk_import_operations_vehicle_id", table_name="bulk_import_operations")
    op.drop_index("ix_bulk_import_operations_user_id", table_name="bulk_import_operations")
    op.drop_table("bulk_import_operations")
