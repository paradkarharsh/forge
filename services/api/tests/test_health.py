"""Health endpoint tests."""


def test_health_returns_ok_with_service_info(test_client) -> None:
    response = test_client.get("/health", headers={"Host": "localhost"})
    assert response.status_code == 200
    body = response.json()
    assert body == {
        "service": "forge-api",
        "environment": "development",
        "status": "ok",
    }
