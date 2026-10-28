"""Collapsing the several spellings one fuel station arrives under.

A station name reaches the database three ways: typed into the fuel form, read
off a receipt by OCR, or imported in bulk. One Costco produced four spellings —
`Costco`, `Costco Gasoline`, `Costco Wholesale` and `COSTCO WHOLESALE` —
because the receipt header, the pump display and the driver each name it
differently, and every spelling then reads as a different station.

The rule here is deliberately conservative: a name is only ever replaced by one
the fleet already uses. Nothing in this module carries a list of chains or
invents a canonical brand name, so an unfamiliar station is stored exactly as
given and becomes the spelling that later variants collapse onto.

The one thing this cannot do is lengthen a name. With `Costco` already on file,
saving `Costco Fenton` stores `Costco`, because by these rules that is the same
station said at greater length. Renaming a station is an edit to the existing
rows, not something a new entry can express.
"""

import re
from typing import Iterable, Optional

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models import FuelEntry, Vehicle

_WHITESPACE = re.compile(r"\s+")

# A trailing store number — `#4421`, `# 4421` — is never part of the brand, and
# left in place it makes every location of a chain its own station.
_STORE_NUMBER = re.compile(r"\s*#\s*\d+\s*$")


def tidy_station(name: Optional[str]) -> Optional[str]:
    """Trim, collapse internal whitespace, drop a trailing store number.

    Returns None for anything that ends up empty, so a blank location is stored
    as NULL rather than as an empty string.
    """
    if name is None:
        return None
    cleaned = _STORE_NUMBER.sub("", _WHITESPACE.sub(" ", name).strip()).strip()
    return cleaned or None


def _says_the_same_station(known: str, incoming: str) -> bool:
    """True when `incoming` is `known` said at greater length.

    The match has to land on a word boundary: `Costco Wholesale` is a longer
    reading of `Costco`, while `Costcutter` is a different shop.
    """
    k, i = known.lower(), incoming.lower()
    return len(i) > len(k) and i.startswith(k) and not i[len(k)].isalnum()


def canonical_station(name: Optional[str], known: Iterable[str]) -> Optional[str]:
    """Return the spelling to store for `name`.

    `known` is the station names already in use, most used first; the first one
    that matches wins, so the fleet's established spelling is what survives.
    """
    incoming = tidy_station(name)
    if incoming is None:
        return None

    seen: list[str] = []
    for candidate in known:
        tidied = tidy_station(candidate)
        if tidied and tidied not in seen:
            seen.append(tidied)

    # The brand root is checked before an exact match so that the collapsing
    # converges: with both `Costco` and `Costco Gasoline` on file, a new
    # `Costco Gasoline` still lands on `Costco` rather than keeping itself
    # alive. The shortest root wins; ties go to the most used spelling.
    roots = [candidate for candidate in seen if _says_the_same_station(candidate, incoming)]
    if roots:
        return min(roots, key=len)
    for candidate in seen:
        if candidate.lower() == incoming.lower():
            return candidate
    return incoming


def known_station_names(db: Session, owner_user_id: int) -> list[str]:
    """Station names already in use across one owner's fleet, most used first.

    Scoped to the fleet's owner rather than to whoever is logged in, so an
    editor filling up someone else's vehicle writes that fleet's spellings.
    """
    rows = (
        db.query(FuelEntry.location, func.count(FuelEntry.id).label("uses"))
        .join(Vehicle, Vehicle.id == FuelEntry.vehicle_id)
        .filter(
            Vehicle.user_id == owner_user_id,
            FuelEntry.location.isnot(None),
            FuelEntry.location != "",
        )
        .group_by(FuelEntry.location)
        .order_by(func.count(FuelEntry.id).desc(), FuelEntry.location.asc())
        .all()
    )
    return [row[0] for row in rows]
