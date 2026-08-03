"""Shared test fixtures.

Provides deterministic fakes for all security protocols and repository
interfaces, plus a configured test client that bypasses real database and
cache connections.
"""
from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient

from forge_api.domain.auth import WorkspaceRole
from forge_api.domain.security import AccessClaims
from forge_api.domain.sessions import SessionRecord
from forge_api.domain.users import OAuthIdentityRecord, UserRecord
from forge_api.domain.workspaces import MembershipRecord, WorkspaceRecord
from forge_api.infrastructure.settings import get_settings

# ─── Fake security primitives ──────────────────────────────────────


class FakeTokenProvider:
    """Deterministic JWT replacement for tests."""

    def __init__(self) -> None:
        self._store: dict[str, AccessClaims] = {}

    def create_access_token(self, claims: AccessClaims) -> str:
        token = f"fake-access-{claims.user_id}-{claims.session_id}"
        self._store[token] = claims
        return token

    def decode_access_token(self, token: str) -> AccessClaims:
        if token not in self._store:
            raise ValueError("invalid token")
        return self._store[token]


class FakePasswordHasher:
    def hash(self, password: str) -> str:
        return f"hashed:{password}"

    def verify(self, password: str, hashed: str) -> bool:
        return hashed == f"hashed:{password}"


class FakeRefreshTokenGenerator:
    def __init__(self) -> None:
        self._counter = 0

    def generate(self) -> str:
        self._counter += 1
        return f"fake-refresh-{self._counter}"

    def digest(self, token: str) -> str:
        return hashlib.sha256(token.encode()).hexdigest()


# ─── Fake repositories ─────────────────────────────────────────────


