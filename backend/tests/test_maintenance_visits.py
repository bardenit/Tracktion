"""Visits, and the service-invoice OCR rules measured against a real receipt.

The OCR fixtures below are verbatim readings taken from qwen3.5:4b on a
two-page Todd Wenzel repair order (2026-10-27), including the two ways the
model got the grand total wrong. They are kept exact so a prompt or threshold
change that reintroduces either failure shows up here.
"""

from uuid import uuid4

import pytest

from app.models import MaintenanceEntry
from app.services import ocr_validation


# ── Readings taken from the real two-page invoice ────────────────────────────

# Page 1's totals box is blank — the invoice is a pre-invoice — and the model
# filled the field with operation #1's sub total on 5 of 5 runs.
PAGE_ONE = {
    "shop": "Todd Wenzel",
    "odometer": "13710",
    "date": "2026-10-27",
    "total": "83.84",
    "services": [
        {"name": "DEX6: DEX6 OIL CHANGE SERVICE", "amount": "83.84"},
        {"name": "A MAI: MAINTENANCE", "amount": ".00"},
        {"name": "MPVI: PERFORM MULTI POINT INSPECTION", "amount": ".00"},
        {"name": "ENV: ENVIRONMENTAL SERVICE", "amount": "7.86"},
    ],
}

# Page 2 does print a total, but the column is clipped off the edge of the
# photo, and the model returned the PARTS row instead on 3 of 3 runs.
PAGE_TWO = {
    "shop": "TODD WENZEL",
    "odometer": "13710",
    "date": "2026-10-27",
    "total": "148.30",
    "services": [
        {"name": "FUEL SYSTEM CLEANER ADDITIVE FOR GM", "amount": "48.90"},
        {"name": "ROTATE TIRES", "amount": "29.95"},
        {"name": "CABIN: REPLACE IN CABIN AIR FILTER", "amount": "79.95"},
    ],
}


def test_a_grand_total_repeating_a_line_item_is_rejected():
    cleaned, warnings = ocr_validation.clean_maintenance(PAGE_ONE)
    assert "total" not in cleaned
    assert any("repeated a line item" in w for w in warnings)


def test_a_grand_total_smaller_than_its_own_lines_is_rejected():
    cleaned, warnings = ocr_validation.clean_maintenance(PAGE_TWO)
    assert "total" not in cleaned
    assert any("smaller than the lines" in w for w in warnings)
    assert cleaned["lines_total"] == pytest.approx(158.80)


def test_operation_codes_are_stripped_and_a_bare_dot_zero_is_kept():
    cleaned, _ = ocr_validation.clean_maintenance(PAGE_ONE)
    names = [s["name"] for s in cleaned["services"]]
    assert names[0] == "DEX6 OIL CHANGE SERVICE"
    assert names[2] == "PERFORM MULTI POINT INSPECTION"
    # A zero sub total prints as ".00" and must survive as a real zero, not be
    # dropped — a no-charge inspection is still service history worth keeping.
    assert cleaned["services"][1]["amount"] == 0.0
    assert cleaned["lines_total"] == pytest.approx(91.70)


def test_a_repair_order_number_is_not_accepted_as_an_odometer():
    # Observed at 1024px: the R/O number sits above the mileage in the header
    # and was returned in its place.
    cleaned, warnings = ocr_validation.clean_maintenance(
        {**PAGE_ONE, "odometer": "39174936"}
    )
    assert "odometer" not in cleaned
    assert any("implausible odometer" in w for w in warnings)


def test_merging_pages_keeps_every_operation_and_declines_a_bad_total():
    merged, warnings = ocr_validation.merge_maintenance([
        ocr_validation.clean_maintenance(PAGE_ONE),
        ocr_validation.clean_maintenance(PAGE_TWO),
    ])
    assert len(merged["services"]) == 7
    assert merged["odometer"] == 13710
    assert merged["date"] == "2026-10-27"
    assert merged["lines_total"] == pytest.approx(250.50)
    # Neither page produced a usable total, so the app falls back to the sum.
    assert "total" not in merged
    assert warnings


