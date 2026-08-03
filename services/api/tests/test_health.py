from fastapi.testclient import TestClient
from forge_api.presentation.http.app import create_app
def test_health_endpoint_reports_service_readiness(monkeypatch) -> None:
    monkeypatch.setenv("FORGE_DATABASE_URL", "postgresql+asyncpg://forge:secret@localhost:5432/forge")
    monkeypatch.setenv("FORGE_REDIS_URL", "redis://localhost:6379/0")
    from forge_api.infrastructure.settings import get_settings
    get_settings.cache_clear()
    response = TestClient(create_app()).get("/health")
    assert response.status_code == 200
    assert response.json() == {"service":"forge-api","environment":"development","status":"ok"}