class FakeSessionRepository:
    def __init__(self) -> None:
        self._sessions: dict[UUID, SessionRecord] = {}

    async def get(
        self, session_id: UUID, *, user_id: UUID | None = None
    ) -> SessionRecord | None:
        s = self._sessions.get(session_id)
        if s and user_id and s.user_id != user_id:
            return None
        return s

    async def find_by_refresh_hash(self, refresh_hash: str) -> SessionRecord | None:
        for s in self._sessions.values():
            if s.refresh_hash == refresh_hash:
                return s
        return None

    async def list_active(self, user_id: UUID) -> list[SessionRecord]:
        now = datetime.now(UTC)
        return sorted(
            [
                s
                for s in self._sessions.values()
                if s.user_id == user_id
                and s.revoked_at is None
                and s.expires_at > now
            ],
            key=lambda s: s.last_active_at,
            reverse=True,
        )

    async def create(
        self,
        *,
        user_id: UUID,
        family_id: UUID,
        refresh_hash: str,
        expires_at: datetime,
        device_name: str | None,
        ip_address: str | None,
        user_agent: str | None,
    ) -> SessionRecord:
        now = datetime.now(UTC)
        record = SessionRecord(
            id=uuid4(),
            user_id=user_id,
            family_id=family_id,
            refresh_hash=refresh_hash,
            created_at=now,
            expires_at=expires_at,
            revoked_at=None,
            replaced_at=None,
            last_active_at=now,
            device_name=device_name,
            ip_address=ip_address,
            user_agent=user_agent,
        )
        self._sessions[record.id] = record
        return record

    async def rotate(self, session_id: UUID, at: datetime) -> bool:
        s = self._sessions.get(session_id)
        if not s or s.revoked_at:
            return False
        self._sessions[session_id] = SessionRecord(
            id=s.id,
            user_id=s.user_id,
            family_id=s.family_id,
            refresh_hash=s.refresh_hash,
            created_at=s.created_at,
            expires_at=s.expires_at,
            revoked_at=at,
            replaced_at=at,
            last_active_at=s.last_active_at,
            device_name=s.device_name,
            ip_address=s.ip_address,
            user_agent=s.user_agent,
        )
        return True

    async def revoke(self, session_id: UUID, user_id: UUID, at: datetime) -> bool:
        s = self._sessions.get(session_id)
        if not s or s.user_id != user_id or s.revoked_at:
            return False
        self._sessions[session_id] = SessionRecord(
            id=s.id,
            user_id=s.user_id,
            family_id=s.family_id,
            refresh_hash=s.refresh_hash,
            created_at=s.created_at,
            expires_at=s.expires_at,
            revoked_at=at,
            replaced_at=s.replaced_at,
            last_active_at=s.last_active_at,
            device_name=s.device_name,
            ip_address=s.ip_address,
            user_agent=s.user_agent,
        )
        return True

    async def revoke_family(self, family_id: UUID, at: datetime) -> int:
        count = 0
        for sid, s in list(self._sessions.items()):
            if s.family_id == family_id and s.revoked_at is None:
                self._sessions[sid] = SessionRecord(
                    id=s.id,
                    user_id=s.user_id,
                    family_id=s.family_id,
                    refresh_hash=s.refresh_hash,
                    created_at=s.created_at,
                    expires_at=s.expires_at,
                    revoked_at=at,
                    replaced_at=s.replaced_at,
                    last_active_at=s.last_active_at,
                    device_name=s.device_name,
                    ip_address=s.ip_address,
                    user_agent=s.user_agent,
                )
                count += 1
        return count

    async def revoke_all(self, user_id: UUID, at: datetime) -> int:
        count = 0
        for sid, s in list(self._sessions.items()):
            if s.user_id == user_id and s.revoked_at is None:
                self._sessions[sid] = SessionRecord(
                    id=s.id,
                    user_id=s.user_id,
                    family_id=s.family_id,
                    refresh_hash=s.refresh_hash,
                    created_at=s.created_at,
                    expires_at=s.expires_at,
                    revoked_at=at,
                    replaced_at=s.replaced_at,
                    last_active_at=s.last_active_at,
                    device_name=s.device_name,
                    ip_address=s.ip_address,
                    user_agent=s.user_agent,
                )
                count += 1
        return count

    async def touch(
        self, session_id: UUID, at: datetime, *, stale_before: datetime
    ) -> bool:
        s = self._sessions.get(session_id)
        if not s or s.last_active_at >= stale_before:
            return False
        self._sessions[session_id] = SessionRecord(
            id=s.id,
            user_id=s.user_id,
            family_id=s.family_id,
            refresh_hash=s.refresh_hash,
            created_at=s.created_at,
            expires_at=s.expires_at,
            revoked_at=s.revoked_at,
            replaced_at=s.replaced_at,
            last_active_at=at,
            device_name=s.device_name,
            ip_address=s.ip_address,
            user_agent=s.user_agent,
        )
        return True

    async def cleanup_expired(self, now: datetime) -> int:
        expired = [sid for sid, s in self._sessions.items() if s.expires_at < now]
        for sid in expired:
            del self._sessions[sid]
        return len(expired)


class FakeUserRepository:
    def __init__(self) -> None:
        self._users: dict[UUID, UserRecord] = {}

    async def find_by_email(self, email: str) -> UserRecord | None:
        for u in self._users.values():
            if u.email == email.lower():
                return u
        return None

    async def find_by_id(self, user_id: UUID) -> UserRecord | None:
        return self._users.get(user_id)

    async def create(self, *, email: str, password_hash: str | None) -> UserRecord:
        record = UserRecord(
            id=uuid4(),
            email=email.lower(),
            password_hash=password_hash,
            created_at=datetime.now(UTC),
        )
        self._users[record.id] = record
        return record


class FakeOAuthIdentityRepository:
    def __init__(self) -> None:
        self._identities: list[OAuthIdentityRecord] = []

    async def find(self, provider: str, subject: str) -> OAuthIdentityRecord | None:
        for i in self._identities:
            if i.provider == provider and i.subject == subject:
                return i
        return None

    async def create(
        self, *, user_id: UUID, provider: str, subject: str
    ) -> OAuthIdentityRecord:
        record = OAuthIdentityRecord(
            id=uuid4(),
            user_id=user_id,
            provider=provider,
            subject=subject,
            created_at=datetime.now(UTC),
        )
        self._identities.append(record)
        return record


