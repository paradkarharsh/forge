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
from forge_api.domain.repository import (
    BranchRecord,
    CloneStatus,
    RepositoryEventRecord,
    RepositoryRecord,
    RepositoryVisibility,
    SyncJobRecord,
    SyncJobStatus,
    SyncStatus,
)
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


_SENTINEL = object()


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

    async def get_by_slug(self, slug: str) -> WorkspaceRecord | None:
        for w in self._workspaces.values():
            if w.slug == slug.lower() and w.deleted_at is None:
                return w
        return None

    async def get_membership(
        self, workspace_id: UUID, user_id: UUID
    ) -> MembershipRecord | None:
        for m in self._memberships:
            if m.workspace_id == workspace_id and m.user_id == user_id:
                return m
        return None

    async def list_members(self, workspace_id: UUID) -> list[MembershipRecord]:
        return [m for m in self._memberships if m.workspace_id == workspace_id]

    async def create(
        self, *, name: str, slug: str, description: str | None = None
    ) -> WorkspaceRecord:
        record = WorkspaceRecord(
            id=uuid4(),
            name=name,
            slug=slug.lower(),
            created_at=datetime.now(UTC),
            deleted_at=None,
            description=description,
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

    async def remove_member(self, workspace_id: UUID, user_id: UUID) -> bool:
        for i, m in enumerate(self._memberships):
            if m.workspace_id == workspace_id and m.user_id == user_id:
                self._memberships.pop(i)
                return True
        return False

    async def update_member_role(
        self, workspace_id: UUID, user_id: UUID, role: WorkspaceRole
    ) -> bool:
        for i, m in enumerate(self._memberships):
            if m.workspace_id == workspace_id and m.user_id == user_id:
                self._memberships[i] = MembershipRecord(
                    workspace_id=m.workspace_id,
                    user_id=m.user_id,
                    role=role,
                    created_at=m.created_at,
                )
                return True
        return False

    async def rename(self, workspace_id: UUID, name: str) -> WorkspaceRecord | None:
        w = self._workspaces.get(workspace_id)
        if not w or w.deleted_at:
            return None
        updated = WorkspaceRecord(
            id=w.id, name=name, slug=w.slug, created_at=w.created_at,
            deleted_at=None, description=w.description,
        )
        self._workspaces[workspace_id] = updated
        return updated

    async def update(
        self,
        workspace_id: UUID,
        *,
        name: str | None = None,
        slug: str | None = None,
        description: str | None = _SENTINEL,
    ) -> WorkspaceRecord | None:
        w = self._workspaces.get(workspace_id)
        if not w or w.deleted_at:
            return None
        updated = WorkspaceRecord(
            id=w.id,
            name=name if name is not None else w.name,
            slug=slug.lower() if slug is not None else w.slug,
            created_at=w.created_at,
            deleted_at=None,
            description=description if description is not _SENTINEL else w.description,
        )
        self._workspaces[workspace_id] = updated
        return updated

    async def soft_delete(self, workspace_id: UUID) -> bool:
        w = self._workspaces.get(workspace_id)
        if not w or w.deleted_at:
            return False
        self._workspaces[workspace_id] = WorkspaceRecord(
            id=w.id, name=w.name, slug=w.slug, created_at=w.created_at,
            deleted_at=datetime.now(UTC), description=w.description,
        )
        return True


# ─── Fake audit logger ──────────────────────────────────────────────


class FakeAuditLogger:
    """Collects audit events in memory for assertion."""

    def __init__(self) -> None:
        self.events: list[dict[str, Any]] = []

    def record(self, event) -> None:
        self.events.append({"event": event})

    def log(self, event_type, **kwargs) -> None:
        self.events.append({"event": event_type, **kwargs})


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


# ─── Fake repository domain repositories ────────────────────────────


class FakeRepositoryRepository:
    def __init__(self) -> None:
        self._repos: dict[UUID, RepositoryRecord] = {}

    async def get(self, repository_id: UUID) -> RepositoryRecord | None:
        r = self._repos.get(repository_id)
        if r and r.deleted_at is None:
            return r
        return None

    async def get_by_workspace(
        self,
        workspace_id: UUID,
        *,
        include_archived: bool = False,
        include_deleted: bool = False,
    ) -> list[RepositoryRecord]:
        results = []
        for r in self._repos.values():
            if r.workspace_id != workspace_id:
                continue
            if not include_deleted and r.deleted_at:
                continue
            if not include_archived and r.archived_at:
                continue
            results.append(r)
        return sorted(results, key=lambda x: x.created_at, reverse=True)

    async def create(
        self,
        *,
        workspace_id: UUID,
        name: str,
        owner: str,
        provider: str,
        remote_url: str | None = None,
        local_path: str | None = None,
        default_branch: str | None = None,
        clone_status: str = "pending",
        sync_status: str = "idle",
        visibility: str = "private",
        description: str | None = None,
    ) -> RepositoryRecord:
        now = datetime.now(UTC)
        record = RepositoryRecord(
            id=uuid4(),
            workspace_id=workspace_id,
            name=name,
            owner=owner,
            provider=provider,
            remote_url=remote_url,
            local_path=local_path,
            default_branch=default_branch,
            current_branch=None,
            clone_status=CloneStatus(clone_status),
            sync_status=SyncStatus(sync_status),
            visibility=RepositoryVisibility(visibility),
            description=description,
            size_bytes=None,
            last_commit_hash=None,
            last_synced_at=None,
            created_at=now,
            updated_at=now,
            archived_at=None,
            deleted_at=None,
        )
        self._repos[record.id] = record
        return record

    async def update(
        self,
        repository_id: UUID,
        **kwargs,
    ) -> RepositoryRecord | None:
        r = self._repos.get(repository_id)
        if not r or r.deleted_at:
            return None
        fields = {
            "name": r.name,
            "description": r.description,
            "default_branch": r.default_branch,
            "current_branch": r.current_branch,
            "clone_status": r.clone_status,
            "sync_status": r.sync_status,
            "visibility": r.visibility,
            "local_path": r.local_path,
            "size_bytes": r.size_bytes,
            "last_commit_hash": r.last_commit_hash,
            "last_synced_at": r.last_synced_at,
        }
        for k, v in kwargs.items():
            if k in fields:
                if k == "clone_status" and isinstance(v, str):
                    v = CloneStatus(v)
                elif k == "sync_status" and isinstance(v, str):
                    v = SyncStatus(v)
                elif k == "visibility" and isinstance(v, str):
                    v = RepositoryVisibility(v)
                fields[k] = v
        updated = RepositoryRecord(
            id=r.id,
            workspace_id=r.workspace_id,
            owner=r.owner,
            provider=r.provider,
            remote_url=r.remote_url,
            created_at=r.created_at,
            updated_at=datetime.now(UTC),
            archived_at=r.archived_at,
            deleted_at=r.deleted_at,
            **fields,
        )
        self._repos[repository_id] = updated
        return updated

    async def soft_delete(self, repository_id: UUID) -> bool:
        r = self._repos.get(repository_id)
        if not r or r.deleted_at:
            return False
        self._repos[repository_id] = RepositoryRecord(
            id=r.id, workspace_id=r.workspace_id, name=r.name, owner=r.owner,
            provider=r.provider, remote_url=r.remote_url, local_path=r.local_path,
            default_branch=r.default_branch, current_branch=r.current_branch,
            clone_status=r.clone_status, sync_status=r.sync_status,
            visibility=r.visibility, description=r.description,
            size_bytes=r.size_bytes, last_commit_hash=r.last_commit_hash,
            last_synced_at=r.last_synced_at, created_at=r.created_at,
            updated_at=datetime.now(UTC), archived_at=r.archived_at,
            deleted_at=datetime.now(UTC),
        )
        return True

    async def archive(self, repository_id: UUID) -> bool:
        r = self._repos.get(repository_id)
        if not r or r.deleted_at or r.archived_at:
            return False
        self._repos[repository_id] = RepositoryRecord(
            id=r.id, workspace_id=r.workspace_id, name=r.name, owner=r.owner,
            provider=r.provider, remote_url=r.remote_url, local_path=r.local_path,
            default_branch=r.default_branch, current_branch=r.current_branch,
            clone_status=r.clone_status, sync_status=r.sync_status,
            visibility=r.visibility, description=r.description,
            size_bytes=r.size_bytes, last_commit_hash=r.last_commit_hash,
            last_synced_at=r.last_synced_at, created_at=r.created_at,
            updated_at=datetime.now(UTC), archived_at=datetime.now(UTC),
            deleted_at=None,
        )
        return True

    async def restore(self, repository_id: UUID) -> RepositoryRecord | None:
        r = self._repos.get(repository_id)
        if not r:
            return None
        restored = RepositoryRecord(
            id=r.id, workspace_id=r.workspace_id, name=r.name, owner=r.owner,
            provider=r.provider, remote_url=r.remote_url, local_path=r.local_path,
            default_branch=r.default_branch, current_branch=r.current_branch,
            clone_status=r.clone_status, sync_status=r.sync_status,
            visibility=r.visibility, description=r.description,
            size_bytes=r.size_bytes, last_commit_hash=r.last_commit_hash,
            last_synced_at=r.last_synced_at, created_at=r.created_at,
            updated_at=datetime.now(UTC), archived_at=None, deleted_at=None,
        )
        self._repos[repository_id] = restored
        return restored


class FakeRepositoryBranchRepository:
    def __init__(self) -> None:
        self._branches: list[BranchRecord] = []

    async def list_by_repository(self, repository_id: UUID) -> list[BranchRecord]:
        return sorted(
            [b for b in self._branches if b.repository_id == repository_id],
            key=lambda b: b.name,
        )

    async def upsert(
        self,
        *,
        repository_id: UUID,
        name: str,
        commit_hash: str | None = None,
        is_default: bool = False,
        is_protected: bool = False,
    ) -> BranchRecord:
        for i, b in enumerate(self._branches):
            if b.repository_id == repository_id and b.name == name:
                updated = BranchRecord(
                    id=b.id, repository_id=repository_id, name=name,
                    commit_hash=commit_hash, is_default=is_default,
                    is_protected=is_protected, created_at=b.created_at,
                )
                self._branches[i] = updated
                return updated
        record = BranchRecord(
            id=uuid4(), repository_id=repository_id, name=name,
            commit_hash=commit_hash, is_default=is_default,
            is_protected=is_protected, created_at=datetime.now(UTC),
        )
        self._branches.append(record)
        return record

    async def delete_by_repository(self, repository_id: UUID) -> int:
        before = len(self._branches)
        self._branches = [b for b in self._branches if b.repository_id != repository_id]
        return before - len(self._branches)


class FakeRepositorySyncJobRepository:
    def __init__(self) -> None:
        self._jobs: dict[UUID, SyncJobRecord] = {}

    async def get(self, job_id: UUID) -> SyncJobRecord | None:
        return self._jobs.get(job_id)

    async def list_by_repository(
        self, repository_id: UUID, *, job_type: str | None = None
    ) -> list[SyncJobRecord]:
        results = [
            j for j in self._jobs.values()
            if j.repository_id == repository_id
            and (job_type is None or j.job_type == job_type)
        ]
        return sorted(results, key=lambda j: j.created_at, reverse=True)

    async def create(
        self, *, repository_id: UUID, job_type: str, status: str = "pending",
    ) -> SyncJobRecord:
        record = SyncJobRecord(
            id=uuid4(), repository_id=repository_id, job_type=job_type,
            status=SyncJobStatus(status), started_at=None, completed_at=None,
            error_message=None, created_at=datetime.now(UTC),
        )
        self._jobs[record.id] = record
        return record

    async def update_status(
        self, job_id: UUID, *, status: str, error_message: str | None = None,
    ) -> SyncJobRecord | None:
        j = self._jobs.get(job_id)
        if not j:
            return None
        now = datetime.now(UTC)
        updated = SyncJobRecord(
            id=j.id, repository_id=j.repository_id, job_type=j.job_type,
            status=SyncJobStatus(status),
            started_at=now if status == "running" and not j.started_at else j.started_at,
            completed_at=now if status in ("completed", "failed") else j.completed_at,
            error_message=error_message if error_message is not None else j.error_message,
            created_at=j.created_at,
        )
        self._jobs[job_id] = updated
        return updated


class FakeRepositoryEventRepository:
    def __init__(self) -> None:
        self._events: list[RepositoryEventRecord] = []

    async def list_by_repository(
        self, repository_id: UUID, *, limit: int = 50
    ) -> list[RepositoryEventRecord]:
        filtered = [e for e in self._events if e.repository_id == repository_id]
        return sorted(filtered, key=lambda e: e.created_at, reverse=True)[:limit]

    async def create(
        self,
        *,
        repository_id: UUID,
        event_type: str,
        actor_id: UUID | None = None,
        payload: dict | None = None,
    ) -> RepositoryEventRecord:
        record = RepositoryEventRecord(
            id=uuid4(), repository_id=repository_id, event_type=event_type,
            actor_id=actor_id, payload=payload, created_at=datetime.now(UTC),
        )
        self._events.append(record)
        return record


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
def fake_repositories() -> FakeRepositoryRepository:
    return FakeRepositoryRepository()


@pytest.fixture
def fake_branches() -> FakeRepositoryBranchRepository:
    return FakeRepositoryBranchRepository()


@pytest.fixture
def fake_sync_jobs() -> FakeRepositorySyncJobRepository:
    return FakeRepositorySyncJobRepository()


@pytest.fixture
def fake_repo_events() -> FakeRepositoryEventRepository:
    return FakeRepositoryEventRepository()
