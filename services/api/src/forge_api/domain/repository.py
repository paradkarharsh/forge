"""Repository domain records and value objects.

Persistence-neutral dataclasses representing repositories, branches,
sync jobs, and repository events within a workspace.
"""
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from uuid import UUID

from forge_api.domain.indexing import IndexStatus


class RepositoryProvider(StrEnum):
    GITHUB = "github"
    GITLAB = "gitlab"
    BITBUCKET = "bitbucket"
    LOCAL = "local"


class RepositoryVisibility(StrEnum):
    PUBLIC = "public"
    PRIVATE = "private"
    INTERNAL = "internal"


class CloneStatus(StrEnum):
    PENDING = "pending"
    CLONING = "cloning"
    READY = "ready"
    FAILED = "failed"


class SyncStatus(StrEnum):
    IDLE = "idle"
    SYNCING = "syncing"
    FAILED = "failed"


class SyncJobStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class SyncJobType(StrEnum):
    CLONE = "clone"
    SYNC = "sync"
    INDEX = "index"
    AGENT_EXECUTE = "agent_execute"
    AGENT_RESUME = "agent_resume"



@dataclass(frozen=True, slots=True)
class RepositoryRecord:
    id: UUID
    workspace_id: UUID
    name: str
    owner: str
    provider: RepositoryProvider
    remote_url: str | None
    local_path: str | None
    default_branch: str | None
    current_branch: str | None
    clone_status: CloneStatus
    sync_status: SyncStatus
    visibility: RepositoryVisibility
    description: str | None
    size_bytes: int | None
    last_commit_hash: str | None
    last_synced_at: datetime | None
    created_at: datetime
    updated_at: datetime
    archived_at: datetime | None
    deleted_at: datetime | None
    index_status: IndexStatus = IndexStatus.PENDING
    indexed_at: datetime | None = None
    file_count: int | None = None
    symbol_count: int | None = None


@dataclass(frozen=True, slots=True)
class BranchRecord:
    id: UUID
    repository_id: UUID
    name: str
    commit_hash: str | None
    is_default: bool
    is_protected: bool
    created_at: datetime


@dataclass(frozen=True, slots=True)
class SyncJobRecord:
    id: UUID
    repository_id: UUID
    job_type: SyncJobType
    status: SyncJobStatus
    started_at: datetime | None
    completed_at: datetime | None
    error_message: str | None
    created_at: datetime


@dataclass(frozen=True, slots=True)
class RepositoryEventRecord:
    id: UUID
    repository_id: UUID
    event_type: str
    actor_id: UUID | None
    payload: dict | None
    created_at: datetime
