"""Authentication application service.

Orchestrates registration, login, and token issuance. All persistence
access runs through repository ports; security operations use protocol
abstractions so infrastructure details never leak into business logic.
"""
from datetime import UTC, datetime, timedelta
from uuid import UUID

from forge_api.application.auth.dtos import TokenPair
from forge_api.domain.audit import AuditEventType
from forge_api.domain.errors import AuthenticationError, ConflictError
from forge_api.domain.repositories import SessionRepository, UserRepository
from forge_api.domain.security import (
    AccessClaims,
    PasswordHasher,
    RefreshTokenGenerator,
    TokenProvider,
)
from forge_api.infrastructure.audit import AuditLogger


class AuthService:
    """Handles registration, credential login, and token pair issuance."""

    def __init__(
        self,
        *,
        users: UserRepository,
        sessions: SessionRepository,
        tokens: TokenProvider,
        passwords: PasswordHasher,
        refresh: RefreshTokenGenerator,
        audit: AuditLogger,
        refresh_ttl_days: int,
    ) -> None:
        self._users = users
        self._sessions = sessions
        self._tokens = tokens
        self._passwords = passwords
        self._refresh = refresh
        self._audit = audit
        self._refresh_ttl = timedelta(days=refresh_ttl_days)

    async def register(
        self,
        *,
        email: str,
        password: str,
        ip_address: str | None,
        user_agent: str | None,
        device_name: str | None,
    ) -> TokenPair:
        """Register a new user and return an initial token pair."""
        existing = await self._users.find_by_email(email)
        if existing:
            raise ConflictError("Email already registered", code="email_taken")

        hashed = self._passwords.hash(password)
        user = await self._users.create(email=email, password_hash=hashed)

        return await self._issue(
            user_id=user.id,
            ip_address=ip_address,
            user_agent=user_agent,
            device_name=device_name,
            audit_event=AuditEventType.REGISTER,
        )

    async def login(
        self,
        *,
        email: str,
        password: str,
        ip_address: str | None,
        user_agent: str | None,
        device_name: str | None,
    ) -> TokenPair:
        """Authenticate with credentials and return a token pair."""
        user = await self._users.find_by_email(email)

        if (
            not user
            or not user.password_hash
            or not self._passwords.verify(password, user.password_hash)
        ):
            raise AuthenticationError("Invalid credentials")

        return await self._issue(
            user_id=user.id,
            ip_address=ip_address,
            user_agent=user_agent,
            device_name=device_name,
            audit_event=AuditEventType.LOGIN,
        )

    async def _issue(
        self,
        *,
        user_id: UUID,
        ip_address: str | None,
        user_agent: str | None,
        device_name: str | None,
        audit_event: AuditEventType,
    ) -> TokenPair:
        """Create a session and return a signed token pair."""
        raw_refresh = self._refresh.generate()
        now = datetime.now(UTC)

        session = await self._sessions.create(
            user_id=user_id,
            family_id=user_id,  # first session in a new family
            refresh_hash=self._refresh.digest(raw_refresh),
            expires_at=now + self._refresh_ttl,
            device_name=device_name,
            ip_address=ip_address,
            user_agent=user_agent,
        )

        access_token = self._tokens.create_access_token(
            AccessClaims(user_id=user_id, session_id=session.id)
        )

        self._audit.log(
            audit_event,
            user_id=user_id,
            session_id=session.id,
            ip_address=ip_address,
            user_agent=user_agent,
        )

        return TokenPair(access_token=access_token, refresh_token=raw_refresh)
