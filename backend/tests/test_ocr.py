"""OCR route and validation tests.

The unit tests stub the provider adapter, so they are fast, deterministic and
need no network. A live test against a real provider is opt-in: set
TRACKTION_OCR_LIVE=1 and TRACKTION_OCR_IMAGES=/path/to/photos. No sample images
are committed — the realistic ones are receipts and insurance cards.
"""

import io
import json
import os
from pathlib import Path

import pytest

from app.services import ocr_validation
from app.services.ocr_providers import ProviderUnreachable


PNG_1PX = bytes.fromhex(
    "89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c4"
    "890000000a49444154789c6360000002000100ffff03000006000557bfabd400"
    "00000049454e44ae426082"
)


def _upload(extra=None):
    files = {"file": ("pump.png", io.BytesIO(PNG_1PX), "image/png")}
    return {"files": files, "data": extra or {}}


class StubProvider:
    """Stands in for a real adapter. Returns a canned payload or raises."""

    type = "ollama"
    supports_preload = True

    def __init__(self, payload=None, raises=None):
        self.payload = payload or {}
        self.raises = raises
        self.calls = []

    def scan(self, image, media_type, prompt, schema):
        self.calls.append({"media_type": media_type, "prompt": prompt, "schema": schema})
        if self.raises:
            raise self.raises
        return self.payload

    def preload(self):
        self.calls.append({"preload": True})
        if self.raises:
            raise self.raises

    def test(self):
        return {"success": True}


@pytest.fixture
def stub(monkeypatch):
    """Install a stub adapter and return a setter for its payload."""
    holder = {}

    def install(payload=None, raises=None, supports_preload=True):
        provider = StubProvider(payload, raises)
        provider.supports_preload = supports_preload
        holder["provider"] = provider
        monkeypatch.setattr("app.routes.ocr.build_provider", lambda cfg: provider)
        return provider

    return install


# ── Validation: fuel ──────────────────────────────────────────────────────────

def test_fuel_accepts_a_clean_reading():
    out, warnings = ocr_validation.clean_fuel({"cost": "65.00", "gallons": "13.405"})
    assert out["cost"] == 65.00
    assert out["gallons"] == 13.405
    assert warnings == []


def test_fuel_rejects_decimal_drop():
    # 4603 for 46.03 is the observed 100x failure: it survives the absolute
    # ranges only because gallons is sane, so the derived price must catch it.
    out, warnings = ocr_validation.clean_fuel({"cost": "4603", "gallons": "12.545"})
    assert "cost" not in out
    assert warnings


def test_fuel_rejects_field_swap():
    # Gallons grabbed from the cost line: $1.00/gal is impossible.
    out, warnings = ocr_validation.clean_fuel({"cost": "20.00", "gallons": "20.000"})
    assert "cost" not in out and "gallons" not in out
    assert any("per gallon" in w for w in warnings)


def test_fuel_rejects_out_of_range_total():
    out, warnings = ocr_validation.clean_fuel({"cost": "500.00", "gallons": "20.500"})
    assert "cost" not in out
    assert warnings


def test_fuel_cannot_catch_a_plausible_fabrication():
    """Documents a known limit rather than asserting a fix.

    An observed fabrication of $140.00 for 20.5 gallons works out to $6.83 a
    gallon, which is inside every range here. Narrowing the range to catch it
    would reject real fill-ups. Only the user confirming the form catches this.
    """
    out, warnings = ocr_validation.clean_fuel({"cost": "140.00", "gallons": "20.500"})
    assert out["cost"] == 140.0
    assert warnings == []


def test_fuel_drops_inconsistent_price_but_keeps_the_scan():
    # A display showing no price per gallon has been observed to produce one.
    out, _ = ocr_validation.clean_fuel(
        {"cost": "65.00", "gallons": "13.405", "price_per_gallon": "6.500"}
    )
    assert "price_per_gallon" not in out
    assert out["cost"] == 65.00
    assert out["gallons"] == 13.405


def test_fuel_keeps_a_consistent_price():
    out, _ = ocr_validation.clean_fuel(
        {"cost": "69.00", "gallons": "20.542", "price_per_gallon": "3.359"}
    )
    assert out["price_per_gallon"] == 3.359


# ── Validation: expense ───────────────────────────────────────────────────────

def test_expense_treats_empty_date_as_absent():
    out, warnings = ocr_validation.clean_expense({"amount": "80.01", "date": ""})
    assert "date" not in out
    assert warnings == []


def test_expense_rejects_placeholder_year():
    out, warnings = ocr_validation.clean_expense({"amount": "164.24", "date": "0000-09-12"})
    assert "date" not in out
    assert warnings


