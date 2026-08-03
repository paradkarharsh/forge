"""Workspace application service.

Handles workspace creation, listing, renaming, and membership
authorization checks. All persistence goes through repository ports.
"""
from uuid import UUID

from forge_api.domain.audit import AuditEventType
from forge_api.domain.auth import WorkspaceRole
from forge_api.domain.errors import AuthorizationError, NotFoundError
from forge_api.domain.repositories import WorkspaceRepository
from forge_api.domain.workspaces import WorkspaceRecord
from forge_api.infrastructure.audit import AuditLogger


class WorkspaceService:
    """Orchestrates workspace operations behind clean domain boundaries."""

    _RENAME_ROLES = frozenset({WorkspaceRole.OWNER, WorkspaceRole.ADMIN})

    def __init__(
        self,
        *,
        workspaces: WorkspaceRepository,
        audit: AuditLogger,
    ) -> None:
        self._workspaces = workspaces
        self._audit = audit

    async def list_workspaces(
        self, user_id: UUID
    ) -> list[tuple[WorkspaceRecord, WorkspaceRole]]:
        return await self._workspaces.list_for_user(user_id)

    async def create_workspace(
        self,
        *,
        name: str,
        owner_id: UUID,
        ip_address: str | None,
        user_agent: str | None,
    ) -> tuple[WorkspaceRecord, WorkspaceRole]:
        workspace = await self._workspaces.create(name=name.strip())
        await self._workspaces.add_member(
            workspace_id=workspace.id,
            user_id=owner_id,
            role=WorkspaceRole.OWNER,
        )
        self._audit.log(
            AuditEventType.WORKSPACE_CREATED,
            user_id=owner_id,
            ip_address=ip_address,
            user_agent=user_agent,
            payload={"workspace_id": str(workspace.id)},
        )
        return workspace, WorkspaceRole.OWNER

    async def rename_workspace(
        self,
        *,
        workspace_id: UUID,
        user_id: UUID,
        name: str,
        ip_address: str | None,
        user_agent: str | None,
    ) -> WorkspaceRecord:
        member = await self._workspaces.get_membership(workspace_id, user_id)
        if not member or member.role not in self._RENAME_ROLES:
            raise AuthorizationError("Insufficient workspace role")

        workspace = await self._workspaces.rename(workspace_id, name.strip())
        if not workspace:
            raise NotFoundError("Workspace not found")

        self._audit.log(
            AuditEventType.WORKSPACE_RENAMED,
            user_id=user_id,
            ip_address=ip_address,
            user_agent=user_agent,
            payload={"workspace_id": str(workspace_id), "new_name": name.strip()},
        )
        return workspace
