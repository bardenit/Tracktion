from app.models import User, Vehicle, VehicleCollaborator


def test_require_admin_rejects_non_admin():
    from fastapi import HTTPException
    from app.deps import require_admin

    try:
        require_admin(User(id=1, email="user@example.test", password_hash="x", is_admin=False))
    except HTTPException as exc:
        assert exc.status_code == 403
    else:
        raise AssertionError("non-admin was allowed")


def test_remove_collaborator_is_scoped_to_vehicle(app_client, db_session, seeded_objects):
    owner, _, vehicle_a = seeded_objects
    vehicle_b = Vehicle(user_id=owner.id, make="Ford", model="Focus", year=2021)
    other = User(email="other@example.test", password_hash="hash")
    db_session.add_all([vehicle_b, other])
    db_session.flush()
    foreign = VehicleCollaborator(vehicle_id=vehicle_b.id, user_id=other.id, role="viewer")
    db_session.add(foreign)
    db_session.commit()

    response = app_client.delete(f"/api/vehicles/{vehicle_a.id}/collaborators/{foreign.id}")

    assert response.status_code == 404
    assert db_session.get(VehicleCollaborator, foreign.id) is not None

