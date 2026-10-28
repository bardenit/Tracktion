"""Group maintenance entries into visits and fix the air-filter vocabulary.

One shop visit produces several maintenance entries — an oil change, a tire
rotation, a cabin filter — that share a date, an odometer reading, a shop and a
receipt. They stay separate rows so reminder matching and per-service interval
maths keep working on `type`, and `visit_id` is what groups them for display.

The receipt gains its own `visit_id` so it remains visible from every service in
the visit rather than only from whichever entry it happened to be attached to.

`documents.maintenance_entry_id` was added by 0002 as a bare integer with no
foreign key, so deleting a maintenance entry silently orphaned any attachment.
This adds the constraint with ON DELETE SET NULL, after clearing rows that
already point at entries which no longer exist.

Revision ID: 0010_maintenance_visits
Revises: 0009_restore_configured_storage
"""
from alembic import op
import sqlalchemy as sa


revision = "0010_maintenance_visits"
down_revision = "0009_restore_configured_storage"
branch_labels = None
depends_on = None

FK_NAME = "fk_documents_maintenance_entry_id"


def _columns(bind, table):
    return {c["name"] for c in sa.inspect(bind).get_columns(table)}


def upgrade():
    bind = op.get_bind()

    if "visit_id" not in _columns(bind, "maintenance_entries"):
        op.add_column("maintenance_entries", sa.Column("visit_id", sa.String(36), nullable=True))
        op.create_index("ix_maintenance_entries_visit_id", "maintenance_entries", ["visit_id"])

    if "visit_id" not in _columns(bind, "documents"):
        op.add_column("documents", sa.Column("visit_id", sa.String(36), nullable=True))
        op.create_index("ix_documents_visit_id", "documents", ["visit_id"])

    # Clear attachments orphaned by the missing constraint before adding it.
    bind.execute(sa.text(
        "UPDATE documents SET maintenance_entry_id = NULL "
        "WHERE maintenance_entry_id IS NOT NULL AND maintenance_entry_id NOT IN "
        "(SELECT id FROM maintenance_entries)"
    ))

    # SQLite cannot ALTER a table to add a constraint, and rebuilding `documents`
    # through batch mode to gain one is not worth the risk on a table that holds
    # the only pointer to stored files. SQLite also leaves foreign keys unenforced
    # unless PRAGMA foreign_keys is on, so the constraint would buy little there.
    # Production runs Postgres, where it is both cheap and enforced; everywhere
    # else the orphan sweep above plus the application code carry the guarantee.
    if bind.dialect.name != "sqlite":
        existing = {fk["name"] for fk in sa.inspect(bind).get_foreign_keys("documents")}
        if FK_NAME not in existing:
            op.create_foreign_key(
                FK_NAME, "documents", "maintenance_entries",
                ["maintenance_entry_id"], ["id"], ondelete="SET NULL",
            )

    # `Air Filter` is ambiguous now that engine and cabin filters are separate
    # service types, and a reminder only matches an entry whose `type` string is
    # identical, so the two spellings have to be reconciled or neither matches.
    # History is renamed outright; a reminder is renamed only where the vehicle
    # has no `Engine Air Filter` reminder already, so nothing is ever duplicated
    # or deleted out from under the user.
    bind.execute(sa.text(
        "UPDATE maintenance_entries SET type = 'Engine Air Filter' WHERE type = 'Air Filter'"
    ))
    bind.execute(sa.text(
        "UPDATE maintenance_reminders SET service_type = 'Engine Air Filter' "
        "WHERE service_type = 'Air Filter' AND NOT EXISTS ("
        "  SELECT 1 FROM maintenance_reminders other "
        "  WHERE other.vehicle_id = maintenance_reminders.vehicle_id "
        "    AND other.service_type = 'Engine Air Filter')"
    ))


def downgrade():
    bind = op.get_bind()

    if bind.dialect.name != "sqlite":
        existing = {fk["name"] for fk in sa.inspect(bind).get_foreign_keys("documents")}
        if FK_NAME in existing:
            op.drop_constraint(FK_NAME, "documents", type_="foreignkey")

    if "visit_id" in _columns(bind, "documents"):
        op.drop_index("ix_documents_visit_id", table_name="documents")
        op.drop_column("documents", "visit_id")

    if "visit_id" in _columns(bind, "maintenance_entries"):
        op.drop_index("ix_maintenance_entries_visit_id", table_name="maintenance_entries")
        op.drop_column("maintenance_entries", "visit_id")
