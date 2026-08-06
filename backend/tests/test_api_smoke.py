def test_route_fixture_isolated_and_seeded(app_client):
    response = app_client.get("/api/vehicles/")

    assert response.status_code == 200
    assert [vehicle["make"] for vehicle in response.json()] == ["Honda"]


def test_health_checks_database_readiness(app_client):
    response = app_client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "healthy", "database": "ready"}

