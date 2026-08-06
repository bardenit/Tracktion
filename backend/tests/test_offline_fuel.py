from datetime import date

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def offline_client(db_session, seeded_objects):
    from app.auth import get_current_user
    from app.database import get_db
    from app.main import app

    owner, _, _ = seeded_objects

    def override_db():
        yield db_session

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_current_user] = lambda: owner
    app.state.database_ready = True
    client = TestClient(app)
    yield client
    client.close()
    app.dependency_overrides.clear()


def _payload(operation_id: str, **overrides):
    payload = {
        "operation_id": operation_id,
        "date": date.today().isoformat(),
        "mileage": 1000,
        "gallons": 10,
        "cost": 35,
        "location": "Pump",
        "notes": "offline",
        "octane": 87,
        "missed_fillup": True,
        "partial_fillup": True,
    }
    payload.update(overrides)
    return payload


def test_offline_replay_returns_original_entry(offline_client, seeded_objects, db_session):
    from app.models import FuelEntry, FuelIdempotencyOperation

    _, _, vehicle = seeded_objects
    operation_id = "20ab3bc9-d1df-49f8-91af-929823da8cc1"

    first = offline_client.post(f"/api/fuel/{vehicle.id}/entries", json=_payload(operation_id))
    replay = offline_client.post(f"/api/fuel/{vehicle.id}/entries", json=_payload(operation_id))

    assert first.status_code == 200
    assert replay.status_code == 200
    assert replay.json()["id"] == first.json()["id"]
    assert db_session.query(FuelEntry).count() == 1
    operation = db_session.query(FuelIdempotencyOperation).one()
    assert operation.fuel_entry_id == first.json()["id"]
    assert operation.user_id == seeded_objects[0].id
    assert replay.json()["partial_fillup"] is True
    assert replay.json()["missed_fillup"] is True


def test_operation_reuse_with_changed_binding_is_generic_conflict(offline_client, seeded_objects):
    _, _, vehicle = seeded_objects
    operation_id = "1b50bad4-03dd-4c8a-801f-d1ec1384738e"
    assert offline_client.post(f"/api/fuel/{vehicle.id}/entries", json=_payload(operation_id)).status_code == 200

    response = offline_client.post(
        f"/api/fuel/{vehicle.id}/entries",
        json=_payload(operation_id, gallons=11),
    )

    assert response.status_code == 409
    assert response.json() == {"detail": "Idempotency operation conflict"}


def test_same_operation_id_is_independent_per_user(offline_client, seeded_objects, db_session):
    from app.auth import get_current_user
    from app.main import app
    from app.models import User, Vehicle

    owner, _, first_vehicle = seeded_objects
    second_owner = User(email="second@example.test", password_hash="hash")
    db_session.add(second_owner)
    db_session.flush()
    second_vehicle = Vehicle(user_id=second_owner.id, make="Ford", model="Focus", year=2021)
    db_session.add(second_vehicle)
    db_session.commit()
    operation_id = "05db5549-aebc-428c-870b-0ec43f2575ad"

    app.dependency_overrides[get_current_user] = lambda: owner
    first = offline_client.post(f"/api/fuel/{first_vehicle.id}/entries", json=_payload(operation_id))
    app.dependency_overrides[get_current_user] = lambda: second_owner
    second = offline_client.post(f"/api/fuel/{second_vehicle.id}/entries", json=_payload(operation_id))

    assert first.status_code == second.status_code == 200
    assert first.json()["id"] != second.json()["id"]