def test_expense_defaults_missing_category():
    out, _ = ocr_validation.clean_expense({"amount": "80.01"})
    assert out["category"] == "other"


def test_expense_normalises_unknown_category():
    out, _ = ocr_validation.clean_expense({"amount": "10.00", "category": "parking"})
    assert out["category"] == "other"


def test_expense_rejects_zero_amount():
    out, warnings = ocr_validation.clean_expense({"amount": "0.00"})
    assert "amount" not in out
    assert warnings


# ── Validation: document expiry ───────────────────────────────────────────────

def test_document_accepts_expiry_and_omits_absent_amount():
    out, warnings = ocr_validation.clean_document(
        {"expires_on": "2026-08-25", "category": "insurance",
         "description": "Auto-Owners no-fault insurance"}
    )
    assert out["expires_on"] == "2026-08-25"
    assert out["category"] == "insurance"
    assert "amount" not in out
    assert warnings == []


@pytest.mark.parametrize("junk", ["Omit", "", '{"expires_on": "2026-08-25"}', "0.00"])
def test_document_filters_junk_amounts(junk):
    # An unconstrained field returns obvious garbage, which is the point: it is
    # rejectable here, where a plausible fabrication would not be.
    out, _ = ocr_validation.clean_document({"amount": junk})
    assert "amount" not in out


def test_document_strips_description_containing_a_policy_number():
    out, warnings = ocr_validation.clean_document(
        {"description": "Auto-Owners policy 55-506-042-03"}
    )
    assert "description" not in out
    assert warnings


# ── Routes ────────────────────────────────────────────────────────────────────

def test_fuel_route_returns_cleaned_fields(admin_client, stub):
    stub({"cost": "65.00", "gallons": "13.405"})
    call = _upload()
    r = admin_client.post("/api/ocr/fuel", files=call["files"])
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["cost"] == 65.00
    assert body["gallons"] == 13.405
    assert body["warnings"] == []


def test_fuel_route_surfaces_validation_warnings(admin_client, stub):
    stub({"cost": "20.00", "gallons": "20.000"})
    r = admin_client.post("/api/ocr/fuel", files=_upload()["files"])
    assert r.status_code == 200, r.text
    assert r.json()["warnings"]


def test_route_rejects_non_image(admin_client, stub):
    stub({})
    files = {"file": ("notes.txt", io.BytesIO(b"hello"), "text/plain")}
    r = admin_client.post("/api/ocr/fuel", files=files)
    assert r.status_code == 400


def test_unreachable_provider_returns_503_with_alternatives(admin_client, stub):
    stub(raises=ProviderUnreachable("Local Ollama"))
    r = admin_client.post("/api/ocr/fuel", files=_upload()["files"])
    assert r.status_code == 503, r.text
    detail = r.json()["detail"]
    assert detail["provider_unreachable"] is True
    assert isinstance(detail["alternatives"], list)


def test_unknown_provider_id_is_rejected(admin_client, stub):
    stub({"cost": "65.00", "gallons": "13.405"})
    r = admin_client.post(
        "/api/ocr/fuel", files=_upload()["files"], data={"provider": "no-such-provider"}
    )
    assert r.status_code == 400


def test_provider_override_never_accepts_a_url(admin_client, stub):
    """A caller-supplied base URL must not be honoured: that would make an
    authenticated endpoint an SSRF primitive against the internal network."""
    stub({"cost": "65.00", "gallons": "13.405"})
    r = admin_client.post(
        "/api/ocr/fuel",
        files=_upload()["files"],
        data={"provider": "http://169.254.169.254/latest/meta-data/"},
    )
    assert r.status_code == 400


def test_vin_route_reports_check_digit(admin_client, stub):
    stub({"vin": "LRBFZMR42TD016158"})
    r = admin_client.post("/api/ocr/vin", files=_upload()["files"])
    assert r.status_code == 200, r.text
    assert r.json() == {"vin": "LRBFZMR42TD016158", "check_digit_ok": True}


def test_vin_route_flags_a_failed_check_digit(admin_client, stub):
    stub({"vin": "LRLFZMR42TD016158"})
    r = admin_client.post("/api/ocr/vin", files=_upload()["files"])
    assert r.status_code == 200, r.text
    assert r.json()["check_digit_ok"] is False


def test_vin_route_rejects_a_short_read(admin_client, stub):
    stub({"vin": "LRFZMR42TD016158"})
    r = admin_client.post("/api/ocr/vin", files=_upload()["files"])
    assert r.status_code == 422


def test_preload_is_a_noop_for_providers_without_support(admin_client, stub):
    stub({}, supports_preload=False)
    r = admin_client.post("/api/ocr/preload")
    assert r.status_code == 204


