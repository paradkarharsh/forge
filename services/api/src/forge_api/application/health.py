from forge_api.domain.health import ServiceHealth
from forge_api.infrastructure.settings import Settings
class GetServiceHealth:
    def __init__(self, settings: Settings) -> None: self._settings = settings
    def execute(self) -> ServiceHealth: return ServiceHealth(service="forge-api", environment=self._settings.environment, status="ok")
