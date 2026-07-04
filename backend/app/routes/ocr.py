import base64
import json
import logging
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from app.auth import get_current_user
from app.models import User
from app.data_config import get_config

router = APIRouter()

_FUEL_PROMPT = (
    "Extract fuel purchase details from this gas pump display or fuel receipt photo. "
    "Pump displays use seven-segment digits that are easy to misread or transpose, so read each "
    "number carefully digit by digit. Then cross-check your reading with arithmetic: "
    "price per gallon x gallons must equal the total cost within a few cents. If the numbers "
    "don't reconcile, re-read the digits and correct the value that makes the arithmetic consistent. "
    "Sanity ranges: gallons 1-45, price per gallon $2-$7, total cost $5-$250. "
    "Return a JSON object with these fields (only include ones you can read with high confidence "
    "AND that pass the arithmetic check — omit a field rather than guessing): "
    "date (YYYY-MM-DD string), gallons (number), cost (total dollar amount as number), "
    "price_per_gallon (number if shown), location (gas station name string), "
    "mileage (odometer reading as number if visible). "
    "Return ONLY valid JSON with no markdown or explanation."
)

_EXPENSE_PROMPT = (
    "Extract expense/purchase details from this receipt image. "
    "Return a JSON object with these fields (only include ones you can find with confidence): "
    "date (YYYY-MM-DD string), amount (total dollar amount as number), "
    "description (concise string of what was purchased), "
    "category (one of exactly: insurance, registration, repair, fuel, other). "
    "Return ONLY valid JSON with no markdown or explanation."
)


def _get_client():
    key = get_config().get("integrations", {}).get("anthropic_api_key", "")
    if not key:
        raise HTTPException(
            status_code=400,
            detail="Anthropic API key not configured. Add it in Settings → Integrations.",
        )
    import anthropic
    return anthropic.Anthropic(api_key=key)


async def _scan(file: UploadFile, prompt: str, model: str = "claude-haiku-4-5-20251001") -> dict:
    if not file.content_type or not file.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="File must be an image (JPEG, PNG, WebP, etc.)")

    data = await file.read()
    if len(data) > 10 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="Image too large (max 10 MB)")

    client = _get_client()
    b64 = base64.standard_b64encode(data).decode()

    try:
        msg = client.messages.create(
            model=model,
            max_tokens=512,
            messages=[{
                "role": "user",
                "content": [
                    {"type": "image", "source": {"type": "base64", "media_type": file.content_type, "data": b64}},
                    {"type": "text", "text": prompt},
                ],
            }],
        )
        raw = msg.content[0].text.strip()
        if raw.startswith("```"):
            raw = raw.split("\n", 1)[1].rsplit("```", 1)[0].strip()
        return json.loads(raw)
    except json.JSONDecodeError:
        raise HTTPException(status_code=422, detail="Could not parse receipt data. Try a clearer photo.")
    except Exception:
        logging.exception("OCR scan failed")
        raise HTTPException(status_code=500, detail="OCR processing failed. Please try again.")


@router.post("/fuel")
async def ocr_fuel(file: UploadFile = File(...), current_user: User = Depends(get_current_user)):
    # Sonnet 5 has high-resolution vision — much better at seven-segment pump digits
    return await _scan(file, _FUEL_PROMPT, model="claude-sonnet-5")


@router.post("/expense")
async def ocr_expense(file: UploadFile = File(...), current_user: User = Depends(get_current_user)):
    return await _scan(file, _EXPENSE_PROMPT)


_DOC_EXPIRY_PROMPT = (
    "This is a photo or scan of a vehicle document such as a registration card or insurance card. "
    "Extract these fields (only include ones you can read with confidence): "
    "expires_on (the expiration/renewal date as a YYYY-MM-DD string — look for labels like "
    "'expires', 'expiration date', 'valid through', 'renewal date', 'policy period end'), "
    "description (a short label like 'Vehicle registration' or the insurer name and policy number), "
    "category (exactly one of: insurance, registration, other), "
    "amount (the fee or premium dollar amount as a number, if shown). "
    "Return ONLY valid JSON with no markdown or explanation."
)


@router.post("/document-expiry")
async def ocr_document_expiry(file: UploadFile = File(...), current_user: User = Depends(get_current_user)):
    return await _scan(file, _DOC_EXPIRY_PROMPT)
