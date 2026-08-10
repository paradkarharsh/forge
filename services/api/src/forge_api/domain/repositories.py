"""Repository ports.

Domain services depend on these interfaces; infrastructure adapters
implement them with concrete persistence engines (currently SQLAlchemy).
"""
from datetime import datetime
from typing import Protocol
from uuid import UUID

from forge_api.domain.auth import WorkspaceRole
from forge_api.domain.indexing import (
    ChunkRecord,
    DependencyRecord,
    FileRecord,
    SymbolRecord,
)
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
        index_status: str | None = None,
        indexed_at: datetime | None = ...,
        file_count: int | None = ...,
        symbol_count: int | None = ...,
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

    async def find_pending_by_type(self, job_type: str) -> SyncJobRecord | None: ...


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


class RepositoryFileRepository(Protocol):
    async def get(self, file_id: UUID) -> FileRecord | None: ...

    async def get_by_path(
        self, repository_id: UUID, path: str
    ) -> FileRecord | None: ...

    async def list_by_repository(
        self, repository_id: UUID, *, language: str | None = None
    ) -> list[FileRecord]: ...

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
    ) -> FileRecord: ...

    async def delete_by_repository(self, repository_id: UUID) -> int: ...

    async def delete_by_paths(self, repository_id: UUID, paths: list[str]) -> int: ...


class RepositorySymbolRepository(Protocol):
    async def list_by_file(self, file_id: UUID) -> list[SymbolRecord]: ...

    async def list_by_repository(
        self, repository_id: UUID, *, kind: str | None = None
    ) -> list[SymbolRecord]: ...

    async def search_by_name(
        self,
        repository_id: UUID,
        query: str,
        *,
        kind: str | None = None,
        limit: int = 50,
    ) -> list[SymbolRecord]: ...

    async def bulk_create(self, symbols: list[SymbolRecord]) -> None: ...

    async def delete_by_file(self, file_id: UUID) -> int: ...

    async def delete_by_repository(self, repository_id: UUID) -> int: ...


class RepositoryDependencyRepository(Protocol):
    async def list_by_file(self, source_file_id: UUID) -> list[DependencyRecord]: ...

    async def list_dependents(self, target_file_id: UUID) -> list[DependencyRecord]: ...

    async def bulk_create(self, dependencies: list[DependencyRecord]) -> None: ...

    async def delete_by_file(self, source_file_id: UUID) -> int: ...

    async def delete_by_repository(self, repository_id: UUID) -> int: ...


class RepositoryChunkRepository(Protocol):
    async def list_by_file(self, file_id: UUID) -> list[ChunkRecord]: ...

    async def search_semantic(
        self,
        repository_id: UUID,
        query_embedding: list[float],
        *,
        limit: int = 20,
    ) -> list[ChunkRecord]: ...

    async def bulk_create(self, chunks: list[ChunkRecord]) -> None: ...

    async def delete_by_file(self, file_id: UUID) -> int: ...

    async def delete_by_repository(self, repository_id: UUID) -> int: ...