class FakeWorkspaceRepository:
    def __init__(self) -> None:
        self._workspaces: dict[UUID, WorkspaceRecord] = {}
        self._memberships: list[MembershipRecord] = []

    async def list_for_user(
        self, user_id: UUID
    ) -> list[tuple[WorkspaceRecord, WorkspaceRole]]:
        results = []
        for m in self._memberships:
            if m.user_id == user_id:
                w = self._workspaces.get(m.workspace_id)
                if w and w.deleted_at is None:
                    results.append((w, m.role))
        return results

    async def get(self, workspace_id: UUID) -> WorkspaceRecord | None:
        w = self._workspaces.get(workspace_id)
        if w and w.deleted_at is None:
            return w
        return None

    async def get_membership(
        self, workspace_id: UUID, user_id: UUID
    ) -> MembershipRecord | None:
        for m in self._memberships:
            if m.workspace_id == workspace_id and m.user_id == user_id:
                return m
        return None

    async def create(self, *, name: str) -> WorkspaceRecord:
        record = WorkspaceRecord(
            id=uuid4(),
            name=name,
            created_at=datetime.now(UTC),
            deleted_at=None,
        )
        self._workspaces[record.id] = record
        return record

    async def add_member(
        self, *, workspace_id: UUID, user_id: UUID, role: WorkspaceRole
    ) -> None:
        self._memberships.append(
            MembershipRecord(
                workspace_id=workspace_id,
                user_id=user_id,
                role=role,
                created_at=datetime.now(UTC),
            )
        )

    async def rename(self, workspace_id: UUID, name: str) -> WorkspaceRecord | None:
        w = self._workspaces.get(workspace_id)
        if not w or w.deleted_at:
            return None
        updated = WorkspaceRecord(
            id=w.id, name=name, created_at=w.created_at, deleted_at=None
        )
        self._workspaces[workspace_id] = updated
        return updated


# ─── Fake audit logger ──────────────────────────────────────────────


class FakeAuditLogger:
    """Collects audit events in memory for assertion."""

    def __init__(self) -> None:
        self.events: list[dict[str, Any]] = []

    def record(self, event) -> None:
        self.events.append({"event": event})

    def log(self, event_type, **kwargs) -> None:
        self.events.append({"event": event_type, **kwargs})


# ─── Fixtures ───────────────────────────────────────────────────────


@pytest.fixture
def fake_tokens() -> FakeTokenProvider:
    return FakeTokenProvider()


@pytest.fixture
def fake_passwords() -> FakePasswordHasher:
    return FakePasswordHasher()


@pytest.fixture
def fake_refresh() -> FakeRefreshTokenGenerator:
    return FakeRefreshTokenGenerator()


@pytest.fixture
def fake_sessions() -> FakeSessionRepository:
    return FakeSessionRepository()


@pytest.fixture
def fake_users() -> FakeUserRepository:
    return FakeUserRepository()


@pytest.fixture
def fake_oauth_identities() -> FakeOAuthIdentityRepository:
    return FakeOAuthIdentityRepository()


@pytest.fixture
def fake_workspaces() -> FakeWorkspaceRepository:
    return FakeWorkspaceRepository()


@pytest.fixture
def fake_audit() -> FakeAuditLogger:
    return FakeAuditLogger()


@pytest.fixture
def test_client(monkeypatch) -> TestClient:
    """Create a TestClient with env vars set so Settings can load."""
    monkeypatch.setenv(
        "FORGE_DATABASE_URL",
        "postgresql+asyncpg://forge:secret@localhost:5432/forge",
    )
    monkeypatch.setenv("FORGE_REDIS_URL", "redis://localhost:6379/0")
    monkeypatch.setenv(
        "FORGE_JWT_SECRET",
        "test-secret-that-is-at-least-32-chars-long-for-security",
    )
    get_settings.cache_clear()
    from forge_api.presentation.http.app import create_app

    return TestClient(create_app(), raise_server_exceptions=False)
