from fastapi import APIRouter, Depends

from forge_api.application.health import GetServiceHealth
from forge_api.domain.health import ServiceHealth
from forge_api.infrastructure.settings import Settings, get_settings

router = APIRouter(tags=["system"])


def get_health_use_case(settings: Settings = Depends(get_settings)) -> GetServiceHealth:
    return GetServiceHealth(settings)


@router.get("/health", response_model=ServiceHealth, summary="Report service readiness")
def read_health(
    use_case: GetServiceHealth = Depends(get_health_use_case),
) -> ServiceHealth:
    return use_case.execute()
