"""Add installation administrator and refresh sessions.

Revision ID: 0003_admin_and_refresh_sessions
Revises: 0002_legacy_compatibility
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect


revision = "0003_admin_and_refresh_sessions"
down_revision = "0002_legacy_compatibility"
branch_labels = None
depends_on = None


def upgrade():
    inspector = inspect(op.get_bind())
    user_columns = {column["name"] for column in inspector.get_columns("users")}
    if "is_admin" not in user_columns:
        op.add_column("users", sa.Column("is_admin", sa.Boolean(), server_default=sa.false(), nullable=False))
    op.execute(
        "UPDATE users SET is_admin = true WHERE id = "
        "(SELECT id FROM users ORDER BY created_at ASC, id ASC LIMIT 1)"
    )
    if "refresh_sessions" not in inspector.get_table_names():
        op.create_table(
            "refresh_sessions",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
            sa.Column("jti_hash", sa.String(64), nullable=False, unique=True),
            sa.Column("family_id", sa.String(36), nullable=False),
            sa.Column("expires_at", sa.DateTime(), nullable=False),
            sa.Column("revoked_at", sa.DateTime()),
            sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        )
        op.create_index("ix_refresh_sessions_user_id", "refresh_sessions", ["user_id"])
        op.create_index("ix_refresh_sessions_jti_hash", "refresh_sessions", ["jti_hash"], unique=True)
        op.create_index("ix_refresh_sessions_family_id", "refresh_sessions", ["family_id"])


def downgrade():
    raise RuntimeError("0003_admin_and_refresh_sessions is forward-only")
