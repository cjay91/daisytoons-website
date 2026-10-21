def test_unknown_route_uses_the_error_shape(client):
    response = client.get("/no-such-page")

    assert response.status_code == 404
    assert response.json() == {"error": {"code": "not_found", "message": "Not Found"}}
