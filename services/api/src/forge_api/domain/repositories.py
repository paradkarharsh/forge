"""Repository ports.

Domain services depend on these interfaces; infrastructure adapters
implement them with concrete persistence engines (currently SQLAlchemy).
"""
from datetime import datetime
from typing import Protocol
from uuid import UUID

from forge_api.domain.auth import WorkspaceRole
from forge_api.domain.conversation import (
    ConversationRecord,
    MessageRecord,
    UsageEventRecord,
)
from forge_api.domain.indexing import (
    ChunkRecord,
    DependencyRecord,
    FileRecord,
    SymbolRecord,
)
from forge_api.domain.memory import (
    ConversationContextEntry,
    MemoryRecord,
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


class MemoryRepository(Protocol):
    """Durable memory store port.

    Every query enforces workspace isolation, and user-scoped queries
    additionally enforce user ownership at the adapter level so isolation
    never depends on the HTTP layer alone.
    """

    async def get(self, memory_id: UUID) -> MemoryRecord | None: ...

    async def list_by_workspace(
        self,
        workspace_id: UUID,
        *,
        memory_type: str | None = None,
        status: str | None = None,
        tags: list[str] | None = None,
        limit: int = 50,
    ) -> list[MemoryRecord]: ...

    async def list_by_repository(
        self,
        repository_id: UUID,
        *,
        memory_type: str | None = None,
        status: str | None = None,
        tags: list[str] | None = None,
        limit: int = 50,
    ) -> list[MemoryRecord]: ...

    async def list_by_user(
        self,
        workspace_id: UUID,
        user_id: UUID,
        *,
        memory_type: str | None = None,
        status: str | None = None,
        tags: list[str] | None = None,
        limit: int = 50,
    ) -> list[MemoryRecord]: ...

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
    ) -> MemoryRecord: ...

    async def update(
        self,
        memory_id: UUID,
        *,
        content: str | None = None,
        summary: str | None = ...,
        status: str | None = None,
        confidence: float | None = None,
        tags: list[str] | None = None,
        embedding: list[float] | None = ...,
        expires_at: datetime | None = ...,
    ) -> MemoryRecord | None: ...

    async def soft_delete(self, memory_id: UUID) -> bool: ...

    async def search_semantic(
        self,
        workspace_id: UUID,
        query_embedding: list[float],
        *,
        repository_id: UUID | None = None,
        user_id: UUID | None = None,
        limit: int = 20,
    ) -> list[MemoryRecord]: ...

    async def search_by_tags(
        self,
        workspace_id: UUID,
        tags: list[str],
        *,
        repository_id: UUID | None = None,
        limit: int = 50,
    ) -> list[MemoryRecord]: ...

    async def mark_stale(
        self, repository_id: UUID, paths: list[str],
    ) -> int: ...

    async def delete_by_repository(self, repository_id: UUID) -> int: ...

    async def touch_accessed(self, memory_ids: list[UUID]) -> None: ...

    async def find_expired(
        self, now: datetime, *, limit: int = 100,
    ) -> list[MemoryRecord]: ...

    async def find_missing_embeddings(
        self, *, limit: int = 100,
    ) -> list[MemoryRecord]: ...

    async def hard_delete_old(self, older_than: datetime) -> int: ...

    async def bulk_update_status(
        self, memory_ids: list[UUID], status: str,
    ) -> int: ...

    async def bulk_update_embeddings(
        self, updates: list[tuple[UUID, list[float]]],
    ) -> int: ...


class ConversationContextStore(Protocol):
    """Ephemeral conversation context port (Redis-backed)."""

    async def get(
        self, session_id: UUID, conversation_id: UUID,
    ) -> list[ConversationContextEntry]: ...

    async def append(
        self,
        session_id: UUID,
        conversation_id: UUID,
        entry: ConversationContextEntry,
    ) -> None: ...

    async def clear(
        self, session_id: UUID, conversation_id: UUID,
    ) -> None: ...

    async def set_ttl(
        self, session_id: UUID, conversation_id: UUID, ttl_seconds: int,
    ) -> None: ...


# ─── Conversation history (persistent, PostgreSQL) ────────────────────


class ConversationRepository(Protocol):
    """Durable conversation store port."""

    async def get(self, conversation_id: UUID) -> ConversationRecord | None: ...

    async def list_by_workspace(
        self,
        workspace_id: UUID,
        user_id: UUID,
        *,
        limit: int = 50,
        offset: int = 0,
        include_deleted: bool = False,
    ) -> list[ConversationRecord]: ...

    async def count_by_workspace(
        self,
        workspace_id: UUID,
        user_id: UUID,
        *,
        include_deleted: bool = False,
    ) -> int: ...

    async def create(
        self,
        *,
        workspace_id: UUID,
        user_id: UUID,
        title: str | None = None,
        repository_id: UUID | None = None,
    ) -> ConversationRecord: ...

    async def update_title(
        self, conversation_id: UUID, title: str,
    ) -> ConversationRecord | None: ...

    async def increment_message_count(
        self, conversation_id: UUID,
    ) -> bool: ...

    async def soft_delete(self, conversation_id: UUID) -> bool: ...


class MessageRepository(Protocol):
    """Durable message store port."""

    async def get(self, message_id: UUID) -> MessageRecord | None: ...

    async def list_by_conversation(
        self,
        conversation_id: UUID,
        *,
        limit: int = 50,
        offset: int = 0,
    ) -> list[MessageRecord]: ...

    async def count_by_conversation(
        self, conversation_id: UUID,
    ) -> int: ...

    async def create(
        self,
        *,
        conversation_id: UUID,
        role: str,
        content: str,
        provider: str | None = None,
        model: str | None = None,
        prompt_version: str | None = None,
        input_tokens: int | None = None,
        output_tokens: int | None = None,
        total_tokens: int | None = None,
        duration_ms: float | None = None,
        finish_reason: str | None = None,
        status: str = "complete",
        metadata: dict | None = None,
    ) -> MessageRecord: ...

    async def update(
        self,
        message_id: UUID,
        *,
        content: str | None = None,
        input_tokens: int | None = None,
        output_tokens: int | None = None,
        total_tokens: int | None = None,
        duration_ms: float | None = None,
        finish_reason: str | None = None,
        status: str | None = None,
        metadata: dict | None = None,
    ) -> MessageRecord | None: ...


class UsageEventRepository(Protocol):
    """Usage event store port."""

    async def create(
        self,
        *,
        workspace_id: UUID,
        user_id: UUID,
        conversation_id: UUID | None = None,
        message_id: UUID | None = None,
        provider: str,
        model: str,
        input_tokens: int,
        output_tokens: int,
        total_tokens: int,
        duration_ms: float,
        estimated_cost: float,
        metadata: dict | None = None,
    ) -> UsageEventRecord: ...

    async def list_by_workspace(
        self,
        workspace_id: UUID,
        *,
        user_id: UUID | None = None,
        start: datetime | None = None,
        end: datetime | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[UsageEventRecord]: ...

    async def aggregate_by_workspace(
        self,
        workspace_id: UUID,
        *,
        user_id: UUID | None = None,
        start: datetime | None = None,
        end: datetime | None = None,
    ) -> dict: ...
