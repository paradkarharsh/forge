"""Shared test fixtures.

Provides deterministic fakes for all security protocols and repository
interfaces, plus a configured test client that bypasses real database and
cache connections.
"""
from __future__ import annotations

import asyncio
import hashlib
import os
from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

import asyncpg
import pytest
from alembic.config import Config
from fastapi.testclient import TestClient

from alembic import command
from forge_api.domain.auth import WorkspaceRole
from forge_api.domain.errors import DomainError
from forge_api.domain.indexing import (
    ChunkRecord,
    DependencyRecord,
    DiscoveredFile,
    FileRecord,
    IndexStatus,
    SymbolRecord,
)
from forge_api.domain.memory import (
    ConversationContextEntry,
    MemoryRecord,
    MemoryStatus,
)
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
from forge_api.infrastructure.language_map import detect_language
from forge_api.infrastructure.settings import get_settings
from forge_api.presentation.http.security_middleware import RateLimitMiddleware

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
        f"postgresql+asyncpg://{PG_USER}:{PG_PASSWORD}@{PG_HOST}:{PG_PORT}/forge",
    )
    monkeypatch.setenv("FORGE_REDIS_URL", "redis://localhost:6379/0")
    monkeypatch.setenv(
        "FORGE_JWT_SECRET",
        "test-secret-that-is-at-least-32-chars-long-for-security",
    )
    monkeypatch.setenv("FORGE_INDEX_WORKER_ENABLED", "false")
    monkeypatch.setenv("FORGE_MEMORY_MAINTENANCE_WORKER_ENABLED", "false")
    get_settings.cache_clear()
    from forge_api.presentation.http.app import create_app

    client = TestClient(
        create_app(),
        base_url="http://localhost",
        raise_server_exceptions=False,
    )
    yield client
    get_settings.cache_clear()



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
            "index_status": r.index_status,
            "indexed_at": r.indexed_at,
            "file_count": r.file_count,
            "symbol_count": r.symbol_count,
        }
        for k, v in kwargs.items():
            if k in fields:
                if k == "clone_status" and isinstance(v, str):
                    v = CloneStatus(v)
                elif k == "sync_status" and isinstance(v, str):
                    v = SyncStatus(v)
                elif k == "visibility" and isinstance(v, str):
                    v = RepositoryVisibility(v)
                elif k == "index_status" and isinstance(v, str):
                    v = IndexStatus(v)
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

    async def find_pending_by_type(self, job_type: str) -> SyncJobRecord | None:
        pending = [
            j for j in self._jobs.values()
            if j.job_type.value == job_type and j.status == SyncJobStatus.PENDING
        ]
        if not pending:
            return None
        return sorted(pending, key=lambda j: j.created_at)[0]


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


class FakeRepositoryFileRepository:
    def __init__(self) -> None:
        self._files: dict[UUID, FileRecord] = {}

    async def get(self, file_id: UUID) -> FileRecord | None:
        return self._files.get(file_id)

    async def get_by_path(
        self, repository_id: UUID, path: str
    ) -> FileRecord | None:
        for f in self._files.values():
            if f.repository_id == repository_id and f.path == path:
                return f
        return None

    async def list_by_repository(
        self, repository_id: UUID, *, language: str | None = None
    ) -> list[FileRecord]:
        results = [
            f for f in self._files.values()
            if f.repository_id == repository_id
            and (language is None or f.language == language)
        ]
        return sorted(results, key=lambda f: f.path)

    async def upsert(
        self,
        *,
        repository_id: UUID,
        path: str,
        language: str | None,
        size_bytes: int,
        line_count: int | None,
        commit_hash: str,
        content_hash: str,
    ) -> FileRecord:
        existing = None
        for f in self._files.values():
            if f.repository_id == repository_id and f.path == path:
                existing = f
                break
        if existing is not None:
            record = FileRecord(
                id=existing.id, repository_id=repository_id, path=path,
                language=language, size_bytes=size_bytes, line_count=line_count,
                commit_hash=commit_hash, content_hash=content_hash,
                indexed_at=datetime.now(UTC),
            )
            self._files[record.id] = record
            return record
        record = FileRecord(
            id=uuid4(), repository_id=repository_id, path=path,
            language=language, size_bytes=size_bytes, line_count=line_count,
            commit_hash=commit_hash, content_hash=content_hash,
            indexed_at=datetime.now(UTC),
        )
        self._files[record.id] = record
        return record

    async def delete_by_repository(self, repository_id: UUID) -> int:
        before = len(self._files)
        self._files = {
            k: v for k, v in self._files.items()
            if v.repository_id != repository_id
        }
        return before - len(self._files)

    async def delete_by_paths(
        self, repository_id: UUID, paths: list[str]
    ) -> int:
        targets = set(paths)
        before = len(self._files)
        self._files = {
            k: v for k, v in self._files.items()
            if not (v.repository_id == repository_id and v.path in targets)
        }
        return before - len(self._files)


