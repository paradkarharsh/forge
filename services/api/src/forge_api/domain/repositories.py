"""Repository ports.

Domain services depend on these interfaces; infrastructure adapters
implement them with concrete persistence engines (currently SQLAlchemy).
"""
from datetime import datetime
from typing import Protocol
from uuid import UUID

from forge_api.domain.auth import WorkspaceRole
from forge_api.domain.repository import (
    BranchRecord,
    RepositoryEventRecord,
    RepositoryRecord,
    SyncJobRecord,
)
from forge_api.domain.sessions import SessionRecord
from forge_api.domain.users import OAuthIdentityRecord, UserRecord
from forge_api.domain.workspaces import MembershipRecord, WorkspaceRecord


class SessionRepository(Protocol):
    async def get(
        self, session_id: UUID, *, user_id: UUID | None = None
    ) -> SessionRecord | None: ...

    async def find_by_refresh_hash(self, refresh_hash: str) -> SessionRecord | None: ...

    async def list_active(self, user_id: UUID) -> list[SessionRecord]: ...

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
    ) -> SessionRecord: ...

    async def rotate(self, session_id: UUID, at: datetime) -> bool: ...

    async def revoke(self, session_id: UUID, user_id: UUID, at: datetime) -> bool: ...

    async def revoke_family(self, family_id: UUID, at: datetime) -> int: ...

    async def revoke_all(self, user_id: UUID, at: datetime) -> int: ...

    async def touch(self, session_id: UUID, at: datetime, *, stale_before: datetime) -> bool: ...

    async def cleanup_expired(self, now: datetime) -> int: ...


class UserRepository(Protocol):
    async def find_by_email(self, email: str) -> UserRecord | None: ...

    async def find_by_id(self, user_id: UUID) -> UserRecord | None: ...

    async def create(self, *, email: str, password_hash: str | None) -> UserRecord: ...


class OAuthIdentityRepository(Protocol):
    async def find(self, provider: str, subject: str) -> OAuthIdentityRecord | None: ...

    async def create(
        self, *, user_id: UUID, provider: str, subject: str
    ) -> OAuthIdentityRecord: ...


class WorkspaceRepository(Protocol):
    async def list_for_user(self, user_id: UUID) -> list[tuple[WorkspaceRecord, WorkspaceRole]]: ...

    async def get(self, workspace_id: UUID) -> WorkspaceRecord | None: ...

    async def get_by_slug(self, slug: str) -> WorkspaceRecord | None: ...

    async def get_membership(
        self, workspace_id: UUID, user_id: UUID
    ) -> MembershipRecord | None: ...

    async def list_members(self, workspace_id: UUID) -> list[MembershipRecord]: ...

    async def create(
        self, *, name: str, slug: str, description: str | None = None
    ) -> WorkspaceRecord: ...

    async def add_member(
        self, *, workspace_id: UUID, user_id: UUID, role: WorkspaceRole
    ) -> None: ...

    async def remove_member(self, workspace_id: UUID, user_id: UUID) -> bool: ...

    async def update_member_role(
        self, workspace_id: UUID, user_id: UUID, role: WorkspaceRole
    ) -> bool: ...

    async def rename(self, workspace_id: UUID, name: str) -> WorkspaceRecord | None: ...

    async def update(
        self,
        workspace_id: UUID,
        *,
        name: str | None = None,
        slug: str | None = None,
        description: str | None = ...,
    ) -> WorkspaceRecord | None: ...

    async def soft_delete(self, workspace_id: UUID) -> bool: ...


class RepositoryRepository(Protocol):
    async def get(self, repository_id: UUID) -> RepositoryRecord | None: ...

    async def get_by_workspace(
        self,
        workspace_id: UUID,
        *,
        include_archived: bool = False,
        include_deleted: bool = False,
    ) -> list[RepositoryRecord]: ...

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
    ) -> RepositoryRecord: ...

    async def update(
        self,
        repository_id: UUID,
        *,
        name: str | None = None,
        description: str | None = ...,
        default_branch: str | None = ...,
        current_branch: str | None = ...,
        clone_status: str | None = None,
        sync_status: str | None = None,
        visibility: str | None = None,
        local_path: str | None = ...,
        size_bytes: int | None = ...,
        last_commit_hash: str | None = ...,
        last_synced_at: datetime | None = ...,
    ) -> RepositoryRecord | None: ...

    async def soft_delete(self, repository_id: UUID) -> bool: ...

    async def archive(self, repository_id: UUID) -> bool: ...

    async def restore(self, repository_id: UUID) -> RepositoryRecord | None: ...


class RepositoryBranchRepository(Protocol):
    async def list_by_repository(self, repository_id: UUID) -> list[BranchRecord]: ...

    async def upsert(
        self,
        *,
        repository_id: UUID,
        name: str,
        commit_hash: str | None = None,
        is_default: bool = False,
        is_protected: bool = False,
    ) -> BranchRecord: ...

    async def delete_by_repository(self, repository_id: UUID) -> int: ...


class RepositorySyncJobRepository(Protocol):
    async def get(self, job_id: UUID) -> SyncJobRecord | None: ...

    async def list_by_repository(
        self, repository_id: UUID, *, job_type: str | None = None
    ) -> list[SyncJobRecord]: ...

    async def create(
        self,
        *,
        repository_id: UUID,
        job_type: str,
        status: str = "pending",
    ) -> SyncJobRecord: ...

    async def update_status(
        self,
        job_id: UUID,
        *,
        status: str,
        error_message: str | None = None,
    ) -> SyncJobRecord | None: ...


class RepositoryEventRepository(Protocol):
    async def list_by_repository(
        self, repository_id: UUID, *, limit: int = 50
    ) -> list[RepositoryEventRecord]: ...

    async def create(
        self,
        *,
        repository_id: UUID,
        event_type: str,
        actor_id: UUID | None = None,
        payload: dict | None = None,
    ) -> RepositoryEventRecord: ...
