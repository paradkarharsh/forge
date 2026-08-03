"""Session lifecycle application service.

Handles refresh-token rotation with reuse detection, session listing,
individual/bulk revocation, logout, expiration cleanup, and
last_active throttling.
"""
from datetime import UTC, datetime, timedelta
from uuid import UUID

from forge_api.application.auth.dtos import TokenPair
from forge_api.application.auth.session_dtos import SessionView
from forge_api.domain.audit import AuditEventType
from forge_api.domain.errors import AuthenticationError, NotFoundError
from forge_api.domain.repositories import SessionRepository
from forge_api.domain.security import (
    AccessClaims,
    RefreshTokenGenerator,
    TokenProvider,
)
from forge_api.infrastructure.audit import AuditLogger


class SessionService:
    """Manages the full session lifecycle including rotation and reuse detection."""

    def __init__(
        self,
        *,
        sessions: SessionRepository,
        tokens: TokenProvider,
        refresh: RefreshTokenGenerator,
        audit: AuditLogger,
        refresh_ttl_days: int,
        last_active_throttle_seconds: int,
    ) -> None:
        self._sessions = sessions
        self._tokens = tokens
        self._refresh = refresh
        self._audit = audit
        self._refresh_ttl = timedelta(days=refresh_ttl_days)
        self._throttle = timedelta(seconds=last_active_throttle_seconds)

    async def refresh(
        self,
        raw_token: str,
        *,
        ip_address: str | None,
        user_agent: str | None,
        device_name: str | None,
    ) -> TokenPair:
        """Rotate a refresh token and issue a new token pair.

        If the incoming token has already been consumed (reuse detection),
        the entire token family is revoked.
        """
        digest = self._refresh.digest(raw_token)
        session = await self._sessions.find_by_refresh_hash(digest)

        if not session:
            raise AuthenticationError("Refresh token rejected")

        now = datetime.now(UTC)

        if session.revoked_at or session.expires_at < now:
            # Reuse detected — revoke the whole family.
            revoked_count = await self._sessions.revoke_family(
                session.family_id, now
            )
            self._audit.log(
                AuditEventType.REFRESH_REUSE_DETECTED,
                user_id=session.user_id,
                session_id=session.id,
                ip_address=ip_address,
                user_agent=user_agent,
                reason="refresh token reuse detected",
                payload={"family_revoked_count": revoked_count},
            )
            raise AuthenticationError("Refresh token rejected")

        # Mark the old session as rotated.
        await self._sessions.rotate(session.id, now)

        # Issue replacement.
        raw_replacement = self._refresh.generate()
        new_session = await self._sessions.create(
            user_id=session.user_id,
            family_id=session.family_id,
            refresh_hash=self._refresh.digest(raw_replacement),
            expires_at=now + self._refresh_ttl,
            device_name=device_name,
            ip_address=ip_address,
            user_agent=user_agent,
        )

        access_token = self._tokens.create_access_token(
            AccessClaims(user_id=session.user_id, session_id=new_session.id)
        )

        self._audit.log(
            AuditEventType.REFRESH_ROTATED,
            user_id=session.user_id,
            session_id=new_session.id,
            ip_address=ip_address,
            user_agent=user_agent,
        )

        return TokenPair(
            access_token=access_token, refresh_token=raw_replacement
        )

    async def list_sessions(self, user_id: UUID) -> list[SessionView]:
        """Return all active sessions for a user."""
        records = await self._sessions.list_active(user_id)
        return [
            SessionView(
                id=r.id,
                device_name=r.device_name,
                ip_address=r.ip_address,
                user_agent=r.user_agent,
                last_active_at=r.last_active_at,
                expires_at=r.expires_at,
            )
            for r in records
        ]

    async def revoke(
        self,
        session_id: UUID,
        user_id: UUID,
        *,
        ip_address: str | None,
        user_agent: str | None,
    ) -> None:
        """Revoke a single session by id."""
        now = datetime.now(UTC)
        revoked = await self._sessions.revoke(session_id, user_id, now)
        if not revoked:
            raise NotFoundError("Session not found")
        self._audit.log(
            AuditEventType.SESSION_REVOKED,
            user_id=user_id,
            session_id=session_id,
            ip_address=ip_address,
            user_agent=user_agent,
        )

    async def revoke_all(
        self,
        user_id: UUID,
        *,
        ip_address: str | None,
        user_agent: str | None,
    ) -> int:
        """Revoke all active sessions for a user."""
        now = datetime.now(UTC)
        count = await self._sessions.revoke_all(user_id, now)
        self._audit.log(
            AuditEventType.LOGOUT_ALL,
            user_id=user_id,
            ip_address=ip_address,
            user_agent=user_agent,
            payload={"revoked_count": count},
        )
        return count

    async def logout(
        self,
        session_id: UUID,
        user_id: UUID,
        *,
        ip_address: str | None,
        user_agent: str | None,
    ) -> None:
        """Log out the current session."""
        now = datetime.now(UTC)
        await self._sessions.revoke(session_id, user_id, now)
        self._audit.log(
            AuditEventType.LOGOUT,
            user_id=user_id,
            session_id=session_id,
            ip_address=ip_address,
            user_agent=user_agent,
        )

    async def touch(self, session_id: UUID) -> None:
        """Update last_active timestamp, throttled to avoid write storms."""
        now = datetime.now(UTC)
        stale_before = now - self._throttle
        await self._sessions.touch(session_id, now, stale_before=stale_before)

    async def cleanup_expired(self) -> int:
        """Delete sessions past their expiry and audit the cleanup."""
        now = datetime.now(UTC)
        count = await self._sessions.cleanup_expired(now)
        if count > 0:
            self._audit.log(
                AuditEventType.SESSION_CLEANED,
                payload={"cleaned_count": count},
            )
        return count
