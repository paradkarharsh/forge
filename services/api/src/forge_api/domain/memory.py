"""Context and memory engine domain model.

Persistence-neutral records, enums, and ports for the durable memory
store and ephemeral conversation context.  The memory layer sits between
Repository Intelligence and the future LLM/Agent layer: it stores
project decisions, conventions, facts, user preferences, summaries, and
annotations while *referencing* (never duplicating) the repository
intelligence data produced by FP5.
"""
from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from typing import Protocol
from uuid import UUID

# ─── Enums ────────────────────────────────────────────────────────────


class MemoryType(StrEnum):
    DECISION = "decision"
    CONVENTION = "convention"
    FACT = "fact"
    PREFERENCE = "preference"
    SUMMARY = "summary"
    ANNOTATION = "annotation"


class MemoryScope(StrEnum):
    WORKSPACE = "workspace"
    REPOSITORY = "repository"
    USER = "user"


class MemoryStatus(StrEnum):
    ACTIVE = "active"
    STALE = "stale"
    ARCHIVED = "archived"


class ContextSource(StrEnum):
    MEMORY = "memory"
    REPOSITORY_CHUNK = "repository_chunk"
    REPOSITORY_SYMBOL = "repository_symbol"
    REPOSITORY_FILE = "repository_file"
    REPOSITORY_DEPENDENCY = "repository_dependency"
    CONVERSATION = "conversation"


# ─── Records ──────────────────────────────────────────────────────────


@dataclass(frozen=True, slots=True)
class MemoryRecord:
    """A single durable memory entry."""

    id: UUID
    workspace_id: UUID
    repository_id: UUID | None
    user_id: UUID | None
    memory_type: MemoryType
    scope: MemoryScope
    status: MemoryStatus
    content: str
    summary: str | None
    source_file_path: str | None
    source_symbol_name: str | None
    source_commit_hash: str | None
    confidence: float
    tags: list[str]
    embedding: list[float] | None
    created_by: UUID | None
    created_at: datetime
    updated_at: datetime
    accessed_at: datetime | None
    expires_at: datetime | None
    deleted_at: datetime | None


@dataclass(frozen=True, slots=True)
class ConversationContextEntry:
    """One entry in an ephemeral conversation context (Redis-backed)."""

    role: str  # "user" | "assistant" | "system" | "context"
    content: str
    timestamp: datetime
    source_ids: list[str] = field(default_factory=list)


# ─── Context model ───────────────────────────────────────────────────


@dataclass(frozen=True, slots=True)
class ContextEntry:
    """One unit of context in an assembled context window."""

    source: ContextSource
    scope: MemoryScope
    content: str
    relevance_score: float
    source_id: UUID | None
    file_path: str | None
    metadata: dict


@dataclass(frozen=True, slots=True)
class ContextWindow:
    """Assembled context ready for a future LLM consumer."""

    entries: tuple[ContextEntry, ...]
    total_tokens: int
    truncated: bool
    repository_id: UUID | None
    workspace_id: UUID
    assembled_at: datetime


@dataclass(frozen=True, slots=True)
class ContextRankingConfig:
    """Configurable ranking weights for context assembly."""

    semantic_weight: float = 0.40
    recency_weight: float = 0.20
    confidence_weight: float = 0.15
    scope_weight: float = 0.15
    type_weight: float = 0.10


# ─── Repository ports ────────────────────────────────────────────────


class MemoryRepository(Protocol):
    """Durable memory store port."""

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

    async def find_expired(self, now: datetime, *, limit: int = 100) -> list[MemoryRecord]: ...

    async def find_missing_embeddings(self, *, limit: int = 100) -> list[MemoryRecord]: ...

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