def test_merging_accepts_a_total_that_covers_every_line():
    good_page_two = {**PAGE_TWO, "total": "238.05"}
    merged, warnings = ocr_validation.merge_maintenance([
        ocr_validation.clean_maintenance(PAGE_ONE),
        ocr_validation.clean_maintenance(good_page_two),
    ])
    assert merged["total"] == pytest.approx(238.05)
    # A discount legitimately puts the total below the lines it covers.
    assert any("lower than the services" in w for w in warnings)


# ── The visits endpoint ──────────────────────────────────────────────────────

def _visit_payload(**overrides):
    payload = {
        "operation_id": str(uuid4()),
        "date": "2026-10-27",
        "mileage": 13_710,
        "service_provider": "Todd Wenzel GMC",
        "services": [
            {"type": "Oil Change", "cost": 83.84},
            {"type": "Tire Rotation", "cost": 29.95},
            {"type": "Cabin Air Filter", "cost": 79.95},
        ],
    }
    payload.update(overrides)
    return payload


def test_a_visit_creates_one_entry_per_service_sharing_a_visit_id(app_client, db_session, seeded_objects):
    _, _, vehicle = seeded_objects
    response = app_client.post(f"/api/maintenance/{vehicle.id}/visits", json=_visit_payload())
    assert response.status_code == 200
    body = response.json()

    assert len(body["entries"]) == 3
    assert body["total_cost"] == pytest.approx(193.74)
    assert {e["visit_id"] for e in body["entries"]} == {body["visit_id"]}
    # Each service keeps its own cost, which is what per-service history needs.
    assert {e["type"]: e["cost"] for e in body["entries"]}["Tire Rotation"] == pytest.approx(29.95)


def test_a_visit_rolls_every_matching_reminder_forward(app_client, seeded_objects):
    _, _, vehicle = seeded_objects
    for service_type, interval in (("Oil Change", 5_000), ("Cabin Air Filter", 15_000)):
        created = app_client.post(f"/api/maintenance/{vehicle.id}/reminders", json={
            "service_type": service_type, "interval_miles": interval,
        })
        assert created.status_code == 200

    assert app_client.post(
        f"/api/maintenance/{vehicle.id}/visits", json=_visit_payload()
    ).status_code == 200

    due = {r["service_type"]: r["next_due_mileage"]
           for r in app_client.get(f"/api/maintenance/{vehicle.id}/reminders").json()}
    assert due["Oil Change"] == 18_710
    assert due["Cabin Air Filter"] == 28_710


def test_reposting_a_visit_does_not_double_log_it(app_client, db_session, seeded_objects):
    _, _, vehicle = seeded_objects
    payload = _visit_payload()
    first = app_client.post(f"/api/maintenance/{vehicle.id}/visits", json=payload)
    second = app_client.post(f"/api/maintenance/{vehicle.id}/visits", json=payload)

    assert first.status_code == second.status_code == 200
    assert first.json()["visit_id"] == second.json()["visit_id"]
    assert [e["id"] for e in first.json()["entries"]] == [e["id"] for e in second.json()["entries"]]
    assert db_session.query(MaintenanceEntry).filter_by(vehicle_id=vehicle.id).count() == 3


def test_a_visit_rejects_the_same_service_listed_twice(app_client, seeded_objects):
    _, _, vehicle = seeded_objects
    response = app_client.post(f"/api/maintenance/{vehicle.id}/visits", json=_visit_payload(
        services=[{"type": "Oil Change", "cost": 50}, {"type": "oil change", "cost": 20}],
    ))
    # Two entries of one type in a single visit would make the reminder's
    # "most recent matching entry" ambiguous, and is always a UI mistake.
    assert response.status_code == 422


# ── Totals, measured against the real Todd Wenzel invoice ────────────────────
# Page 1 is a "Pre-Invoice" whose totals box is empty; page 2 prints TOTAL DUE
# 238.61. The seven operations sum to 250.50 and the invoice bills 238.61 after
# 8.11 of sales tax and a -20.00 QL discount.

