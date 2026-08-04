"""Dependency injection for the presentation layer.

Application services are assembled through ``Depends()`` chains rooted here.
Database session factory and cache client are created once at application
startup (lifespan) and shared via ``app.state``; every request builds fresh
repositories and services bound to the shared session factory.
"""
from collections.abc import AsyncGenerator

from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from forge_api.application.auth.auth_service import AuthService
from forge_api.application.auth.oauth_service import OAuthService
from forge_api.application.auth.session_service import SessionService
from forge_api.application.workspaces.workspace_service import WorkspaceService
from forge_api.domain.errors import AuthenticationError, ServiceUnavailableError
from forge_api.domain.security import AccessClaims
from forge_api.infrastructure.audit import AuditLogger
from forge_api.infrastructure.database import create_session_factory
from forge_api.infrastructure.oauth import OAuthStateManager
from forge_api.infrastructure.oauth_identity_repository import (
    SqlOAuthIdentityRepository,
)
from forge_api.infrastructure.security import (
    Argon2PasswordHasher,
    JwtTokenProvider,
    SecureRefreshTokenGenerator,
)
from forge_api.infrastructure.session_repository import SqlSessionRepository
from forge_api.infrastructure.settings import Settings, get_settings
from forge_api.infrastructure.user_repository import SqlUserRepository
from forge_api.infrastructure.workspace_repository import SqlWorkspaceRepository

_bearer = HTTPBearer()


# ─── Singletons / settings ─────────────────────────────────────────


def _token_provider(settings: Settings = Depends(get_settings)) -> JwtTokenProvider:
    return JwtTokenProvider(settings)


def _password_hasher() -> Argon2PasswordHasher:
    return Argon2PasswordHasher()


def _refresh_generator() -> SecureRefreshTokenGenerator:
    return SecureRefreshTokenGenerator()


# ─── App-shared session factory / cache ────────────────────────────


def _session_factory(request: Request) -> async_sessionmaker:
    factory = getattr(request.app.state, "session_factory", None)
    if factory is None:
        factory = create_session_factory(get_settings())
    return factory


async def get_session(request: Request) -> AsyncGenerator[AsyncSession, None]:
    async with _session_factory(request)() as session:
        yield session
        await session.commit()


def get_cache(request: Request) -> Redis:
    cache = getattr(request.app.state, "cache", None)
    if cache is None:
        raise ServiceUnavailableError("Cache is unavailable")
    return cache


# ─── Audit ──────────────────────────────────────────────────────────


def get_audit(db: AsyncSession = Depends(get_session)) -> AuditLogger:
    return AuditLogger(db)


# ─── Authentication ─────────────────────────────────────────────────


def current_claims(
    token: HTTPAuthorizationCredentials = Depends(_bearer),
    tokens: JwtTokenProvider = Depends(_token_provider),
) -> AccessClaims:
    """Decode the bearer token and return the access claims."""
    try:
        return tokens.decode_access_token(token.credentials)
    except Exception as exc:
        raise AuthenticationError("Invalid access token") from exc


async def validated_claims(
    claims: AccessClaims = Depends(current_claims),
    db: AsyncSession = Depends(get_session),
) -> AccessClaims:
    """Decode the bearer token AND verify the session is still active."""
    from datetime import UTC, datetime

    from forge_api.infrastructure.session_repository import SqlSessionRepository

    repo = SqlSessionRepository(db)
    session = await repo.get(claims.session_id, user_id=claims.user_id)
    if not session or session.revoked_at is not None:
        raise AuthenticationError("Session has been revoked")
    if session.expires_at < datetime.now(UTC):
        raise AuthenticationError("Session has expired")
    return claims


def current_user_id(claims: AccessClaims = Depends(current_claims)) -> str:
    """Convenience: return user_id as a string for backward compat."""
    return str(claims.user_id)


# ─── Application services ──────────────────────────────────────────


def get_auth_service(
    db: AsyncSession = Depends(get_session),
    settings: Settings = Depends(get_settings),
    tokens: JwtTokenProvider = Depends(_token_provider),
    passwords: Argon2PasswordHasher = Depends(_password_hasher),
    refresh: SecureRefreshTokenGenerator = Depends(_refresh_generator),
    audit: AuditLogger = Depends(get_audit),
) -> AuthService:
    return AuthService(
        users=SqlUserRepository(db),
        sessions=SqlSessionRepository(db),
        tokens=tokens,
        passwords=passwords,
        refresh=refresh,
        audit=audit,
        refresh_ttl_days=settings.refresh_token_ttl_days,
    )


def get_session_service(
    db: AsyncSession = Depends(get_session),
    settings: Settings = Depends(get_settings),
    tokens: JwtTokenProvider = Depends(_token_provider),
    refresh: SecureRefreshTokenGenerator = Depends(_refresh_generator),
    audit: AuditLogger = Depends(get_audit),
) -> SessionService:
    return SessionService(
        sessions=SqlSessionRepository(db),
        tokens=tokens,
        refresh=refresh,
        audit=audit,
        refresh_ttl_days=settings.refresh_token_ttl_days,
        last_active_throttle_seconds=settings.session_last_active_throttle_seconds,
    )


def get_oauth_service(
    db: AsyncSession = Depends(get_session),
    cache: Redis = Depends(get_cache),
    settings: Settings = Depends(get_settings),
    tokens: JwtTokenProvider = Depends(_token_provider),
    refresh: SecureRefreshTokenGenerator = Depends(_refresh_generator),
    audit: AuditLogger = Depends(get_audit),
) -> OAuthService:
    return OAuthService(
        users=SqlUserRepository(db),
        oauth_identities=SqlOAuthIdentityRepository(db),
        sessions=SqlSessionRepository(db),
        tokens=tokens,
        refresh=refresh,
        audit=audit,
        state_manager=OAuthStateManager(cache, settings),
        settings=settings,
    )


def get_workspace_service(
    db: AsyncSession = Depends(get_session),
    audit: AuditLogger = Depends(get_audit),
) -> WorkspaceService:
    return WorkspaceService(
        workspaces=SqlWorkspaceRepository(db),
        audit=audit,
    )


# ─── Request context helpers ────────────────────────────────────────


def client_ip(request: Request) -> str | None:
    return request.client.host if request.client else None


def client_user_agent(request: Request) -> str | None:
    return request.headers.get("user-agent")


def client_device_name(request: Request) -> str | None:
    return request.headers.get("sec-ch-ua-platform")