class FakeRepositorySymbolRepository:
    def __init__(self) -> None:
        self._symbols: list[SymbolRecord] = []

    async def list_by_file(self, file_id: UUID) -> list[SymbolRecord]:
        return sorted(
            [s for s in self._symbols if s.file_id == file_id],
            key=lambda s: s.line_start,
        )

    async def list_by_repository(
        self, repository_id: UUID, *, kind: str | None = None
    ) -> list[SymbolRecord]:
        result = [
            s for s in self._symbols
            if s.repository_id == repository_id
            and (kind is None or s.kind.value == kind)
        ]
        return sorted(result, key=lambda s: s.line_start)

    async def search_by_name(
        self,
        repository_id: UUID,
        query: str,
        *,
        kind: str | None = None,
        limit: int = 50,
    ) -> list[SymbolRecord]:
        result = [
            s for s in self._symbols
            if s.repository_id == repository_id
            and query.lower() in s.name.lower()
            and (kind is None or s.kind.value == kind)
        ]
        return sorted(result, key=lambda s: s.name)[:limit]

    async def bulk_create(self, symbols: list[SymbolRecord]) -> None:
        self._symbols.extend(symbols)

    async def delete_by_file(self, file_id: UUID) -> int:
        before = len(self._symbols)
        self._symbols = [s for s in self._symbols if s.file_id != file_id]
        return before - len(self._symbols)

    async def delete_by_repository(self, repository_id: UUID) -> int:
        before = len(self._symbols)
        self._symbols = [
            s for s in self._symbols if s.repository_id != repository_id
        ]
        return before - len(self._symbols)


class FakeRepositoryDependencyRepository:
    def __init__(self) -> None:
        self._dependencies: list[DependencyRecord] = []

    async def _all(self) -> list[DependencyRecord]:
        return self._dependencies

    async def list_by_file(self, source_file_id: UUID) -> list[DependencyRecord]:
        return [
            d for d in self._dependencies if d.source_file_id == source_file_id
        ]

    async def list_dependents(self, target_file_id: UUID) -> list[DependencyRecord]:
        return [
            d for d in self._dependencies if d.target_file_id == target_file_id
        ]

    async def bulk_create(self, dependencies: list[DependencyRecord]) -> None:
        self._dependencies.extend(dependencies)

    async def delete_by_file(self, source_file_id: UUID) -> int:
        before = len(self._dependencies)
        self._dependencies = [
            d for d in self._dependencies
            if d.source_file_id != source_file_id
        ]
        return before - len(self._dependencies)

    async def delete_by_repository(self, repository_id: UUID) -> int:
        before = len(self._dependencies)
        self._dependencies = [
            d for d in self._dependencies
            if d.repository_id != repository_id
        ]
        return before - len(self._dependencies)