_PAGE_ONE_LINES = [
    {"name": "DEX6 OIL CHANGE SERVICE", "amount": "83.84"},
    {"name": "MAINTENANCE", "amount": ".00"},
    {"name": "PERFORM MULTI POINT INSPECTION", "amount": ".00"},
    {"name": "ENVIRONMENTAL SERVICE", "amount": "7.86"},
]
_PAGE_TWO_LINES = [
    {"name": "FUEL SYSTEM CLEANER ADDITIVE FOR GM", "amount": "48.90"},
    {"name": "ROTATE TIRES", "amount": "29.95"},
    {"name": "REPLACE IN CABIN AIR FILTER", "amount": "79.95"},
]


def test_blank_totals_box_phantom_is_rejected():
    """Page 1's box is blank and the model invents a total anyway. Observed
    94.95, 95.24 and 93.48; each clears page 1's own 91.70 of operations."""
    for phantom in ("94.95", "95.24", "93.48"):
        page_one = ocr_validation.clean_maintenance(
            {"services": _PAGE_ONE_LINES, "total": phantom}
        )
        page_two = ocr_validation.clean_maintenance(
            {"services": _PAGE_TWO_LINES, "total": "238.61"}
        )
        merged, warnings = ocr_validation.merge_maintenance([page_one, page_two])
        assert merged["lines_total"] == 250.50
        assert merged["total"] == 238.61, f"phantom {phantom} won over the real total"
        assert any("does not fit" in w for w in warnings)


def test_phantom_alone_is_dropped_rather_than_shown():
    """When the real total is lost, a phantom must not stand in for it."""
    page_one = ocr_validation.clean_maintenance(
        {"services": _PAGE_ONE_LINES, "total": "93.48"}
    )
    page_two = ocr_validation.clean_maintenance({"services": _PAGE_TWO_LINES})
    merged, warnings = ocr_validation.merge_maintenance([page_one, page_two])
    assert merged["lines_total"] == 250.50
    assert "total" not in merged
    assert any("does not fit" in w for w in warnings)


def test_a_real_discounted_total_still_survives():
    """238.61 against 250.50 of lines is the true invoice; the discount must not
    make it look implausible."""
    page_one = ocr_validation.clean_maintenance({"services": _PAGE_ONE_LINES})
    page_two = ocr_validation.clean_maintenance(
        {"services": _PAGE_TWO_LINES, "total": "238.61"}
    )
    merged, warnings = ocr_validation.merge_maintenance([page_one, page_two])
    assert merged["total"] == 238.61
    assert any("lower than the services" in w for w in warnings)


def test_a_misread_sub_total_is_flagged_by_the_printed_total():
    """Taking the cabin filter's part price (59.95) instead of its sub total
    (79.95) yields 230.50 — below the printed total, which is the signal."""
    misread = [dict(_PAGE_TWO_LINES[0]), dict(_PAGE_TWO_LINES[1]),
               {"name": "REPLACE IN CABIN AIR FILTER", "amount": "59.95"}]
    page_one = ocr_validation.clean_maintenance({"services": _PAGE_ONE_LINES})
    page_two = ocr_validation.clean_maintenance({"services": misread, "total": "238.61"})
    merged, warnings = ocr_validation.merge_maintenance([page_one, page_two])
    assert merged["lines_total"] == 230.50
    assert merged["total"] == 238.61
    assert any("higher than the services" in w for w in warnings)


def test_a_page_that_reads_nothing_is_reported():
    """Observed once in five runs: page 2 came back with no operations and the
    invoice silently looked like page 1 alone."""
    page_one = ocr_validation.clean_maintenance({"services": _PAGE_ONE_LINES})
    page_two = ocr_validation.clean_maintenance({"services": []})
    merged, warnings = ocr_validation.merge_maintenance([page_one, page_two])
    assert merged["lines_total"] == 91.70
    assert any("produced no operations" in w for w in warnings)


# ── Visit totals: tax, fees and discounts ────────────────────────────────────

