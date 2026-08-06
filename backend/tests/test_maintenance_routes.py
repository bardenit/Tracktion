from uuid import uuid4

from app.models import MaintenanceEntry


def test_completion_is_idempotent_and_update_is_config_only(app_client, db_session, seeded_objects):
    _, _, vehicle = seeded_objects
    created = app_client.post(f"/api/maintenance/{vehicle.id}/reminders", json={
        "service_type": "Oil", "interval_miles": 5_000,
    })
    assert created.status_code == 200
    reminder_id = created.json()["id"]

    rejected = app_client.put(f"/api/maintenance/{vehicle.id}/reminders/{reminder_id}", json={
        "last_performed_mileage": 99_999,
    })
    assert rejected.status_code == 200
    assert rejected.json()["last_performed_mileage"] is None

    operation_id = str(uuid4())
    payload = {"operation_id": operation_id, "date": "2026-08-01", "mileage": 12_000, "cost": 40}
    first = app_client.post(f"/api/maintenance/{vehicle.id}/reminders/{reminder_id}/complete", json=payload)
    second = app_client.post(f"/api/maintenance/{vehicle.id}/reminders/{reminder_id}/complete", json=payload)
    assert first.status_code == second.status_code == 200
    assert first.json()["id"] == second.json()["id"]
    assert db_session.query(MaintenanceEntry).filter_by(vehicle_id=vehicle.id, type="Oil").count() == 1

    reminder = app_client.get(f"/api/maintenance/{vehicle.id}/reminders").json()[0]
    assert reminder["last_performed_mileage"] == 12_000
    assert reminder["next_due_mileage"] == 17_000


def test_entry_type_change_and_delete_recompute_both_reminders(app_client, seeded_objects):
    _, _, vehicle = seeded_objects
    for service_type in ("Oil", "Tires"):
        assert app_client.post(f"/api/maintenance/{vehicle.id}/reminders", json={
            "service_type": service_type, "interval_miles": 1_000,
        }).status_code == 200
    entry = app_client.post(f"/api/maintenance/{vehicle.id}/entries", json={
        "date": "2026-01-01", "mileage": 10_000, "type": "Oil", "cost": 1,
    }).json()
    assert app_client.put(f"/api/maintenance/{vehicle.id}/entries/{entry['id']}", json={
        "date": "2026-01-02", "mileage": 10_100, "type": "Tires", "cost": 1,
    }).status_code == 200
    reminders = {r["service_type"]: r for r in app_client.get(f"/api/maintenance/{vehicle.id}/reminders").json()}
    assert reminders["Oil"]["last_performed_mileage"] is None
    assert reminders["Tires"]["last_performed_mileage"] == 10_100
    assert app_client.delete(f"/api/maintenance/{vehicle.id}/entries/{entry['id']}").status_code == 200
    reminders = {r["service_type"]: r for r in app_client.get(f"/api/maintenance/{vehicle.id}/reminders").json()}
    assert reminders["Tires"]["last_performed_mileage"] is None
