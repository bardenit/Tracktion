"""Collapse the several spellings one fuel station arrived under.

One Costco had accumulated four names across 26 fill-ups — `Costco`, `Costco
Gasoline`, `Costco Wholesale` and `COSTCO WHOLESALE` — because the receipt
header, the pump and the driver each name it differently, and a `Marathon `
with a trailing space read as a second Marathon. Every spelling counts as its
own station anywhere station names are grouped.

Two reductions, per fleet owner. Spellings that differ only in case or
whitespace collapse onto the most used of them; a longer reading of a name
already on file collapses onto the shortest root present, so `COSTCO WHOLESALE`
becomes `Costco` but `Costcutter` is left alone. A trailing store number is
dropped, and a location that tidies to nothing becomes NULL.

The rules are copied from `app/services/station_names.py` rather than imported
from it. A migration is frozen history and must not change its behaviour
because that module was later edited; `test_station_names.py` pins both.

Revision ID: 0011_normalize_fuel_station_names
Revises: 0010_maintenance_visits
"""
from collections import Counter, defaultdict
import re

from alembic import op
import sqlalchemy as sa


revision = "0011_normalize_fuel_station_names"
down_revision = "0010_maintenance_visits"
branch_labels = None
depends_on = None

_WHITESPACE = re.compile(r"\s+")
_STORE_NUMBER = re.compile(r"\s*#\s*\d+\s*$")


def _tidy(name):
    if name is None:
        return None
    cleaned = _STORE_NUMBER.sub("", _WHITESPACE.sub(" ", name).strip()).strip()
    return cleaned or None


def _says_the_same_station(known, incoming):
    k, i = known.lower(), incoming.lower()
    return len(i) > len(k) and i.startswith(k) and not i[len(k)].isalnum()


def _reduce(counts):
    """Map every spelling in one fleet to the single name it should keep."""
    by_case = defaultdict(list)
    for name in counts:
        by_case[name.lower()].append(name)
    representative = {}
    for spellings in by_case.values():
        best = sorted(spellings, key=lambda name: (-counts[name], name))[0]
        for name in spellings:
            representative[name] = best

    distinct = sorted(set(representative.values()), key=lambda name: (len(name), name))
    root = {}
    for name in distinct:
        roots = [other for other in distinct if _says_the_same_station(other, name)]
        root[name] = min(roots, key=lambda other: (len(other), other)) if roots else name

    return {name: root[representative[name]] for name in counts}


def upgrade():
    bind = op.get_bind()
    rows = bind.execute(sa.text(
        "SELECT f.id AS id, f.location AS location, v.user_id AS user_id "
        "FROM fuel_entries f JOIN vehicles v ON v.id = f.vehicle_id "
        "WHERE f.location IS NOT NULL"
    )).fetchall()

    counts = defaultdict(Counter)
    for row in rows:
        tidied = _tidy(row.location)
        if tidied:
            counts[row.user_id][tidied] += 1
    canonical = {owner: _reduce(names) for owner, names in counts.items()}

    changes = []
    for row in rows:
        tidied = _tidy(row.location)
        target = canonical.get(row.user_id, {}).get(tidied) if tidied else None
        if target != row.location:
            changes.append({"entry_id": row.id, "location": target})

    if changes:
        bind.execute(
            sa.text("UPDATE fuel_entries SET location = :location WHERE id = :entry_id"),
            changes,
        )


def downgrade():
    """Nothing to restore — the spellings this replaced are not recorded."""