def test_a_visit_carries_a_negative_adjustment_line(app_client, seeded_objects):
    """238.61 paid against 250.50 of operations: 8.11 tax less a 20.00 discount.
    The services keep the costs the receipt prints."""
    _, _, vehicle = seeded_objects
    response = app_client.post(f"/api/maintenance/{vehicle.id}/visits", json=_visit_payload(
        services=[
            {"type": "Oil Change", "cost": 83.84},
            {"type": "Tire Rotation", "cost": 29.95},
            {"type": "Cabin Air Filter", "cost": 79.95},
            {"type": "Tax, fees & discounts", "cost": -11.89},
        ],
    ))
    assert response.status_code == 200
    body = response.json()
    assert body["total_cost"] == pytest.approx(181.85)
    costs = {e["type"]: e["cost"] for e in body["entries"]}
    assert costs["Oil Change"] == pytest.approx(83.84)
    assert costs["Tax, fees & discounts"] == pytest.approx(-11.89)


def test_an_adjustment_joins_a_visit_logged_earlier(app_client, seeded_objects):
    _, _, vehicle = seeded_objects
    visit = app_client.post(f"/api/maintenance/{vehicle.id}/visits", json=_visit_payload()).json()

    added = app_client.post(f"/api/maintenance/{vehicle.id}/entries", json={
        "date": "2026-10-27", "mileage": 13_710, "type": "Tax, fees & discounts",
        "cost": -11.89, "visit_id": visit["visit_id"],
    })
    assert added.status_code == 200
    assert added.json()["visit_id"] == visit["visit_id"]

    entries = app_client.get(f"/api/maintenance/{vehicle.id}/entries").json()
    in_visit = [e for e in entries if e["visit_id"] == visit["visit_id"]]
    assert len(in_visit) == 4
    assert sum(e["cost"] for e in in_visit) == pytest.approx(181.85)


def test_an_entry_cannot_join_a_visit_that_is_not_this_vehicles(app_client, seeded_objects):
    """Without this check the per-vehicle access gate would be bypassed: the
    caller writes to a vehicle it can reach, but grafts the row onto another
    vehicle's visit."""
    _, _, vehicle = seeded_objects
    response = app_client.post(f"/api/maintenance/{vehicle.id}/entries", json={
        "date": "2026-10-27", "mileage": 13_710, "type": "Tax, fees & discounts",
        "cost": -11.89, "visit_id": str(uuid4()),
    })
    assert response.status_code == 404


# ── Discount lines ───────────────────────────────────────────────────────────
# `QL discount  -20.00` is a labelled line beside the operations and read 6/6.
# Sales tax is deliberately not extracted: it lives in the totals box, whose
# value column is offset from its labels, and it read 1/6.

def test_a_printed_discount_line_is_kept():
    cleaned, _ = ocr_validation.clean_maintenance({
        "services": _PAGE_TWO_LINES,
        "adjustments": [{"label": "QL discount", "amount": "-20.00"}],
    })
    assert cleaned["discounts"] == [{"label": "QL discount", "amount": -20.0}]


def test_the_totals_box_cannot_masquerade_as_a_discount():
    """One run returned the whole box. Only a discount-labelled negative line
    survives: TOTAL DUE restated as `DISCOUNTS 238.61` is positive, and
    `SPECIAL ORDER DEPOSIT -20.00` is the same discount under another name."""
    cleaned, _ = ocr_validation.clean_maintenance({
        "services": _PAGE_TWO_LINES,
        "adjustments": [
            {"label": "QL discount", "amount": "-20.00"},
            {"label": "SPECIAL ORDER DEPOSIT", "amount": "-20.00"},
            {"label": "DISCOUNTS", "amount": "238.61"},
            {"label": "SALES TAX OR TAX I.D.", "amount": ".00"},
            {"label": "LABOR", "amount": "75.95"},
        ],
    })
    assert cleaned["discounts"] == [{"label": "QL discount", "amount": -20.0}]


