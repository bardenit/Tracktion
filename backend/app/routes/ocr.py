import json
import logging
import re
from fastapi import APIRouter, Depends, Form, HTTPException, Response, UploadFile, File
from starlette.concurrency import run_in_threadpool
from app.auth import get_current_user
from app.models import User
from app.data_config import get_ocr_provider, get_ocr_settings
from app.services import ocr_validation
from app.services.ocr_providers import (
    ProviderError,
    ProviderUnreachable,
    build_provider,
)

# Any authenticated user may scan. A scan extracts data and writes nothing;
# saving it goes through the fuel and expense routes, which enforce write
# access per vehicle. Configuring providers stays admin-only, in settings.
router = APIRouter()

MAX_IMAGE_BYTES = 10 * 1024 * 1024

# Prompt notes, measured against qwen3.5:4b (see CHANGES_OLLAMA_MIGRATION.md):
# the explicit decimal-place counts eliminate 100x magnitude errors, and asking
# the model to reconcile its own arithmetic produces consistent wrong answers,
# so the sanity ranges live in ocr_validation instead.
_FUEL_PROMPT = (
    "This photo shows either a gas pump display or a printed fuel receipt. "
    "Transcribe ONLY values physically shown in the image. Do not compute, derive, infer, or "
    "correct any value. Do not fill in a field that is not printed. Copy every digit shown, "
    "including all decimal places. Decimal-place rules, which override what you think you see if "
    "a decimal point is faint: the total cost always has exactly 2 digits after the decimal point; "
    "the gallons value always has exactly 3 digits after the decimal point; the price per gallon "
    "always has exactly 3 digits after the decimal point. On a receipt the total may be labelled "
    "FUEL SALE, TOTAL or SALE, the gallons may be labelled GALLONS or GAL, and the price per "
    "gallon may be labelled PRICE/G or PPG. An odometer reading is printed on some fleet receipts "
    "and never on a pump display; omit it unless it is actually shown. Return ONLY valid JSON with "
    "these keys, omitting any key whose value is not printed in the image: "
    '{"cost": total dollar amount, "gallons": gallons, "price_per_gallon": price per gallon, '
    '"date": transaction date as YYYY-MM-DD, "location": station brand name, '
    '"mileage": odometer reading in whole miles}'
)

_FUEL_SCHEMA = {
    "type": "object",
    "properties": {
        "cost": {"type": "string", "pattern": r"^[0-9]{1,3}\.[0-9]{2}$"},
        "gallons": {"type": "string", "pattern": r"^[0-9]{1,2}\.[0-9]{3}$"},
        "price_per_gallon": {"type": "string", "pattern": r"^[0-9]\.[0-9]{3}$"},
        # date, location and mileage are transformed or usually absent, so they
        # stay unconstrained: a pattern removes the model's ability to decline.
        "date": {"type": "string"},
        "location": {"type": "string"},
        "mileage": {"type": "string"},
    },
}

_EXPENSE_PROMPT = (
    "Extract expense details from this receipt or purchase confirmation image. "
    "Transcribe ONLY what is printed. Do not compute, infer, or guess any value.\n"
    "amount: the final total charged. It always has exactly 2 digits after the decimal point. "
    "If several totals are printed, take the one labelled TOTAL, Total or Amount Due. Ignore "
    "subtotals, taxes, processing fees and per-item prices.\n"
    "date: the date the purchase was made, formatted YYYY-MM-DD. Apply these rules in order:\n"
    "  1. If the printed date has a four-digit year, use that year.\n"
    "  2. If the printed date has a TWO-digit year, such as 12/16/22 or 09/12/26, that is still a "
    "printed year. Expand it into the 2000s: 22 means 2022, 26 means 2026. Do not omit the date.\n"
    "  3. If NO year is printed at all, for example a date showing only a weekday, month and day "
    "such as 'Sun, Dec 7', you MUST omit the date field entirely. Never infer a year. Never assume "
    "the current year.\n"
    "  4. If several dates are printed, prefer the transaction or payment date over a service "
    "period.\n"
    "description: at most 6 words naming the merchant and what was bought. No dates, no amounts.\n"
    "category: exactly one of these five values, chosen by what the purchase was for:\n"
    "  fuel - gasoline, diesel, or any fuel purchase\n"
    "  repair - parts, maintenance, service, labour, tyres, oil changes\n"
    "  insurance - an insurance premium or policy payment\n"
    "  registration - vehicle registration, title, plates, inspection fees\n"
    "  other - anything else, including parking, tolls, car washes, rentals\n"
    "Return ONLY valid JSON. Omit any field whose value is not printed in the image."
)