def test_preload_swallows_provider_failure(admin_client, stub):
    stub({}, raises=ProviderUnreachable("Local Ollama"))
    r = admin_client.post("/api/ocr/preload")
    assert r.status_code == 204


def test_preload_warms_a_supported_provider(admin_client, stub):
    provider = stub({})
    r = admin_client.post("/api/ocr/preload")
    assert r.status_code == 202
    assert {"preload": True} in provider.calls


# ── Settings ──────────────────────────────────────────────────────────────────

def test_integrations_never_returns_a_full_key(admin_client):
    r = admin_client.get("/api/settings/integrations")
    assert r.status_code == 200, r.text
    for provider in r.json()["providers"]:
        assert "api_key" not in provider
        if provider["api_key_preview"]:
            assert provider["api_key_preview"].startswith("...")


def test_saving_with_a_blank_key_keeps_the_stored_one(admin_client):
    payload = {
        "active": "anthropic",
        "providers": [
            {"id": "ollama-local", "type": "ollama", "label": "Local Ollama",
             "model": "qwen3.5:4b", "base_url": "http://10.10.10.10:11434"},
            {"id": "anthropic", "type": "anthropic", "label": "Anthropic",
             "model": "claude-sonnet-5", "api_key": "sk-ant-secret-1234"},
        ],
    }
    assert admin_client.post("/api/settings/integrations", json=payload).status_code == 200

    payload["providers"][1]["api_key"] = ""  # what a masked round-trip submits
    assert admin_client.post("/api/settings/integrations", json=payload).status_code == 200

    r = admin_client.get("/api/settings/integrations")
    anthropic = next(p for p in r.json()["providers"] if p["id"] == "anthropic")
    assert anthropic["api_key_set"] is True
    assert anthropic["api_key_preview"] == "...1234"


def test_saving_rejects_an_active_id_not_in_the_list(admin_client):
    payload = {
        "active": "ghost",
        "providers": [
            {"id": "ollama-local", "type": "ollama", "label": "Local Ollama",
             "model": "qwen3.5:4b", "base_url": "http://10.10.10.10:11434"},
        ],
    }
    assert admin_client.post("/api/settings/integrations", json=payload).status_code == 400


def test_saving_rejects_ollama_without_a_base_url(admin_client):
    payload = {
        "active": "ollama-local",
        "providers": [
            {"id": "ollama-local", "type": "ollama", "label": "Local Ollama",
             "model": "qwen3.5:4b"},
        ],
    }
    assert admin_client.post("/api/settings/integrations", json=payload).status_code == 422


def test_set_active_provider_rejects_unknown_id(admin_client):
    r = admin_client.post("/api/settings/integrations/active", json={"id": "ghost"})
    assert r.status_code == 404


# ── Expense schema ────────────────────────────────────────────────────────────

def test_expense_create_lowercases_category():
    from app.schemas import ExpenseCreate
    from datetime import date as _date

    e = ExpenseCreate(category="  Insurance ", amount=10.0, date=_date.today(), description="x")
    assert e.category == "insurance"

def test_fuel_keeps_a_plausible_odometer():
    out, _ = ocr_validation.clean_fuel(
        {"cost": "65.00", "gallons": "13.405", "mileage": "84213"}
    )
    assert out["mileage"] == 84213


def test_fuel_drops_an_implausible_odometer():
    out, _ = ocr_validation.clean_fuel({"cost": "65.00", "gallons": "13.405", "mileage": "0"})
    assert "mileage" not in out


def test_expense_create_keeps_a_custom_category():
    """Users define their own expense categories in the UI; the schema must not
    rewrite them, even though the OCR model is limited to the standard five."""
    from app.schemas import ExpenseCreate
    from datetime import date as _date

    e = ExpenseCreate(category="Detailing", amount=10.0, date=_date.today(), description="x")
    assert e.category == "detailing"



# ── Live, opt-in ──────────────────────────────────────────────────────────────

LIVE = os.environ.get("TRACKTION_OCR_LIVE") == "1"
IMAGE_DIR = os.environ.get("TRACKTION_OCR_IMAGES", "")


@pytest.mark.skipif(not LIVE, reason="set TRACKTION_OCR_LIVE=1 to run against a real provider")
def test_live_fuel_scan(admin_client):
    image = Path(IMAGE_DIR) / "pump.jpg"
    if not image.exists():
        pytest.skip(f"no sample image at {image}")
    with image.open("rb") as fh:
        r = admin_client.post("/api/ocr/fuel", files={"file": ("pump.jpg", fh, "image/jpeg")})
    assert r.status_code == 200, r.text
    body = r.json()
    print("\nlive fuel scan ->", json.dumps(body, indent=2))
    assert "cost" in body or body["warnings"]
