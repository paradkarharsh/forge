"""SessionService unit tests — rotation, reuse detection, logout, cleanup."""
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

from forge_api.application.auth.session_service import SessionService
from forge_api.domain.errors import AuthenticationError, NotFoundError


@pytest.fixture
def session_service(fake_sessions, fake_tokens, fake_refresh, fake_audit):
    return SessionService(
        sessions=fake_sessions,
        tokens=fake_tokens,
        refresh=fake_refresh,
        audit=fake_audit,
        refresh_ttl_days=30,
        last_active_throttle_seconds=60,
    )


@pytest.fixture
def user_id():
    return uuid4()


class TestRefreshRotation:
    @pytest.mark.asyncio
    async def test_refresh_returns_new_token_pair(
        self, session_service, fake_sessions, fake_refresh, user_id
    ) -> None:
        raw = fake_refresh.generate()
        await fake_sessions.create(
            user_id=user_id,
            family_id=user_id,
            refresh_hash=fake_refresh.digest(raw),
            expires_at=datetime.now(UTC) + timedelta(days=30),
            device_name=None,
            ip_address=None,
            user_agent=None,
        )
        pair = await session_service.refresh(
            raw, ip_address=None, user_agent=None, device_name=None
        )
        assert pair.access_token
        assert pair.refresh_token
        assert pair.refresh_token != raw

    @pytest.mark.asyncio
    async def test_old_token_is_revoked_after_rotation(
        self, session_service, fake_sessions, fake_refresh, user_id
    ) -> None:
        raw = fake_refresh.generate()
        session = await fake_sessions.create(
            user_id=user_id,
            family_id=user_id,
            refresh_hash=fake_refresh.digest(raw),
            expires_at=datetime.now(UTC) + timedelta(days=30),
            device_name=None,
            ip_address=None,
            user_agent=None,
        )
        await session_service.refresh(
            raw, ip_address=None, user_agent=None, device_name=None
        )
        old = await fake_sessions.get(session.id)
        assert old is not None
        assert old.revoked_at is not None
        assert old.replaced_at is not None


class TestReuseDetection:
    @pytest.mark.asyncio
    async def test_reusing_rotated_token_revokes_entire_family(
        self, session_service, fake_sessions, fake_refresh, user_id
    ) -> None:
        raw = fake_refresh.generate()
        await fake_sessions.create(
            user_id=user_id,
            family_id=user_id,
            refresh_hash=fake_refresh.digest(raw),
            expires_at=datetime.now(UTC) + timedelta(days=30),
            device_name=None,
            ip_address=None,
            user_agent=None,
        )
        # First use — valid rotation
        await session_service.refresh(
            raw, ip_address=None, user_agent=None, device_name=None
        )
        # Second use of the SAME token — reuse
        with pytest.raises(AuthenticationError, match="rejected"):
            await session_service.refresh(
                raw, ip_address=None, user_agent=None, device_name=None
            )
        # The replacement should also be revoked
        active = await fake_sessions.list_active(user_id)
        assert len(active) == 0

    @pytest.mark.asyncio
    async def test_expired_token_is_rejected(
        self, session_service, fake_sessions, fake_refresh, user_id
    ) -> None:
        raw = fake_refresh.generate()
        await fake_sessions.create(
            user_id=user_id,
            family_id=user_id,
            refresh_hash=fake_refresh.digest(raw),
            expires_at=datetime.now(UTC) - timedelta(hours=1),
            device_name=None,
            ip_address=None,
            user_agent=None,
        )
        with pytest.raises(AuthenticationError, match="rejected"):
            await session_service.refresh(
                raw, ip_address=None, user_agent=None, device_name=None
            )

    @pytest.mark.asyncio
    async def test_unknown_token_is_rejected(self, session_service) -> None:
        with pytest.raises(AuthenticationError, match="rejected"):
            await session_service.refresh(
                "totally-unknown-token",
                ip_address=None,
                user_agent=None,
                device_name=None,
            )

    @pytest.mark.asyncio
    async def test_reuse_audits_event(
        self, session_service, fake_sessions, fake_refresh, fake_audit, user_id
    ) -> None:
        raw = fake_refresh.generate()
        await fake_sessions.create(
            user_id=user_id,
            family_id=user_id,
            refresh_hash=fake_refresh.digest(raw),
            expires_at=datetime.now(UTC) + timedelta(days=30),
            device_name=None,
            ip_address=None,
            user_agent=None,
        )
        await session_service.refresh(
            raw, ip_address=None, user_agent=None, device_name=None
        )
        with pytest.raises(AuthenticationError):
            await session_service.refresh(
                raw, ip_address=None, user_agent=None, device_name=None
            )
        assert any(
            e.get("event")
            and hasattr(e["event"], "value")
            and e["event"].value == "auth.refresh_reuse_detected"
            for e in fake_audit.events
        )