# The enum appears in the prompt as well as the schema: the schema constrains
# which strings may be emitted but conveys none of their meaning, and dropping
# the prose list measurably collapsed classification accuracy.
_EXPENSE_SCHEMA = {
    "type": "object",
    "properties": {
        "amount": {"type": "string", "pattern": r"^[0-9]{1,5}\.[0-9]{2}$"},
        "date": {"type": "string"},
        "description": {"type": "string"},
        "category": {
            "type": "string",
            "enum": list(ocr_validation.EXPENSE_CATEGORIES),
        },
    },
}

_DOC_EXPIRY_PROMPT = (
    "This is a photo or scan of a vehicle document such as a registration card or an insurance "
    "card. Transcribe ONLY what is printed. Do not compute, infer, or guess any value.\n"
    "expires_on: the expiration or renewal date, formatted YYYY-MM-DD. Look for labels such as "
    "'Expiration Date', 'Expires', 'Valid Through', 'Renewal Date' or 'Policy Period End'. If the "
    "document also prints an effective or issue date, do NOT use it. Year rules: a four-digit year "
    "is used as printed; a two-digit year such as 08-25-26 is expanded into the 2000s; if no year "
    "is printed at all, omit this field.\n"
    "description: at most 6 words naming the insurer or the document type, for example "
    "'Auto-Owners no-fault insurance' or 'Michigan vehicle registration'. NEVER include a policy "
    "number, account number, VIN, licence plate, phone number or any other identification number. "
    "NEVER include a person's name.\n"
    "category: exactly one of these three values:\n"
    "  insurance - an insurance certificate, card or policy document\n"
    "  registration - a vehicle registration, title or licence document\n"
    "  other - anything else\n"
    "amount: the fee or premium dollar amount actually charged for THIS document. Most insurance "
    "and registration cards do not print one. Ignore any dollar amount that appears in legal text, "
    "penalty clauses, fine ranges or coverage limits — those are not fees. If no fee or premium is "
    "printed, omit this field entirely. Never estimate it.\n"
    "Return ONLY valid JSON. Omit any field whose value is not printed in the image."
)

# amount is deliberately unconstrained. Under a money pattern the model lifted a
# figure out of the card's printed penalty clause rather than omitting the field.
_DOC_EXPIRY_SCHEMA = {
    "type": "object",
    "properties": {
        "expires_on": {"type": "string"},
        "description": {"type": "string"},
        "category": {
            "type": "string",
            "enum": list(ocr_validation.DOCUMENT_CATEGORIES),
        },
        "amount": {"type": "string"},
    },
}

_VIN_PROMPT = (
    "This photo shows a vehicle identification number (VIN), on a door-jamb sticker, a windshield "
    "plate, a registration card, or an insurance card. A VIN is EXACTLY 17 characters of digits "
    "and capital letters. It never contains the letters I, O or Q. Find the value labelled VIN and "
    "transcribe it character by character, left to right. Count the characters as you go and stop "
    "at exactly 17. Do not skip a character. Do not add one. Common misreads: 0 vs O (a VIN never "
    "contains O), 1 vs I (never I), 5 vs S, 8 vs B, 2 vs Z, 6 vs G. "
    'Return ONLY valid JSON: {"vin": "<the 17 characters>"}, or {} if you cannot read all 17 '
    "clearly."
)

_VIN_SCHEMA = {
    "type": "object",
    "properties": {"vin": {"type": "string", "pattern": "^[A-HJ-NPR-Z0-9]{17}$"}},
}


def _alternatives(exclude_id: str) -> list:
    return [
        {"id": p.get("id"), "label": p.get("label") or p.get("id")}
        for p in get_ocr_settings().get("providers", [])
        if p.get("id") and p.get("id") != exclude_id
    ]


def _provider(provider_id: str = ""):
    cfg = get_ocr_provider(provider_id)
    if not cfg:
        raise HTTPException(status_code=400, detail="No OCR provider is configured.")
    try:
        return cfg, build_provider(cfg)
    except ProviderError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


