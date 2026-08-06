from app.models import Vehicle
from app.services.vehicle_mileage import observe_vehicle_mileage


def test_absolute_observations_are_monotonic(db_session, seeded_objects):
    _, _, vehicle = seeded_objects
    vehicle.current_mileage = 10_000
    db_session.commit()

    observe_vehicle_mileage(db_session, vehicle.id, 9_000)
    observe_vehicle_mileage(db_session, vehicle.id, 12_000)
    observe_vehicle_mileage(db_session, vehicle.id, 11_000)
    db_session.commit()

    db_session.refresh(vehicle)
    assert vehicle.current_mileage == 12_000


def test_trip_mutations_do_not_change_odometer(app_client, db_session, seeded_objects):
    _, _, vehicle = seeded_objects
    vehicle.current_mileage = 20_000
    db_session.commit()
    created = app_client.post(f"/api/trips/{vehicle.id}/entries", json={
        "date": "2026-01-01", "miles": 100, "destination": "Work",
    })
    assert created.status_code == 200
    trip_id = created.json()["id"]
    assert app_client.put(f"/api/trips/{vehicle.id}/entries/{trip_id}", json={"miles": 10}).status_code == 200
    assert app_client.delete(f"/api/trips/{vehicle.id}/entries/{trip_id}").status_code == 200
    db_session.refresh(vehicle)
    assert vehicle.current_mileage == 20_000

