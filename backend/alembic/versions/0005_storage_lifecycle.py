"""Add durable storage identity, migration ledger, and cleanup intent.

Revision ID: 0005_storage_lifecycle
Revises: 0004_offline_fuel_idempotency
"""
import uuid

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

revision = "0005_storage_lifecycle"
down_revision = "0004_offline_fuel_idempotency"
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    tables = inspect(bind).get_table_names()
    vehicle_columns = {c["name"] for c in inspect(bind).get_columns("vehicles")}
    if "storage_profiles" not in tables:
        op.create_table("storage_profiles", sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("profile_uuid", sa.String(36), nullable=False, unique=True),
            sa.Column("backend_type", sa.String(20), nullable=False), sa.Column("configuration", sa.JSON(), nullable=False),
            sa.Column("credential_version", sa.Integer(), nullable=False, server_default="1"),
            sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()))
        op.create_index("ix_storage_profiles_profile_uuid", "storage_profiles", ["profile_uuid"], unique=True)
        op.create_index("ix_storage_profiles_is_active", "storage_profiles", ["is_active"])
    columns = {c["name"] for c in inspect(bind).get_columns("documents")}
    for name, column in (
        ("storage_profile_id", sa.Column("storage_profile_id", sa.Integer(), sa.ForeignKey("storage_profiles.id"), nullable=True)),
        ("content_type", sa.Column("content_type", sa.String(100), nullable=True)),
        ("byte_length", sa.Column("byte_length", sa.Integer(), nullable=True)),
        ("sha256", sa.Column("sha256", sa.String(64), nullable=True)),
    ):
        if name not in columns:
            op.add_column("documents", column)
    document_indexes = {index["name"] for index in inspect(bind).get_indexes("documents")}
    if "ix_documents_storage_profile_id" not in document_indexes:
        op.create_index("ix_documents_storage_profile_id", "documents", ["storage_profile_id"])
    profile_id = bind.execute(sa.text("SELECT id FROM storage_profiles WHERE is_active = :active"), {"active": True}).scalar()
    if profile_id is None:
        profile_uuid = str(uuid.uuid4())
        profiles = sa.table("storage_profiles", sa.column("profile_uuid", sa.String),
            sa.column("backend_type", sa.String), sa.column("configuration", sa.JSON),
            sa.column("credential_version", sa.Integer), sa.column("is_active", sa.Boolean))
        op.bulk_insert(profiles, [{"profile_uuid": profile_uuid, "backend_type": "local", "configuration": {},
                                  "credential_version": 1, "is_active": True}])
        profile_id = bind.execute(sa.text("SELECT id FROM storage_profiles WHERE profile_uuid = :uuid"), {"uuid": profile_uuid}).scalar()
    bind.execute(sa.text("UPDATE documents SET storage_profile_id = :profile WHERE storage_profile_id IS NULL"), {"profile": profile_id})
    if "primary_photo_id" not in vehicle_columns:
        with op.batch_alter_table("vehicles") as batch:
            batch.add_column(sa.Column("primary_photo_id", sa.Integer(), nullable=True))
            batch.create_foreign_key("fk_vehicles_primary_photo", "documents", ["primary_photo_id"], ["id"], ondelete="SET NULL")
            batch.create_index("ix_vehicles_primary_photo_id", ["primary_photo_id"])
    if "storage_migrations" not in tables:
        op.create_table("storage_migrations", sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("source_profile_id", sa.Integer(), sa.ForeignKey("storage_profiles.id"), nullable=False),
            sa.Column("destination_profile_id", sa.Integer(), sa.ForeignKey("storage_profiles.id"), nullable=False),
            sa.Column("candidate_credential_version", sa.Integer(), nullable=False), sa.Column("state", sa.String(20), nullable=False),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()))
        op.create_index("ix_storage_migrations_state", "storage_migrations", ["state"])
    if "storage_migration_objects" not in tables:
        op.create_table("storage_migration_objects", sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("migration_id", sa.Integer(), sa.ForeignKey("storage_migrations.id", ondelete="CASCADE"), nullable=False),
            sa.Column("document_id", sa.Integer(), sa.ForeignKey("documents.id", ondelete="CASCADE"), nullable=False),
            sa.Column("source_profile_id", sa.Integer(), nullable=False), sa.Column("destination_profile_id", sa.Integer(), nullable=False),
            sa.Column("source_key", sa.String(512), nullable=False), sa.Column("destination_key", sa.String(512), nullable=False),
            sa.Column("byte_length", sa.Integer(), nullable=False), sa.Column("sha256", sa.String(64), nullable=False),
            sa.Column("state", sa.String(20), nullable=False), sa.Column("error", sa.Text()),
            sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.UniqueConstraint("migration_id", "document_id", name="uq_storage_migration_document"))
        op.create_index("ix_storage_migration_objects_migration_id", "storage_migration_objects", ["migration_id"])
        op.create_index("ix_storage_migration_objects_state", "storage_migration_objects", ["state"])
    if "storage_cleanups" not in tables:
        op.create_table("storage_cleanups", sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("storage_profile_id", sa.Integer(), sa.ForeignKey("storage_profiles.id"), nullable=False),
            sa.Column("object_key", sa.String(512), nullable=False), sa.Column("state", sa.String(20), nullable=False),
            sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"), sa.Column("last_error", sa.Text()),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.UniqueConstraint("storage_profile_id", "object_key", name="uq_storage_cleanup_object"))
        op.create_index("ix_storage_cleanups_storage_profile_id", "storage_cleanups", ["storage_profile_id"])
        op.create_index("ix_storage_cleanups_state", "storage_cleanups", ["state"])


def downgrade():
    raise RuntimeError("0005_storage_lifecycle is forward-only")