def test_a_discount_bigger_than_the_page_is_rejected():
    cleaned, _ = ocr_validation.clean_maintenance({
        "services": _PAGE_TWO_LINES,
        "adjustments": [{"label": "QL discount", "amount": "-900.00"}],
    })
    assert "discounts" not in cleaned


def test_one_discount_restated_across_pages_is_kept_once():
    page_one = ocr_validation.clean_maintenance({
        "services": _PAGE_ONE_LINES,
        "adjustments": [{"label": "QL discount", "amount": "-20.00"}],
    })
    page_two = ocr_validation.clean_maintenance({
        "services": _PAGE_TWO_LINES,
        "adjustments": [{"label": "QL discount", "amount": "-20.00"}],
    })
    merged, _ = ocr_validation.merge_maintenance([page_one, page_two])
    assert merged["discounts"] == [{"label": "QL discount", "amount": -20.0}]


def test_the_boxs_own_discounts_row_is_not_a_discount_line():
    """Observed `DISCOUNTS -3.34`, a figure printed nowhere on the invoice. The
    box summarises; only a descriptively labelled line is a real discount."""
    cleaned, _ = ocr_validation.clean_maintenance({
        "services": _PAGE_TWO_LINES,
        "adjustments": [
            {"label": "DISCOUNTS", "amount": "-3.34"},
            {"label": "QL discount", "amount": "-20.00"},
        ],
    })
    assert cleaned["discounts"] == [{"label": "QL discount", "amount": -20.0}]


# ── Receipt filenames ────────────────────────────────────────────────────────

def _entry(db, vehicle_id, visit_id, **kw):
    from datetime import date

    entry = MaintenanceEntry(
        vehicle_id=vehicle_id, visit_id=visit_id,
        date=kw.get("date", date(2026, 10, 28)), mileage=kw.get("mileage", 13710.0),
        type=kw.get("type", "Oil Change"), cost=kw.get("cost", 83.84),
    )
    db.add(entry)
    db.flush()
    return entry


def test_receipt_is_named_for_the_service_date_and_odometer(db_session, seeded_objects):
    """`receipt-c087ab7c.pdf` says nothing in a list of documents."""
    from app.routes.documents import _receipt_filename

    _, _, vehicle = seeded_objects
    visit = str(uuid4())
    entry = _entry(db_session, vehicle.id, visit)
    assert _receipt_filename(db_session, vehicle.id, visit, entry.id) == \
        "oil-change-2026-10-28-13710mi.pdf"


def test_receipt_name_falls_back_to_the_visits_first_service(db_session, seeded_objects):
    """The anchor entry can be deleted; the visit's own first service still names it."""
    from app.routes.documents import _receipt_filename

    _, _, vehicle = seeded_objects
    visit = str(uuid4())
    _entry(db_session, vehicle.id, visit)
    _entry(db_session, vehicle.id, visit, type="Tire Rotation")
    assert _receipt_filename(db_session, vehicle.id, visit, None) == \
        "oil-change-2026-10-28-13710mi.pdf"


def test_receipt_name_tolerates_a_punctuated_service_type(db_session, seeded_objects):
    """OCR hands back operation names verbatim, trailing full stop and all."""
    from app.routes.documents import _receipt_filename

    _, _, vehicle = seeded_objects
    visit = str(uuid4())
    entry = _entry(db_session, vehicle.id, visit,
                   type="FUEL SYSTEM CLEANER ADDITIVE FOR GM ENHANCED MAINTENANCE PROGRAM.")
    name = _receipt_filename(db_session, vehicle.id, visit, entry.id)
    assert name == "fuel-system-cleaner-additive-for-gm-2026-10-28-13710mi.pdf"
    assert "--" not in name


def test_receipt_name_falls_back_when_the_visit_has_no_entries(db_session, seeded_objects):
    from app.routes.documents import _receipt_filename

    _, _, vehicle = seeded_objects
    visit = "c087ab7c-326c-4a3c-a2dd-b10efe48be7a"
    assert _receipt_filename(db_session, vehicle.id, visit, None) == "receipt-c087ab7c.pdf"
