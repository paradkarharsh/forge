"""Persistence-neutral workspace and membership records."""
from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from forge_api.domain.auth import WorkspaceRole


@dataclass(frozen=True, slots=True)
class WorkspaceRecord:
    id: UUID
    name: str
    slug: str
    created_at: datetime
    deleted_at: datetime | None
    description: str | None = None


@dataclass(frozen=True, slots=True)
class MembershipRecord:
    workspace_id: UUID
    user_id: UUID
    role: WorkspaceRole
    created_at: datetime