class FakeRepositoryChunkRepository:
    def __init__(self) -> None:
        self._chunks: list[ChunkRecord] = []

    async def list_by_file(self, file_id: UUID) -> list[ChunkRecord]:
        return sorted(
            [c for c in self._chunks if c.file_id == file_id],
            key=lambda c: c.chunk_index,
        )

    async def search_semantic(
        self,
        repository_id: UUID,
        query_embedding: list[float],
        *,
        limit: int = 20,
    ) -> list[ChunkRecord]:
        scored = []
        for c in self._chunks:
            if c.repository_id != repository_id or c.embedding is None:
                continue
            dot = sum(a * b for a, b in zip(c.embedding, query_embedding, strict=False))
            scored.append((dot, c))
        scored.sort(key=lambda x: x[0], reverse=True)
        return [c for _, c in scored[:limit]]

    async def bulk_create(self, chunks: list[ChunkRecord]) -> None:
        self._chunks.extend(chunks)

    async def delete_by_file(self, file_id: UUID) -> int:
        before = len(self._chunks)
        self._chunks = [c for c in self._chunks if c.file_id != file_id]
        return before - len(self._chunks)

    async def delete_by_repository(self, repository_id: UUID) -> int:
        before = len(self._chunks)
        self._chunks = [c for c in self._chunks if c.repository_id != repository_id]
        return before - len(self._chunks)


class FakeGitClient:
    """In-memory ``GitClient`` backed by a {path: bytes} content map."""

    def __init__(self, files: dict[str, bytes] | None = None) -> None:
        self._files = files or {}
        self._rev = "a" * 40
        self._diff_entries: list = []

    def set_revision(self, rev: str) -> None:
        self._rev = rev

    def set_files(self, files: dict[str, bytes]) -> None:
        self._files = files

    def set_diff(self, entries: list) -> None:
        self._diff_entries = entries

    async def head_revision(self, repo_dir: str) -> str:
        return self._rev

    async def list_tree(self, repo_dir: str, rev: str = "HEAD") -> list[DiscoveredFile]:
        return [
            DiscoveredFile(
                path=path,
                language=detect_language(path),
                size_bytes=len(content),
            )
            for path, content in sorted(self._files.items())
        ]

    async def read_file(self, repo_dir: str, rev: str, path: str) -> bytes:
        if path not in self._files:
            raise DomainError("git show failed: not found", code="git_error")
        return self._files[path]

    async def diff_name_status(
        self, repo_dir: str, old_rev: str, new_rev: str
    ) -> list:
        return list(self._diff_entries)


# ─── Fake context and memory fakes ───────────────────────────────────


