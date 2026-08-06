"""Restore configured object storage and legacy primary photos.

Revision ID: 0009_restore_configured_storage
Revises: 0008_installation_state
"""
import uuid

from alembic import op
import sqlalchemy as sa

from app.data_config import get_config


revision = "0009_restore_configured_storage"
down_revision = "0008_installation_state"
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    storage_config = dict(get_config().get("storage", {}))
    configured_type = storage_config.get("type", "local").lower()
    active_profile = bind.execute(sa.text(
        "SELECT id, backend_type, configuration FROM storage_profiles WHERE is_active = :active"
    ), {"active": True}).mappings().first()

    if configured_type != "local" and active_profile and active_profile["backend_type"] == "local":
        profile_uuid = str(uuid.uuid4())
        profiles = sa.table(
            "storage_profiles",
            sa.column("profile_uuid", sa.String),
            sa.column("backend_type", sa.String),
            sa.column("configuration", sa.JSON),
            sa.column("credential_version", sa.Integer),
            sa.column("is_active", sa.Boolean),
        )
        bind.execute(profiles.insert().values(
            profile_uuid=profile_uuid,
            backend_type=configured_type,
            configuration=storage_config,
            credential_version=1,
            is_active=True,
        ))
        configured_profile_id = bind.execute(sa.text(
            "SELECT id FROM storage_profiles WHERE profile_uuid = :uuid"
        ), {"uuid": profile_uuid}).scalar_one()
        bind.execute(sa.text(
            "UPDATE documents SET storage_profile_id = :configured WHERE storage_profile_id = :local"
        ), {"configured": configured_profile_id, "local": active_profile["id"]})
        bind.execute(sa.text(
            "UPDATE storage_profiles SET is_active = :inactive WHERE id != :configured"
        ), {"inactive": False, "configured": configured_profile_id})

    bind.execute(sa.text(
        "UPDATE vehicles SET primary_photo_id = ("
        "SELECT MIN(documents.id) FROM documents "
        "WHERE documents.vehicle_id = vehicles.id AND documents.document_type = 'vehicle_photo'"
        ") WHERE primary_photo_id IS NULL AND EXISTS ("
        "SELECT 1 FROM documents "
        "WHERE documents.vehicle_id = vehicles.id AND documents.document_type = 'vehicle_photo'"
        ")"
    ))


def downgrade():
    raise RuntimeError("0009_restore_configured_storage is forward-only")
