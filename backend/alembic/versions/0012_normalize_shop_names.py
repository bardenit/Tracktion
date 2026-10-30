"""Collapse the several spellings one service shop arrived under, and fix two names.

`0011` did this for fuel stations. Service providers arrive the same way and had
not been touched: a dealer invoice heads itself `Todd Wenzel GMC` where the
driver types `Todd Wenzel`, and every spelling counts as its own shop anywhere
providers are grouped.

First the spelling fixes below, which no rule here can reach. Collapsing only
ever replaces a name with one the fleet already uses, so a name that is the only
spelling on file keeps whatever it was typed as, however it was typed —
`TodDWenzel` for a shop visited nine times, and `Loves` for a truck stop that
writes itself `Love's`. Renaming those is an edit to the rows, which is what this
is. They are matched on letters and digits alone, so a fix lands whatever the
capitalisation or spacing of what is stored, and a name not on file is a no-op.

Then two reductions, per fleet owner, now applied to both columns. Spellings that
differ only in case, spacing or punctuation collapse onto the most used of them;
a longer reading of a name already on file collapses onto the shortest root
present, so `Todd Wenzel GMC` becomes `Todd Wenzel` but `Costcutter` is left
alone. A name that tidies to nothing becomes NULL.

The fixes have to come first. With `TodDWenzel` nine times and one `Todd Wenzel
GMC`, reducing first leaves two shops — the GMC reading is not a longer reading
of a root spelled without its space — where fixing first collapses all ten.

The rules are copied from `app/services/station_names.py` rather than imported
from it. A migration is frozen history and must not change its behaviour because
that module was later edited; `test_station_names.py` pins both.

Revision ID: 0012_normalize_shop_names
Revises: 0011_normalize_station_names
"""
from collections import Counter, defaultdict
import re

from alembic import op
import sqlalchemy as sa


revision = "0012_normalize_shop_names"
down_revision = "0011_normalize_station_names"
branch_labels = None
depends_on = None

_WHITESPACE = re.compile(r"\s+")
_STORE_NUMBER = re.compile(r"\s*#\s*\d+\s*$")

# The fleet's own names, as they should read. Keyed on letters and digits only.
_LOCATION_SPELLINGS = {"loves": "Love's"}
_PROVIDER_SPELLINGS = {"toddwenzel": "Todd Wenzel", "alserra": "Al Serra"}


def _tidy(name):
    if name is None:
        return None
    cleaned = _STORE_NUMBER.sub("", _WHITESPACE.sub(" ", name).strip()).strip()
    return cleaned or None


def _letters_and_digits(name):
    return "".join(character for character in name.lower() if character.isalnum())


def _says_the_same_place(known, incoming):
    k, i = known.lower(), incoming.lower()
    return len(i) > len(k) and i.startswith(k) and not i[len(k)].isalnum()


def _reduce(counts):
    """Map every spelling in one fleet to the single name it should keep."""
    by_key = defaultdict(list)
    for name in counts:
        by_key[_letters_and_digits(name)].append(name)
    representative = {}
    for spellings in by_key.values():
        best = sorted(spellings, key=lambda name: (-counts[name], name))[0]
        for name in spellings:
            representative[name] = best

    distinct = sorted(set(representative.values()), key=lambda name: (len(name), name))
    root = {}
    for name in distinct:
        roots = [other for other in distinct if _says_the_same_place(other, name)]
        root[name] = min(roots, key=lambda other: (len(other), other)) if roots else name

    return {name: root[representative[name]] for name in counts}


def _normalize(bind, table, column, spellings):
    """Reduce one column's spellings, then apply the renames. Table and column
    are literals from this module, never anything a caller supplies."""
    rows = bind.execute(sa.text(
        f"SELECT e.id AS id, e.{column} AS value, v.user_id AS user_id "
        f"FROM {table} e JOIN vehicles v ON v.id = e.vehicle_id "
        f"WHERE e.{column} IS NOT NULL"
    )).fetchall()

    def fixed(value):
        tidied = _tidy(value)
        if tidied is None:
            return None
        return spellings.get(_letters_and_digits(tidied), tidied)

    counts = defaultdict(Counter)
    for row in rows:
        name = fixed(row.value)
        if name:
            counts[row.user_id][name] += 1
    canonical = {owner: _reduce(names) for owner, names in counts.items()}

    changes = []
    for row in rows:
        name = fixed(row.value)
        target = canonical.get(row.user_id, {}).get(name) if name else None
        if target != row.value:
            changes.append({"entry_id": row.id, "value": target})

    if changes:
        bind.execute(
            sa.text(f"UPDATE {table} SET {column} = :value WHERE id = :entry_id"),
            changes,
        )


def upgrade():
    bind = op.get_bind()
    _normalize(bind, "fuel_entries", "location", _LOCATION_SPELLINGS)
    _normalize(bind, "maintenance_entries", "service_provider", _PROVIDER_SPELLINGS)


def downgrade():
    """Nothing to restore — the spellings this replaced are not recorded."""
