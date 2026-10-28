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


# A service invoice is the only route where the printed grand total is less
# trustworthy than the line items. Measured on a two-page dealer repair order
# (2026-10-27): every per-operation "Sub Total" read correctly in 35/35 runs at
# 1536px, while the grand total was wrong in 9/9 — fabricated from a line item
# on a page whose total box was blank, and guessed from a clipped column on the
# page that had one. So the lines are summed here and the printed total is only
# ever a cross-check the user sees, never a value the app relies on.
SERVICE_AMOUNT_MAX = Decimal("25000")
# A page total is cross-checked against the operations on the WHOLE invoice, not
# just its own page. Measured on a two-page dealer invoice whose first page is a
# "Pre-Invoice" with an empty totals box: the model fabricates a total there on
# most runs (94.95, 95.24, 93.48 observed) and each one clears the per-page check
# by sitting just above that page's own 91.70 of operations. Against the full
# invoice they are 37-38% of the 250.50 actually billed, while the real total is
# 95% of it. The band below is wide enough for a deep discount or a fee-heavy
# invoice and still rejects every phantom observed.
TOTAL_MIN_RATIO = Decimal("0.5")
TOTAL_MAX_RATIO = Decimal("1.5")
OP_CODE_RE = re.compile(r"^[A-Z0-9][A-Z0-9 ]{0,7}:\s*")
LEADING_DOT_RE = re.compile(r"^\.[0-9]{2}$")

# Only a discount-shaped line is taken. Measured over six runs on a two-page
# dealer invoice: the labelled body line `QL discount  -20.00` read 6/6, while
# anything sourced from the totals box was wrong 5/6 — that box's value column
# is offset from its labels, so "SALES TAX" reads .00 and "DISCOUNTS" reads the
# total due. One run returned the entire box as adjustments, including
# `SPECIAL ORDER DEPOSIT -20.00`, which is the same 20.00 discount restated and
# would double-count. Hence: a keyword match, a negative amount, and a dedupe.
DISCOUNT_LABEL_RE = re.compile(r"discount|coupon|credit|rebate", re.I)
# The totals box's own summary rows. They restate figures itemised elsewhere
# rather than adding a line, and the box's value column is offset from its
# labels, so whatever is read beside one is not what it says. Observed:
# `DISCOUNTS -3.34`, a value appearing nowhere on the invoice, which the
# keyword match above would otherwise accept. A real discount line carries a
# descriptive label such as "QL discount", never the bare box heading.
TOTALS_BOX_ROWS = {
    "discounts", "total due", "total", "total fees amount", "labor", "labour",
    "parts", "deductible", "sublet", "shop supplies", "hazardous materials",
    "sales tax", "sales tax or tax i.d.", "special order deposit", "sub total",
}
SIGNED_MONEY_RE = re.compile(r"^-[0-9]{1,5}\.[0-9]{2}$")


def _discount(value) -> Optional[Decimal]:
    """A printed discount: negative, two decimal places. Junk becomes None."""
    text = str(value or "").strip().replace(",", "").replace("$", "")
    if not SIGNED_MONEY_RE.match(text):
        return None
    return _num(text)


def _money(value) -> Optional[Decimal]:
    """Accept a printed money string. Dealer invoices print a zero sub total as
    '.00', which is not the shape MONEY_RE matches, so normalise that first."""
    text = str(value or "").strip().replace(",", "").replace("$", "")
    if LEADING_DOT_RE.match(text):
        text = "0" + text
    if not MONEY_RE.match(text):
        return None
    return _num(text)


