def test_collection_route_served_without_trailing_slash(app_client):
    """Cloudflare strips the trailing slash, so the origin must answer without it."""
    response = app_client.get("/api/vehicles", follow_redirects=False)

    assert response.status_code == 200
    assert [vehicle["make"] for vehicle in response.json()] == ["Honda"]


def test_slashed_collection_route_still_works(app_client):
    response = app_client.get("/api/vehicles/", follow_redirects=False)

    assert response.status_code == 200


def test_unknown_path_still_returns_not_found(app_client):
    response = app_client.get("/api/zzz", follow_redirects=False)

    assert response.status_code == 404


def test_nested_route_is_untouched(app_client):
    """Only exact collection paths are rewritten, never deeper resource paths."""
    response = app_client.get("/api/vehicles/999", follow_redirects=False)

    assert response.status_code == 404
