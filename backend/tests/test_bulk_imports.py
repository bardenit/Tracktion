from uuid import uuid4

from app.models import Expense, FuelEntry, MaintenanceEntry


def test_fuel_bulk_import_is_retry_safe_and_preserves_flags(app_client, db_session, seeded_objects):
    _, _, vehicle = seeded_objects
    payload = {
        "operation_id": str(uuid4()),
        "entries": [
            {"date": "2026-01-01", "mileage": 100, "gallons": 5, "cost": 15, "missed_fillup": False, "partial_fillup": False},
            {"date": "2026-01-02", "mileage": 120, "gallons": 4, "cost": 12, "missed_fillup": False, "partial_fillup": True},
            {"date": "2026-01-03", "mileage": 140, "gallons": 6, "cost": 18, "missed_fillup": False, "partial_fillup": False},
        ],
    }
    first = app_client.post(f"/api/fuel/{vehicle.id}/entries/bulk", json=payload)
    retry = app_client.post(f"/api/fuel/{vehicle.id}/entries/bulk", json=payload)
    assert first.status_code == retry.status_code == 200
    assert first.json()["imported_count"] == 3
    entries = db_session.query(FuelEntry).order_by(FuelEntry.date).all()
    assert len(entries) == 3
    assert entries[1].partial_fillup is True
    assert entries[2].mpg == 4


def test_invalid_batch_persists_no_prefix(app_client, db_session, seeded_objects):
    _, _, vehicle = seeded_objects
    cases = [
        ("fuel", FuelEntry, [{"date": "2026-01-01", "mileage": 1, "gallons": 1, "cost": 1}, {"date": "bad", "mileage": 2, "gallons": 1, "cost": 1}]),
        ("maintenance", MaintenanceEntry, [{"date": "2026-01-01", "mileage": 1, "type": "Oil", "cost": 1}, {"date": "bad", "mileage": 2, "type": "Oil", "cost": 1}]),
        ("expenses", Expense, [{"date": "2026-01-01", "category": "other", "description": "ok", "amount": 1}, {"date": "bad", "category": "other", "description": "bad", "amount": 1}]),
    ]
    for resource, model, entries in cases:
        response = app_client.post(f"/api/{resource}/{vehicle.id}/entries/bulk", json={"operation_id": str(uuid4()), "entries": entries})
        assert response.status_code == 422
        assert db_session.query(model).count() == 0
