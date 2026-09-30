"""Range and shape checks applied to every OCR result.

These rules live here rather than in the prompts because models do not reliably
enforce constraints stated in prose, and because they must hold identically for
every provider — only the Ollama adapter can enforce a JSON schema at all.

Nothing here is silently discarded: rejected fields are dropped and a warning is
returned alongside, so the user sees what was read and can correct it.
"""

import re
from datetime import date
from decimal import Decimal, InvalidOperation
from typing import Optional, Tuple

# No lower bound on either value beyond being positive. A floor's only unique
# catch is a decimal shifted the wrong way ($46.03 read as $4.60), which the
# derived price below catches better whenever both fields are readable — and
# they are adjacent on the display, so that is nearly always. What a floor does
# reliably is reject small partial fill-ups, which this app supports on purpose.
FUEL_COST_MAX = Decimal("300")
FUEL_GALLONS_MAX = Decimal("60")
# The price per gallon keeps a real range at both ends. Its lower bound is not a
# floor on a reading but a ratio check: $20.00 for 20.000 gallons is $1.00/gal,
# which is how a swapped pair of fields is detected. Diesel runs near $7/gal as
# of late 2026, so the upper bound has to clear that to stay usable.
FUEL_PPG_RANGE = (Decimal("1.5"), Decimal("10"))
PPG_TOLERANCE = Decimal("0.02")
MILEAGE_RANGE = (Decimal("1"), Decimal("2000000"))

EXPENSE_CATEGORIES = ("insurance", "registration", "repair", "fuel", "other")
DOCUMENT_CATEGORIES = ("insurance", "registration", "other")

MONEY_RE = re.compile(r"^[0-9]{1,5}\.[0-9]{2}$")
DIGIT_RUN_RE = re.compile(r"\d[\d\-]{5,}")
MIN_YEAR = 1900
MAX_YEARS_AHEAD = 20


def _num(value) -> Optional[Decimal]:
    """Coerce a model-supplied value to Decimal. Junk becomes None."""
    if value is None or isinstance(value, bool):
        return None
    try:
        parsed = Decimal(str(value).strip())
    except (InvalidOperation, ValueError, ArithmeticError):
        return None
    return parsed if parsed.is_finite() else None


def _date(value) -> Optional[date]:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        parsed = date.fromisoformat(text)
    except ValueError:
        return None
    if parsed.year < MIN_YEAR or parsed.year > date.today().year + MAX_YEARS_AHEAD:
        return None
    return parsed


def _in_range(value: Decimal, bounds: Tuple[Decimal, Decimal]) -> bool:
    return bounds[0] <= value <= bounds[1]


def _positive_at_most(value: Decimal, maximum: Decimal) -> bool:
    return value > 0 and value <= maximum


def clean_fuel(raw: dict) -> Tuple[dict, list]:
    """Fuel route: cost and gallons must agree on a plausible price per gallon."""
    out, warnings = {}, []

    cost = _num(raw.get("cost"))
    gallons = _num(raw.get("gallons"))

    if cost is not None and not _positive_at_most(cost, FUEL_COST_MAX):
        warnings.append(f"Ignored an implausible total of {cost}.")
        cost = None
    if gallons is not None and not _positive_at_most(gallons, FUEL_GALLONS_MAX):
        warnings.append(f"Ignored an implausible gallons reading of {gallons}.")
        gallons = None

    # The derived price catches magnitude errors and swapped fields that the
    # absolute ranges let through: 4603/12.545 is $367/gal, 20.0/20.0 is $1.00.
    if cost is not None and gallons is not None and gallons > 0:
        derived = cost / gallons
        if not _in_range(derived, FUEL_PPG_RANGE):
            warnings.append(
                f"{cost} for {gallons} gallons works out to {derived:.2f} per gallon, "
                "which is out of range — check both values."
            )
            cost = gallons = None

    if cost is not None:
        out["cost"] = float(cost)
    if gallons is not None:
        out["gallons"] = float(gallons)

    ppg = _num(raw.get("price_per_gallon"))
    if ppg is not None and _in_range(ppg, FUEL_PPG_RANGE):
        if cost is not None and gallons is not None and gallons > 0:
            # Drop only the price, never the scan: a display showing no price
            # per gallon has been observed to produce one anyway.
            if abs(ppg - (cost / gallons)) > PPG_TOLERANCE:
                ppg = None
        if ppg is not None:
            out["price_per_gallon"] = float(ppg)

    parsed_date = _date(raw.get("date"))
    if parsed_date:
        out["date"] = parsed_date.isoformat()

    location = str(raw.get("location") or "").strip()
    if location:
        out["location"] = location[:120]

    mileage = _num(raw.get("mileage"))
    if mileage is not None and MILEAGE_RANGE[0] <= mileage <= MILEAGE_RANGE[1]:
        out["mileage"] = int(mileage)

    return out, warnings


def clean_expense(raw: dict) -> Tuple[dict, list]:
    """Expense route: amount is required to be sane, category always present."""
    out, warnings = {}, []

    amount = _num(raw.get("amount"))
    if amount is not None and amount <= 0:
        warnings.append("Ignored a zero or negative amount.")
        amount = None
    if amount is not None:
        out["amount"] = float(amount)

    parsed_date = _date(raw.get("date"))
    if parsed_date:
        out["date"] = parsed_date.isoformat()
    elif raw.get("date"):
        warnings.append("Could not read a usable date — enter it manually.")

    description = str(raw.get("description") or "").strip()
    if description:
        out["description"] = description[:255]

    category = str(raw.get("category") or "").strip().lower()
    out["category"] = category if category in EXPENSE_CATEGORIES else "other"

    return out, warnings


def clean_document(raw: dict) -> Tuple[dict, list]:
    """Document-expiry route: an amount is usually absent, so it is only
    accepted in exactly the printed money shape."""
    out, warnings = {}, []

    expires_on = _date(raw.get("expires_on"))
    if expires_on:
        out["expires_on"] = expires_on.isoformat()
    elif raw.get("expires_on"):
        warnings.append("Could not read a usable expiration date — enter it manually.")

    amount_text = str(raw.get("amount") or "").strip()
    if MONEY_RE.match(amount_text):
        amount = _num(amount_text)
        if amount is not None and amount > 0:
            out["amount"] = float(amount)

    description = str(raw.get("description") or "").strip()
    if description:
        # Defence in depth: the prompt forbids policy and account numbers, but a
        # free-text field bound for storage should not rely on prompt compliance.
        if DIGIT_RUN_RE.search(description):
            warnings.append("Left the description blank because it contained what looked like a policy number.")
        else:
            out["description"] = description[:255]

    category = str(raw.get("category") or "").strip().lower()
    if category in DOCUMENT_CATEGORIES:
        out["category"] = category

    return out, warnings
