"""Repository ports.

Domain services depend on these interfaces; infrastructure adapters
implement them with concrete persistence engines (currently SQLAlchemy).
"""
from datetime import datetime
from typing import Protocol
from uuid import UUID

from forge_api.domain.auth import WorkspaceRole
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

    async def get_membership(
        self, workspace_id: UUID, user_id: UUID
    ) -> MembershipRecord | None: ...

    async def create(self, *, name: str) -> WorkspaceRecord: ...

    async def add_member(
        self, *, workspace_id: UUID, user_id: UUID, role: WorkspaceRole
    ) -> None: ...

    async def rename(self, workspace_id: UUID, name: str) -> WorkspaceRecord | None: ...