class FakeMemoryRepository:
    """In-memory ``MemoryRepository`` mirroring the adapter's isolation rules."""

    def __init__(self) -> None:
        self._memories: dict[UUID, MemoryRecord] = {}

    def _active(
        self, workspace_id: UUID, *, repository_id=None, user_id=None
    ):
        # Mirrors the SQL adapter: a workspace-level query (user_id is None)
        # never surfaces another user's memories.
        def _user_match(m) -> bool:
            if user_id is not None:
                return m.user_id == user_id
            return m.user_id is None

        return [
            m for m in self._memories.values()
            if m.workspace_id == workspace_id
            and m.deleted_at is None
            and (repository_id is None or m.repository_id == repository_id)
            and _user_match(m)
        ]

    async def get(self, memory_id: UUID) -> MemoryRecord | None:
        m = self._memories.get(memory_id)
        if m is None or m.deleted_at is not None:
            return None
        return m

    async def list_by_workspace(
        self,
        workspace_id: UUID,
        *,
        memory_type: str | None = None,
        status: str | None = None,
        tags: list[str] | None = None,
        limit: int = 50,
    ) -> list[MemoryRecord]:
        rows = self._active(workspace_id)
        rows = self._filter(rows, memory_type, status, tags)
        return sorted(rows, key=lambda m: m.updated_at, reverse=True)[:limit]

    async def list_by_repository(
        self,
        repository_id: UUID,
        *,
        memory_type: str | None = None,
        status: str | None = None,
        tags: list[str] | None = None,
        limit: int = 50,
    ) -> list[MemoryRecord]:
        rows = [
            m for m in self._memories.values()
            if m.repository_id == repository_id and m.deleted_at is None
        ]
        rows = self._filter(rows, memory_type, status, tags)
        return sorted(rows, key=lambda m: m.updated_at, reverse=True)[:limit]

    async def list_by_user(
        self,
        workspace_id: UUID,
        user_id: UUID,
        *,
        memory_type: str | None = None,
        status: str | None = None,
        tags: list[str] | None = None,
        limit: int = 50,
    ) -> list[MemoryRecord]:
        rows = self._active(workspace_id, user_id=user_id)
        rows = self._filter(rows, memory_type, status, tags)
        return sorted(rows, key=lambda m: m.updated_at, reverse=True)[:limit]

    async def create(
        self,
        *,
        workspace_id: UUID,
        repository_id: UUID | None = None,
        user_id: UUID | None = None,
        memory_type: str,
        scope: str,
        content: str,
        summary: str | None = None,
        source_file_path: str | None = None,
        source_symbol_name: str | None = None,
        source_commit_hash: str | None = None,
        confidence: float = 1.0,
        tags: list[str] | None = None,
        embedding: list[float] | None = None,
        created_by: UUID | None = None,
        expires_at: datetime | None = None,
    ) -> MemoryRecord:
        now = datetime.now(UTC)
        record = MemoryRecord(
            id=uuid4(),
            workspace_id=workspace_id,
            repository_id=repository_id,
            user_id=user_id,
            memory_type=memory_type,
            scope=scope,
            status=MemoryStatus.ACTIVE,
            content=content,
            summary=summary,
            source_file_path=source_file_path,
            source_symbol_name=source_symbol_name,
            source_commit_hash=source_commit_hash,
            confidence=confidence,
            tags=list(tags or []),
            embedding=embedding,
            created_by=created_by,
            created_at=now,
            updated_at=now,
            accessed_at=None,
            expires_at=expires_at,
            deleted_at=None,
        )
        self._memories[record.id] = record
        return record

    async def update(
        self,
        memory_id: UUID,
        *,
        content: str | None = None,
        summary: str | None = _SENTINEL,
        status: str | None = None,
        confidence: float | None = None,
        tags: list[str] | None = None,
        embedding: list[float] | None = _SENTINEL,
        expires_at: datetime | None = _SENTINEL,
    ) -> MemoryRecord | None:
        m = self._memories.get(memory_id)
        if m is None or m.deleted_at is not None:
            return None
        fields = {
            "content": m.content,
            "summary": m.summary,
            "status": m.status,
            "confidence": m.confidence,
            "tags": list(m.tags),
            "embedding": m.embedding,
            "expires_at": m.expires_at,
        }
        if content is not None:
            fields["content"] = content
        if summary is not _SENTINEL:
            fields["summary"] = summary
        if status is not None:
            fields["status"] = MemoryStatus(status)
        if confidence is not None:
            fields["confidence"] = confidence
        if tags is not None:
            fields["tags"] = list(tags)
        if embedding is not _SENTINEL:
            fields["embedding"] = embedding
        if expires_at is not _SENTINEL:
            fields["expires_at"] = expires_at
        updated = MemoryRecord(
            id=m.id,
            workspace_id=m.workspace_id,
            repository_id=m.repository_id,
            user_id=m.user_id,
            memory_type=m.memory_type,
            scope=m.scope,
            source_file_path=m.source_file_path,
            source_symbol_name=m.source_symbol_name,
            source_commit_hash=m.source_commit_hash,
            created_by=m.created_by,
            created_at=m.created_at,
            updated_at=datetime.now(UTC),
            accessed_at=m.accessed_at,
            deleted_at=m.deleted_at,
            **fields,
        )
        self._memories[memory_id] = updated
        return updated

    async def soft_delete(self, memory_id: UUID) -> bool:
        m = self._memories.get(memory_id)
        if m is None or m.deleted_at is not None:
            return False
        self._memories[memory_id] = MemoryRecord(
            id=m.id,
            workspace_id=m.workspace_id,
            repository_id=m.repository_id,
            user_id=m.user_id,
            memory_type=m.memory_type,
            scope=m.scope,
            status=m.status,
            content=m.content,
            summary=m.summary,
            source_file_path=m.source_file_path,
            source_symbol_name=m.source_symbol_name,
            source_commit_hash=m.source_commit_hash,
            confidence=m.confidence,
            tags=list(m.tags),
            embedding=m.embedding,
            created_by=m.created_by,
            created_at=m.created_at,
            updated_at=m.updated_at,
            accessed_at=m.accessed_at,
            expires_at=m.expires_at,
            deleted_at=datetime.now(UTC),
        )
        return True

    async def search_semantic(
        self,
        workspace_id: UUID,
        query_embedding: list[float],
        *,
        repository_id: UUID | None = None,
        user_id: UUID | None = None,
        limit: int = 20,
    ) -> list[MemoryRecord]:
        rows = self._active(
            workspace_id, repository_id=repository_id, user_id=user_id
        )
        rows = [
            m for m in rows
            if m.embedding is not None and m.status == MemoryStatus.ACTIVE
        ]
        scored = []
        for m in rows:
            dot = sum(
                a * b for a, b in zip(m.embedding, query_embedding, strict=False)
            )
            scored.append((dot, m))
        scored.sort(key=lambda x: x[0], reverse=True)
        return [m for _, m in scored[:limit]]

    async def search_by_tags(
        self,
        workspace_id: UUID,
        tags: list[str],
        *,
        repository_id: UUID | None = None,
        limit: int = 50,
    ) -> list[MemoryRecord]:
        rows = self._active(workspace_id, repository_id=repository_id)
        rows = [m for m in rows if all(t in m.tags for t in tags)]
        return sorted(rows, key=lambda m: m.updated_at, reverse=True)[:limit]

    async def mark_stale(
        self, repository_id: UUID, paths: list[str],
    ) -> int:
        count = 0
        for mid, m in list(self._memories.items()):
            if (
                m.repository_id == repository_id
                and m.deleted_at is None
                and m.status == MemoryStatus.ACTIVE
                and m.source_file_path in paths
            ):
                self._memories[mid] = MemoryRecord(
                    id=m.id,
                    workspace_id=m.workspace_id,
                    repository_id=m.repository_id,
                    user_id=m.user_id,
                    memory_type=m.memory_type,
                    scope=m.scope,
                    status=MemoryStatus.STALE,
                    content=m.content,
                    summary=m.summary,
                    source_file_path=m.source_file_path,
                    source_symbol_name=m.source_symbol_name,
                    source_commit_hash=m.source_commit_hash,
                    confidence=m.confidence,
                    tags=list(m.tags),
                    embedding=m.embedding,
                    created_by=m.created_by,
                    created_at=m.created_at,
                    updated_at=m.updated_at,
                    accessed_at=m.accessed_at,
                    expires_at=m.expires_at,
                    deleted_at=m.deleted_at,
                )
                count += 1
        return count

    async def delete_by_repository(self, repository_id: UUID) -> int:
        before = len(self._memories)
        self._memories = {
            k: v for k, v in self._memories.items()
            if v.repository_id != repository_id
        }
        return before - len(self._memories)

    async def touch_accessed(self, memory_ids: list[UUID]) -> None:
        for mid in memory_ids:
            m = self._memories.get(mid)
            if m is not None:
                self._memories[mid] = MemoryRecord(
                    id=m.id,
                    workspace_id=m.workspace_id,
                    repository_id=m.repository_id,
                    user_id=m.user_id,
                    memory_type=m.memory_type,
                    scope=m.scope,
                    status=m.status,
                    content=m.content,
                    summary=m.summary,
                    source_file_path=m.source_file_path,
                    source_symbol_name=m.source_symbol_name,
                    source_commit_hash=m.source_commit_hash,
                    confidence=m.confidence,
                    tags=list(m.tags),
                    embedding=m.embedding,
                    created_by=m.created_by,
                    created_at=m.created_at,
                    updated_at=m.updated_at,
                    accessed_at=datetime.now(UTC),
                    expires_at=m.expires_at,
                    deleted_at=m.deleted_at,
                )

    async def find_expired(
        self, now: datetime, *, limit: int = 100,
    ) -> list[MemoryRecord]:
        rows = [
            m for m in self._memories.values()
            if m.expires_at is not None
            and m.expires_at < now
            and m.status == MemoryStatus.ACTIVE
            and m.deleted_at is None
        ]
        return rows[:limit]

    async def find_missing_embeddings(
        self, *, limit: int = 100,
    ) -> list[MemoryRecord]:
        rows = [
            m for m in self._memories.values()
            if m.embedding is None and m.deleted_at is None
        ]
        return rows[:limit]

    async def hard_delete_old(self, older_than: datetime) -> int:
        before = len(self._memories)
        self._memories = {
            k: v for k, v in self._memories.items()
            if v.deleted_at is None or v.deleted_at >= older_than
        }
        return before - len(self._memories)

    async def bulk_update_status(
        self, memory_ids: list[UUID], status: str,
    ) -> int:
        count = 0
        for mid in memory_ids:
            m = self._memories.get(mid)
            if m is not None:
                self._memories[mid] = MemoryRecord(
                    id=m.id,
                    workspace_id=m.workspace_id,
                    repository_id=m.repository_id,
                    user_id=m.user_id,
                    memory_type=m.memory_type,
                    scope=m.scope,
                    status=MemoryStatus(status),
                    content=m.content,
                    summary=m.summary,
                    source_file_path=m.source_file_path,
                    source_symbol_name=m.source_symbol_name,
                    source_commit_hash=m.source_commit_hash,
                    confidence=m.confidence,
                    tags=list(m.tags),
                    embedding=m.embedding,
                    created_by=m.created_by,
                    created_at=m.created_at,
                    updated_at=m.updated_at,
                    accessed_at=m.accessed_at,
                    expires_at=m.expires_at,
                    deleted_at=m.deleted_at,
                )
                count += 1
        return count

    async def bulk_update_embeddings(
        self, updates: list[tuple[UUID, list[float]]],
    ) -> int:
        count = 0
        for mid, vector in updates:
            m = self._memories.get(mid)
            if m is not None:
                self._memories[mid] = MemoryRecord(
                    id=m.id,
                    workspace_id=m.workspace_id,
                    repository_id=m.repository_id,
                    user_id=m.user_id,
                    memory_type=m.memory_type,
                    scope=m.scope,
                    status=m.status,
                    content=m.content,
                    summary=m.summary,
                    source_file_path=m.source_file_path,
                    source_symbol_name=m.source_symbol_name,
                    source_commit_hash=m.source_commit_hash,
                    confidence=m.confidence,
                    tags=list(m.tags),
                    embedding=vector,
                    created_by=m.created_by,
                    created_at=m.created_at,
                    updated_at=m.updated_at,
                    accessed_at=m.accessed_at,
                    expires_at=m.expires_at,
                    deleted_at=m.deleted_at,
                )
                count += 1
        return count

    def _filter(self, rows, memory_type, status, tags):
        if memory_type is not None:
            rows = [m for m in rows if m.memory_type == memory_type]
        if status is not None:
            rows = [m for m in rows if m.status == MemoryStatus(status)]
        if tags:
            rows = [m for m in rows if all(t in m.tags for t in tags)]
        return rows


