"""serialize installation bootstrap registration

Revision ID: 0008_installation_state
Revises: 0007_bulk_import_operations
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


revision = "0008_installation_state"
down_revision = "0007_bulk_import_operations"
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    if "installation_state" not in inspect(bind).get_table_names():
        op.create_table(
            "installation_state",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("registration_closed", sa.Boolean(), nullable=False, server_default=sa.false()),
        )
    has_users = bind.execute(sa.text("SELECT id FROM users LIMIT 1")).first() is not None
    existing = bind.execute(sa.text("SELECT id FROM installation_state WHERE id = 1")).first()
    if existing is None:
        bind.execute(
            sa.text("INSERT INTO installation_state (id, registration_closed) VALUES (1, :closed)"),
            {"closed": has_users},
        )
    elif has_users:
        bind.execute(sa.text("UPDATE installation_state SET registration_closed = :closed WHERE id = 1"), {"closed": True})


def downgrade():
    op.drop_table("installation_state")
