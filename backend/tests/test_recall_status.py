from datetime import datetime, timedelta

import pytest

from app.services import recalls as recalls_service


@pytest.fixture
def nhtsa_stub(monkeypatch, db_session):
    """Stubs the NHTSA call and points background refreshes at the test session."""
    calls = []

    async def fake_get_recalls(make, model, year):
        calls.append((make, model, year))
        return [{
            "campaign_number": "FRESH-1",
            "component": "Brakes",
            "summary": None,
            "consequence": None,
            "remedy": None,
            "report_date": None,
        }]

    monkeypatch.setattr(recalls_service, "get_recalls", fake_get_recalls)
    monkeypatch.setattr(recalls_service, "SessionLocal", lambda: db_session)
    recalls_service._refreshing.clear()
    return calls


def test_recall_status_serves_cache_and_refreshes_in_background(app_client, db_session, seeded_objects, nhtsa_stub):
    from app.models import Vehicle

    _, _, vehicle = seeded_objects
    vehicle.recalls_cache = {
        "campaigns": [{"campaign_number": "STALE-1", "component": "Airbag"}],
        "checked_at": (datetime.utcnow() - timedelta(days=3)).isoformat(),
    }
    vehicle.recalls_seen = []
    db_session.commit()

    response = app_client.get(f"/api/vehicles/{vehicle.id}/recall-status")
    assert response.status_code == 200
    body = response.json()

    # Served from the stale cache rather than waiting on NHTSA.
    assert body["available"] is True
    assert [r["campaign_number"] for r in body["new_recalls"]] == ["STALE-1"]

    # The refresh still happened, just out of band.
    assert nhtsa_stub == [("Honda", "Civic", 2020)]
    refreshed = db_session.get(Vehicle, vehicle.id)
    assert [c["campaign_number"] for c in refreshed.recalls_cache["campaigns"]] == ["FRESH-1"]


def test_fresh_cache_does_not_touch_nhtsa(app_client, db_session, seeded_objects, nhtsa_stub):
    _, _, vehicle = seeded_objects
    vehicle.recalls_cache = {
        "campaigns": [{"campaign_number": "SEEN-1", "component": "Airbag"}],
        "checked_at": datetime.utcnow().isoformat(),
    }
    vehicle.recalls_seen = ["SEEN-1"]
    db_session.commit()

    body = app_client.get(f"/api/vehicles/{vehicle.id}/recall-status").json()
    assert body == {"available": True, "new_count": 0, "new_recalls": []}
    assert nhtsa_stub == []


def test_empty_cache_returns_immediately_and_primes_cache(app_client, db_session, seeded_objects, nhtsa_stub):
    from app.models import Vehicle

    _, _, vehicle = seeded_objects
    vehicle.recalls_cache = None
    vehicle.recalls_seen = []
    db_session.commit()

    body = app_client.get(f"/api/vehicles/{vehicle.id}/recall-status").json()
    assert body == {"available": False, "new_count": 0, "new_recalls": []}

    assert nhtsa_stub == [("Honda", "Civic", 2020)]
    primed = db_session.get(Vehicle, vehicle.id)
    assert [c["campaign_number"] for c in primed.recalls_cache["campaigns"]] == ["FRESH-1"]
