"""Authentication routes.

Every response uses the global ``ok()`` / exception-handler contracts.
No SQLAlchemy imports — all persistence runs through application services.
"""
from fastapi import APIRouter, Cookie, Depends, Request, Response
from pydantic import BaseModel, EmailStr, Field

from forge_api.application.auth.auth_service import AuthService
from forge_api.application.auth.session_service import SessionService
from forge_api.infrastructure.settings import Settings, get_settings
from forge_api.presentation.http.contracts import ok
from forge_api.presentation.http.dependencies import (
    client_device_name,
    client_ip,
    client_user_agent,
    current_claims,
    get_auth_service,
    get_session_service,
)

router = APIRouter(prefix="/auth", tags=["auth"])


class Credentials(BaseModel):
    email: EmailStr
    password: str = Field(min_length=12, max_length=128)


def _set_refresh_cookie(
    response: Response, token: str, *, settings: Settings
) -> None:
    response.set_cookie(
        "forge_refresh",
        token,
        httponly=True,
        secure=settings.environment != "development",
        samesite="lax",
        path="/v1/auth",
    )


def _clear_refresh_cookie(response: Response) -> None:
    response.delete_cookie("forge_refresh", path="/v1/auth")


@router.post("/register", status_code=201)
async def register(
    body: Credentials,
    request: Request,
    response: Response,
    auth: AuthService = Depends(get_auth_service),
    settings: Settings = Depends(get_settings),
):
    pair = await auth.register(
        email=body.email,
        password=body.password,
        ip_address=client_ip(request),
        user_agent=client_user_agent(request),
        device_name=client_device_name(request),
    )
    _set_refresh_cookie(response, pair.refresh_token, settings=settings)
    return ok({"access_token": pair.access_token, "token_type": pair.token_type})


@router.post("/login")
async def login(
    body: Credentials,
    request: Request,
    response: Response,
    auth: AuthService = Depends(get_auth_service),
    settings: Settings = Depends(get_settings),
):
    pair = await auth.login(
        email=body.email,
        password=body.password,
        ip_address=client_ip(request),
        user_agent=client_user_agent(request),
        device_name=client_device_name(request),
    )
    _set_refresh_cookie(response, pair.refresh_token, settings=settings)
    return ok({"access_token": pair.access_token, "token_type": pair.token_type})


@router.post("/refresh")
async def refresh(
    request: Request,
    response: Response,
    forge_refresh: str | None = Cookie(default=None),
    session_svc: SessionService = Depends(get_session_service),
    settings: Settings = Depends(get_settings),
):
    from forge_api.domain.errors import AuthenticationError

    if not forge_refresh:
        raise AuthenticationError("Missing refresh token")

    pair = await session_svc.refresh(
        forge_refresh,
        ip_address=client_ip(request),
        user_agent=client_user_agent(request),
        device_name=client_device_name(request),
    )
    _set_refresh_cookie(response, pair.refresh_token, settings=settings)
    return ok({"access_token": pair.access_token, "token_type": pair.token_type})


@router.post("/logout", status_code=204)
async def logout(
    request: Request,
    response: Response,
    claims=Depends(current_claims),
    session_svc: SessionService = Depends(get_session_service),
):
    await session_svc.logout(
        claims.session_id,
        claims.user_id,
        ip_address=client_ip(request),
        user_agent=client_user_agent(request),
    )
    _clear_refresh_cookie(response)


@router.post("/logout-all", status_code=204)
async def logout_all(
    request: Request,
    response: Response,
    claims=Depends(current_claims),
    session_svc: SessionService = Depends(get_session_service),
):
    await session_svc.revoke_all(
        claims.user_id,
        ip_address=client_ip(request),
        user_agent=client_user_agent(request),
    )
    _clear_refresh_cookie(response)