class TestLogout:
    @pytest.mark.asyncio
    async def test_logout_revokes_session(
        self, session_service, fake_sessions, fake_refresh, user_id
    ) -> None:
        raw = fake_refresh.generate()
        session = await fake_sessions.create(
            user_id=user_id,
            family_id=user_id,
            refresh_hash=fake_refresh.digest(raw),
            expires_at=datetime.now(UTC) + timedelta(days=30),
            device_name=None,
            ip_address=None,
            user_agent=None,
        )
        await session_service.logout(
            session.id, user_id, ip_address=None, user_agent=None
        )
        active = await fake_sessions.list_active(user_id)
        assert len(active) == 0


class TestRevokeAll:
    @pytest.mark.asyncio
    async def test_revoke_all_clears_all_sessions(
        self, session_service, fake_sessions, fake_refresh, user_id
    ) -> None:
        for _ in range(3):
            raw = fake_refresh.generate()
            await fake_sessions.create(
                user_id=user_id,
                family_id=user_id,
                refresh_hash=fake_refresh.digest(raw),
                expires_at=datetime.now(UTC) + timedelta(days=30),
                device_name=None,
                ip_address=None,
                user_agent=None,
            )
        count = await session_service.revoke_all(
            user_id, ip_address=None, user_agent=None
        )
        assert count == 3
        active = await fake_sessions.list_active(user_id)
        assert len(active) == 0


class TestRevokeSession:
    @pytest.mark.asyncio
    async def test_revoke_single_session(
        self, session_service, fake_sessions, fake_refresh, user_id
    ) -> None:
        raw = fake_refresh.generate()
        session = await fake_sessions.create(
            user_id=user_id,
            family_id=user_id,
            refresh_hash=fake_refresh.digest(raw),
            expires_at=datetime.now(UTC) + timedelta(days=30),
            device_name=None,
            ip_address=None,
            user_agent=None,
        )
        await session_service.revoke(
            session.id, user_id, ip_address=None, user_agent=None
        )
        s = await fake_sessions.get(session.id)
        assert s is not None
        assert s.revoked_at is not None

    @pytest.mark.asyncio
    async def test_revoke_nonexistent_session_raises(
        self, session_service, user_id
    ) -> None:
        with pytest.raises(NotFoundError, match="not found"):
            await session_service.revoke(
                uuid4(), user_id, ip_address=None, user_agent=None
            )


class TestCleanup:
    @pytest.mark.asyncio
    async def test_cleanup_removes_expired_sessions(
        self, session_service, fake_sessions, fake_refresh, user_id
    ) -> None:
        raw = fake_refresh.generate()
        await fake_sessions.create(
            user_id=user_id,
            family_id=user_id,
            refresh_hash=fake_refresh.digest(raw),
            expires_at=datetime.now(UTC) - timedelta(days=1),
            device_name=None,
            ip_address=None,
            user_agent=None,
        )
        count = await session_service.cleanup_expired()
        assert count == 1

    @pytest.mark.asyncio
    async def test_cleanup_audits_when_sessions_removed(
        self, session_service, fake_sessions, fake_refresh, fake_audit, user_id
    ) -> None:
        raw = fake_refresh.generate()
        await fake_sessions.create(
            user_id=user_id,
            family_id=user_id,
            refresh_hash=fake_refresh.digest(raw),
            expires_at=datetime.now(UTC) - timedelta(days=1),
            device_name=None,
            ip_address=None,
            user_agent=None,
        )
        await session_service.cleanup_expired()
        assert any(
            e.get("event")
            and hasattr(e["event"], "value")
            and e["event"].value == "auth.session_cleaned"
            for e in fake_audit.events
        )

    @pytest.mark.asyncio
    async def test_cleanup_does_not_audit_when_nothing_removed(
        self, session_service, fake_audit
    ) -> None:
        count = await session_service.cleanup_expired()
        assert count == 0
        assert not any(
            e.get("event")
            and hasattr(e["event"], "value")
            and e["event"].value == "auth.session_cleaned"
            for e in fake_audit.events
        )


class TestListSessions:
    @pytest.mark.asyncio
    async def test_list_returns_active_sessions(
        self, session_service, fake_sessions, fake_refresh, user_id
    ) -> None:
        for _ in range(2):
            raw = fake_refresh.generate()
            await fake_sessions.create(
                user_id=user_id,
                family_id=user_id,
                refresh_hash=fake_refresh.digest(raw),
                expires_at=datetime.now(UTC) + timedelta(days=30),
                device_name="TestDevice",
                ip_address="10.0.0.1",
                user_agent="TestUA",
            )
        views = await session_service.list_sessions(user_id)
        assert len(views) == 2
        assert views[0].device_name == "TestDevice"
