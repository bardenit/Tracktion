def test_stats_use_weighted_valid_intervals(app_client, seeded_objects):
    _, _, vehicle = seeded_objects
    for payload in (
        {"date": "2026-01-01", "mileage": 1_000, "gallons": 5, "cost": 15},
        {"date": "2026-01-02", "mileage": 1_100, "gallons": 5, "cost": 15},
        {"date": "2026-01-03", "mileage": 1_400, "gallons": 10, "cost": 30},
    ):
        response = app_client.post(f"/api/fuel/{vehicle.id}/entries", json=payload)
        assert response.status_code == 200, response.text

    stats = app_client.get(f"/api/fuel/{vehicle.id}/stats")
    assert stats.status_code == 200
    assert stats.json()["average_mpg"] == 400 / 15