async def _scan(file: UploadFile, prompt: str, schema: dict, provider_id: str = "") -> dict:
    if not file.content_type or not file.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="File must be an image (JPEG, PNG, WebP, etc.)")

    data = await file.read()
    if len(data) > MAX_IMAGE_BYTES:
        raise HTTPException(status_code=400, detail="Image too large (max 10 MB)")

    cfg, provider = _provider(provider_id)

    try:
        return await run_in_threadpool(provider.scan, data, file.content_type, prompt, schema)
    except ProviderUnreachable as exc:
        raise HTTPException(
            status_code=503,
            detail={
                "detail": f"{exc.label} is unreachable.",
                "provider_unreachable": True,
                "alternatives": _alternatives(cfg.get("id", "")),
            },
        )
    except ProviderError as exc:
        logging.warning("OCR provider error: %s", exc)
        raise HTTPException(status_code=502, detail=str(exc))
    except json.JSONDecodeError:
        raise HTTPException(status_code=422, detail="Could not parse the extracted data. Try a clearer photo.")
    except Exception:
        logging.exception("OCR scan failed")
        raise HTTPException(status_code=500, detail="OCR processing failed. Please try again.")


@router.post("/preload")
async def ocr_preload(provider: str = Form(""), current_user: User = Depends(get_current_user)):
    """Warm the model so the next scan does not pay the cold load.

    Only meaningful for local inference; other provider types are a no-op.
    Failures are deliberately silent — a cold scan is not a user-facing error.
    """
    cfg = get_ocr_provider(provider)
    if not cfg:
        return Response(status_code=204)
    try:
        _, adapter = _provider(provider)
        if not getattr(adapter, "supports_preload", False):
            return Response(status_code=204)
        await run_in_threadpool(adapter.preload)
    except Exception:
        return Response(status_code=204)
    return Response(status_code=202)


@router.post("/fuel")
async def ocr_fuel(
    file: UploadFile = File(...),
    provider: str = Form(""),
    current_user: User = Depends(get_current_user),
):
    raw = await _scan(file, _FUEL_PROMPT, _FUEL_SCHEMA, provider)
    cleaned, warnings = ocr_validation.clean_fuel(raw)
    return {**cleaned, "warnings": warnings}


@router.post("/expense")
async def ocr_expense(
    file: UploadFile = File(...),
    provider: str = Form(""),
    current_user: User = Depends(get_current_user),
):
    raw = await _scan(file, _EXPENSE_PROMPT, _EXPENSE_SCHEMA, provider)
    cleaned, warnings = ocr_validation.clean_expense(raw)
    return {**cleaned, "warnings": warnings}


@router.post("/document-expiry")
async def ocr_document_expiry(
    file: UploadFile = File(...),
    provider: str = Form(""),
    current_user: User = Depends(get_current_user),
):
    raw = await _scan(file, _DOC_EXPIRY_PROMPT, _DOC_EXPIRY_SCHEMA, provider)
    cleaned, warnings = ocr_validation.clean_document(raw)
    return {**cleaned, "warnings": warnings}


_VIN_TRANSLIT = {
    "A": 1, "B": 2, "C": 3, "D": 4, "E": 5, "F": 6, "G": 7, "H": 8,
    "J": 1, "K": 2, "L": 3, "M": 4, "N": 5, "P": 7, "R": 9,
    "S": 2, "T": 3, "U": 4, "V": 5, "W": 6, "X": 7, "Y": 8, "Z": 9,
}
_VIN_WEIGHTS = [8, 7, 6, 5, 4, 3, 2, 10, 0, 9, 8, 7, 6, 5, 4, 3, 2]


def _vin_check_digit_ok(vin: str) -> bool:
    """North American VIN check digit (position 9). Not all import VINs use it."""
    total = 0
    for i, ch in enumerate(vin):
        value = int(ch) if ch.isdigit() else _VIN_TRANSLIT.get(ch)
        if value is None:
            return False
        total += value * _VIN_WEIGHTS[i]
    remainder = total % 11
    expected = "X" if remainder == 10 else str(remainder)
    return vin[8] == expected


@router.post("/vin")
async def ocr_vin(
    file: UploadFile = File(...),
    provider: str = Form(""),
    current_user: User = Depends(get_current_user),
):
    result = await _scan(file, _VIN_PROMPT, _VIN_SCHEMA, provider)
    vin = (result.get("vin") or "").strip().upper().replace(" ", "")
    if not re.fullmatch(r"[A-HJ-NPR-Z0-9]{17}", vin):
        raise HTTPException(status_code=422, detail="Couldn't read a complete VIN — try a closer, sharper photo of the sticker")
    return {"vin": vin, "check_digit_ok": _vin_check_digit_ok(vin)}