class FakeConversationContextStore:
    """In-memory ``ConversationContextStore``."""

    def __init__(self) -> None:
        self._entries: dict[tuple[UUID, UUID], list[ConversationContextEntry]] = {}

    async def get(
        self, session_id: UUID, conversation_id: UUID,
    ) -> list[ConversationContextEntry]:
        return list(self._entries.get((session_id, conversation_id), []))

    async def append(
        self,
        session_id: UUID,
        conversation_id: UUID,
        entry: ConversationContextEntry,
    ) -> None:
        key = (session_id, conversation_id)
        self._entries.setdefault(key, []).append(entry)

    async def clear(
        self, session_id: UUID, conversation_id: UUID,
    ) -> None:
        self._entries.pop((session_id, conversation_id), None)

    async def set_ttl(
        self, session_id: UUID, conversation_id: UUID, ttl_seconds: int,
    ) -> None:
        return


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


@pytest.fixture
def fake_index_files() -> FakeRepositoryFileRepository:
    return FakeRepositoryFileRepository()


@pytest.fixture
def fake_symbols() -> FakeRepositorySymbolRepository:
    return FakeRepositorySymbolRepository()


@pytest.fixture
def fake_dependencies() -> FakeRepositoryDependencyRepository:
    return FakeRepositoryDependencyRepository()