def clean_maintenance(raw: dict) -> Tuple[dict, list]:
    """One page of a service invoice. Pages are merged by merge_maintenance."""
    out, warnings = {}, []

    shop = str(raw.get("shop") or "").strip()
    if shop and not DIGIT_RUN_RE.search(shop):
        out["shop"] = shop[:255]

    odometer = _num(raw.get("odometer"))
    if odometer is not None and _in_range(odometer, MILEAGE_RANGE):
        out["odometer"] = int(odometer)
    elif odometer is not None:
        # An invoice prints the repair-order number near the mileage and the two
        # get confused at low resolution; an R/O number is far out of range.
        warnings.append("Ignored an implausible odometer reading.")

    parsed_date = _date(raw.get("date"))
    if parsed_date:
        out["date"] = parsed_date.isoformat()
    elif raw.get("date"):
        warnings.append("Could not read a usable service date — enter it manually.")

    services = []
    for item in raw.get("services") or []:
        if not isinstance(item, dict):
            continue
        name = OP_CODE_RE.sub("", str(item.get("name") or "").strip()).strip()
        if not name or DIGIT_RUN_RE.search(name):
            continue
        entry = {"name": name[:255]}
        amount = _money(item.get("amount"))
        if amount is not None and 0 <= amount <= SERVICE_AMOUNT_MAX:
            entry["amount"] = float(amount)
        services.append(entry)
    out["services"] = services

    discounts = []
    seen_amounts = set()
    for item in raw.get("adjustments") or []:
        if not isinstance(item, dict):
            continue
        label = str(item.get("label") or "").strip()
        amount = _discount(item.get("amount"))
        if amount is None or not DISCOUNT_LABEL_RE.search(label):
            continue
        if label.strip().strip(":.").lower() in TOTALS_BOX_ROWS:
            continue
        if amount in seen_amounts:
            # The same discount restated by the totals box, not a second one.
            continue
        seen_amounts.add(amount)
        discounts.append({"label": label[:64], "amount": float(amount)})

    lines_total = sum(Decimal(str(s["amount"])) for s in services if "amount" in s)
    out["lines_total"] = float(lines_total)

    # A discount larger than everything on the page is a misread, not a freebie.
    discounts = [d for d in discounts if abs(Decimal(str(d["amount"]))) <= lines_total]
    if discounts:
        out["discounts"] = discounts

    printed = _money(raw.get("total"))
    if printed is not None:
        amounts = {Decimal(str(s["amount"])) for s in services if "amount" in s}
        if printed in amounts:
            # Observed 5/5 on a page whose total box was blank: the model lifted
            # the first operation's sub total and presented it as the total.
            warnings.append("Ignored a grand total that just repeated a line item.")
        elif printed < lines_total:
            # Observed 3/3: the model returned the PARTS subtotal as the total.
            warnings.append("Ignored a grand total smaller than the lines it should contain.")
        else:
            out["total"] = float(printed)

    return out, warnings


def merge_maintenance(pages: list) -> Tuple[dict, list]:
    """Combine per-page results. Lines concatenate in page order; the header
    fields are taken from the first page that produced a usable one."""
    out: dict = {"services": []}
    warnings: list = []
    totals = []

    blank_pages = 0
    seen_discounts = set()
    for cleaned, page_warnings in pages:
        warnings.extend(page_warnings)
        for discount in cleaned.get("discounts") or []:
            # A two-page invoice can restate one discount; keep it once.
            key = (discount["label"].strip().lower(), round(discount["amount"], 2))
            if key in seen_discounts:
                continue
            seen_discounts.add(key)
            out.setdefault("discounts", []).append(discount)
        page_services = cleaned.get("services") or []
        # A page that yields nothing is silent otherwise: the invoice simply
        # looks shorter and cheaper than it is. Observed once in five runs, a
        # second page returned no operations at all and the first page's 91.70
        # was presented as the whole invoice.
        if not page_services:
            blank_pages += 1
        out["services"].extend(page_services)
        for field in ("shop", "odometer", "date"):
            if field not in out and field in cleaned:
                out[field] = cleaned[field]
        if "total" in cleaned:
            totals.append(Decimal(str(cleaned["total"])))

    lines_total = sum(
        Decimal(str(s["amount"])) for s in out["services"] if "amount" in s
    )
    out["lines_total"] = float(lines_total)

    if blank_pages:
        warnings.append(
            f"{blank_pages} of the {len(pages)} pages produced no operations — "
            "rescan that page or add its services by hand."
        )

    # Each page total has already been checked against the operations printed on
    # its own page, which is where the observed misreads were caught. It is NOT
    # checked against the invoice-wide sum: a real total is legitimately smaller
    # than the sub totals it covers whenever a discount is applied — the measured
    # invoice sums to 250.50 of operations and charges 238.05 after a 20.00
    # discount. Rejecting a total for being below the lines would throw away the
    # correct answer on every discounted invoice.
    if totals and lines_total > 0:
        plausible = [
            t for t in totals
            if lines_total * TOTAL_MIN_RATIO <= t <= lines_total * TOTAL_MAX_RATIO
        ]
        if len(plausible) < len(totals):
            warnings.append(
                "Ignored a printed total that does not fit the operations on this invoice."
            )
        totals = plausible

    if totals:
        out["total"] = float(max(totals))
        printed = Decimal(str(out["total"]))
        if printed > lines_total:
            # Fees can push a total above its lines, but so does a misread sub
            # total: observed once in five runs, an operation printing labour and
            # parts rows above its own Sub Total had a part amount taken instead.
            warnings.append(
                "The receipt's total is higher than the services add up to — "
                "sales tax and shop fees sit outside the operations, but a misread "
                "cost looks the same, so check each one."
            )
        elif printed < lines_total:
            warnings.append(
                "The printed total is lower than the services add up to — "
                "a discount or credit usually accounts for the rest."
            )

    return out, warnings
