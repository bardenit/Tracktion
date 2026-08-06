"""Establish the legacy Tracktion schema baseline.

Revision ID: 0001_legacy_baseline
Revises:

This revision is downgrade-safe for a database created by this revision. Existing
installations are fingerprinted and stamped by ``app.schema_bootstrap`` instead.
"""

from alembic import op

from app.database import Base
from app import models  # noqa: F401


revision = "0001_legacy_baseline"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    # The baseline is a frozen declaration of the schema that existed when
    # Alembic was introduced. Later schema changes must use explicit revisions.
    Base.metadata.create_all(bind=op.get_bind())


def downgrade():
    Base.metadata.drop_all(bind=op.get_bind())