@pytest.fixture
def fake_chunks() -> FakeRepositoryChunkRepository:
    return FakeRepositoryChunkRepository()


@pytest.fixture
def fake_git() -> FakeGitClient:
    return FakeGitClient()


@pytest.fixture
def fake_memories() -> FakeMemoryRepository:
    return FakeMemoryRepository()


@pytest.fixture
def fake_conversation() -> FakeConversationContextStore:
    return FakeConversationContextStore()


# ─── Live integration infrastructure (PostgreSQL/Redis) ───────────────


PG_HOST = os.getenv("TEST_PG_HOST", "localhost")
PG_PORT = os.getenv("TEST_PG_PORT", "5432")
PG_USER = os.getenv("POSTGRES_USER", "forge")
PG_PASSWORD = os.getenv("POSTGRES_PASSWORD", "change-me-before-production")
TEST_DB = "forge_test"


def _admin_dsn() -> str:
    return f"postgresql://{PG_USER}:{PG_PASSWORD}@{PG_HOST}:{PG_PORT}/postgres"


def _test_db_url() -> str:
    return f"postgresql+asyncpg://{PG_USER}:{PG_PASSWORD}@{PG_HOST}:{PG_PORT}/{TEST_DB}"


async def _database_reachable() -> bool:
    try:
        conn = await asyncpg.connect(dsn=_admin_dsn(), timeout=2)
        await conn.close()
        return True
    except asyncpg.PostgresError:
        return False


