"""Collapsing the several spellings one station or shop arrives under.

A name reaches the database several ways: typed into a form, read off a receipt
by OCR, or imported in bulk. One Costco produced four spellings — `Costco`,
`Costco Gasoline`, `Costco Wholesale` and `COSTCO WHOLESALE` — because the
receipt header, the pump display and the driver each name it differently, and
every spelling then reads as a different station. Service shops arrive the same
way: a dealer's invoice heads itself `Todd Wenzel GMC` where the driver types
`Todd Wenzel`.

The same rules serve both columns — `fuel_entries.location` through
`known_station_names`, and `maintenance_entries.service_provider` through
`known_shop_names`.

The rule here is deliberately conservative: a name is only ever replaced by one
the fleet already uses. Nothing in this module carries a list of chains or
invents a canonical name, so an unfamiliar one is stored exactly as given and
becomes the spelling that later variants collapse onto.

Two names say the same thing when their letters and digits match, so `Loves`
reaches `Love's` and `TodDWenzel` reaches `Todd Wenzel`. Collapsing a *longer*
reading onto a shorter one is stricter and keeps the word boundary, so `Costco
Wholesale` is a Costco while `Costcutter` is a different shop.

The one thing this cannot do is lengthen a name. With `Costco` already on file,
saving `Costco Fenton` stores `Costco`, because by these rules that is the same
station said at greater length. Renaming is an edit to the rows already stored —
see migration `0012_normalize_shop_names` — not something a new entry can
express.
"""

import re
from typing import Iterable, Optional

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models import FuelEntry, MaintenanceEntry, Vehicle

_WHITESPACE = re.compile(r"\s+")

# A trailing store number — `#4421`, `# 4421` — is never part of the brand, and
# left in place it makes every location of a chain its own station.
_STORE_NUMBER = re.compile(r"\s*#\s*\d+\s*$")


def tidy_name(name: Optional[str]) -> Optional[str]:
    """Trim, collapse internal whitespace, drop a trailing store number.

    Returns None for anything that ends up empty, so a blank name is stored as
    NULL rather than as an empty string.
    """
    if name is None:
        return None
    cleaned = _STORE_NUMBER.sub("", _WHITESPACE.sub(" ", name).strip()).strip()
    return cleaned or None


def _letters_and_digits(name: str) -> str:
    """What two spellings of one name have in common.

    Case, spacing and punctuation vary with whoever typed the name, and none of
    them tells two places apart: `Love's`, `Loves` and `LOVES` are one truck
    stop, and `TodDWenzel` is the dealer written `Todd Wenzel`.
    """
    return "".join(character for character in name.lower() if character.isalnum())


def _says_the_same_place(known: str, incoming: str) -> bool:
    """True when `incoming` is `known` said at greater length.

    Stricter than `_letters_and_digits`, because dropping the spacing here would
    make any name that merely starts with another a longer reading of it. The
    match has to land on a word boundary: `Costco Wholesale` is a longer reading
    of `Costco`, while `Costcutter` is a different shop.
    """
    k, i = known.lower(), incoming.lower()
    return len(i) > len(k) and i.startswith(k) and not i[len(k)].isalnum()


def canonical_name(name: Optional[str], known: Iterable[str]) -> Optional[str]:
    """Return the spelling to store for `name`.

    `known` is the names already in use, most used first; the first one that
    matches wins, so the fleet's established spelling is what survives.
    """
    incoming = tidy_name(name)
    if incoming is None:
        return None

    seen: list[str] = []
    for candidate in known:
        tidied = tidy_name(candidate)
        if tidied and tidied not in seen:
            seen.append(tidied)

    # The brand root is checked before an exact match so that the collapsing
    # converges: with both `Costco` and `Costco Gasoline` on file, a new
    # `Costco Gasoline` still lands on `Costco` rather than keeping itself
    # alive. The shortest root wins; ties go to the most used spelling.
    roots = [candidate for candidate in seen if _says_the_same_place(candidate, incoming)]
    if roots:
        return min(roots, key=len)
    spoken = _letters_and_digits(incoming)
    for candidate in seen:
        if _letters_and_digits(candidate) == spoken:
            return candidate
    return incoming


def _names_in_use(db: Session, owner_user_id: int, model, column) -> list[str]:
    """One owner's spellings of `column`, most used first.

    Scoped to the fleet's owner rather than to whoever is logged in, so an
    editor filling up or servicing someone else's vehicle writes that fleet's
    spellings.
    """
    uses = func.count(model.id)
    rows = (
        db.query(column, uses)
        .join(Vehicle, Vehicle.id == model.vehicle_id)
        .filter(Vehicle.user_id == owner_user_id, column.isnot(None), column != "")
        .group_by(column)
        .order_by(uses.desc(), column.asc())
        .all()
    )
    return [row[0] for row in rows]


def known_station_names(db: Session, owner_user_id: int) -> list[str]:
    """Fuel station names already in use across one owner's fleet."""
    return _names_in_use(db, owner_user_id, FuelEntry, FuelEntry.location)


def known_shop_names(db: Session, owner_user_id: int) -> list[str]:
    """Service providers already in use across one owner's fleet."""
    return _names_in_use(db, owner_user_id, MaintenanceEntry, MaintenanceEntry.service_provider)
