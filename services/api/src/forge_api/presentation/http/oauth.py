"""OAuth routes with state/PKCE/nonce support."""
from fastapi import APIRouter, Depends, Query, Request, Response

from forge_api.application.auth.oauth_service import OAuthService
from forge_api.infrastructure.settings import Settings, get_settings
from forge_api.presentation.http.contracts import ok
from forge_api.presentation.http.dependencies import (
    client_device_name,
    client_ip,
    client_user_agent,
    get_oauth_service,
)

router = APIRouter(prefix="/oauth", tags=["oauth"])


@router.get("/{provider}/authorize")
async def authorize(
    provider: str,
    oauth: OAuthService = Depends(get_oauth_service),
):
    result = await oauth.authorize_url(provider)
    return ok(result)


@router.get("/{provider}/callback")
async def callback(
    provider: str,
    request: Request,
    response: Response,
    code: str = Query(min_length=1),
    state: str = Query(min_length=1),
    oauth: OAuthService = Depends(get_oauth_service),
    settings: Settings = Depends(get_settings),
):
    pair = await oauth.callback(
        provider,
        code,
        state,
        ip_address=client_ip(request),
        user_agent=client_user_agent(request),
        device_name=client_device_name(request),
    )
    response.set_cookie(
        "forge_refresh",
        pair.refresh_token,
        httponly=True,
        secure=settings.environment != "development",
        samesite="lax",
        path="/v1/auth",
    )
    return ok({"access_token": pair.access_token, "token_type": pair.token_type})