async def _admin_execute(sql: str) -> None:
    conn = await asyncpg.connect(dsn=_admin_dsn())
    try:
        await conn.execute(sql)
    finally:
        await conn.close()


async def _create_database() -> None:
    conn = await asyncpg.connect(dsn=_admin_dsn())
    try:
        await conn.execute(f'CREATE DATABASE "{TEST_DB}"')
    finally:
        await conn.close()


async def _drop_database() -> None:
    try:
        await _admin_execute(f'DROP DATABASE IF EXISTS "{TEST_DB}" WITH (FORCE)')
    except asyncpg.PostgresError:
        pass


@pytest.fixture(scope="session")
def forge_test_database():
    """Provision a dedicated test database and run all migrations."""
    try:
        reachable = asyncio.run(_database_reachable())
    except OSError:
        reachable = False
    if not reachable:
        pytest.skip(
            "PostgreSQL is not reachable. Start it with "
            "`docker compose up -d postgres redis` before running integration tests."
        )

    asyncio.run(_drop_database())
    asyncio.run(_create_database())

    db_url = _test_db_url()
    os.environ["FORGE_DATABASE_URL"] = db_url
    os.environ["FORGE_REDIS_URL"] = os.getenv("TEST_REDIS_URL", "redis://localhost:6379/0")
    os.environ["FORGE_JWT_SECRET"] = "integration-test-secret-at-least-32-chars"
    os.environ["FORGE_INDEX_WORKER_ENABLED"] = "false"
    os.environ["FORGE_MEMORY_MAINTENANCE_WORKER_ENABLED"] = "false"

    get_settings.cache_clear()
    alembic_cfg = Config("alembic.ini")
    command.upgrade(alembic_cfg, "head")

    yield db_url

    get_settings.cache_clear()
    asyncio.run(_drop_database())


@pytest.fixture(scope="session")
def integration_client(forge_test_database) -> TestClient:
    """A fully wired application client against the real database."""
    if forge_test_database is None:
        pytest.skip("integration database unavailable")
    os.environ["FORGE_DATABASE_URL"] = forge_test_database
    get_settings.cache_clear()

    from forge_api.presentation.http.app import create_app

    app = create_app()
    with TestClient(app) as client:
        yield client


@pytest.fixture
def _reset_rate_limiter(integration_client: TestClient) -> None:
    """Clear the in-memory rate limiter between integration tests.

    The session-scoped ``integration_client`` shares one ``RateLimitMiddleware``
    instance across every integration test in every module; without a reset,
    later tests can be denied with 429 depending on execution order.

    Integration test modules opt in via ``pytestmark = usefixtures(...)`` so
    unit tests never trigger the live-database client.
    """
    mw = integration_client.app.middleware_stack
    while mw is not None:
        if isinstance(mw, RateLimitMiddleware):
            mw.hits.clear()
            return
        mw = getattr(mw, "app", None)
