"""Workspace application service.

Handles workspace creation, listing, get, update, delete, and membership
management with role-based authorization checks. All persistence goes
through repository ports.
"""
import re
from uuid import UUID

from forge_api.domain.audit import AuditEventType
from forge_api.domain.auth import WorkspaceRole
from forge_api.domain.errors import (
    AuthorizationError,
    ConflictError,
    DomainError,
    NotFoundError,
)
from forge_api.domain.repositories import WorkspaceRepository
from forge_api.domain.workspaces import MembershipRecord, WorkspaceRecord
from forge_api.infrastructure.audit import AuditLogger

_SLUG_RE = re.compile(r"^[a-z0-9][a-z0-9-]{0,138}[a-z0-9]$")
_MANAGE_ROLES = frozenset({WorkspaceRole.OWNER, WorkspaceRole.ADMIN})
_RENAME_ROLES = _MANAGE_ROLES


def slugify(name: str) -> str:
    """Generate a URL-safe slug from a workspace name."""
    slug = re.sub(r"[^a-z0-9]+", "-", name.lower().strip()).strip("-")
    return slug[:140] if slug else "workspace"


class WorkspaceService:
    """Orchestrates workspace operations behind clean domain boundaries."""

    def __init__(
        self,
        *,
        workspaces: WorkspaceRepository,
        audit: AuditLogger,
    ) -> None:
        self._workspaces = workspaces
        self._audit = audit

    # ─── Queries ───────────────────────────────────────────────────

    async def list_workspaces(
        self, user_id: UUID
    ) -> list[tuple[WorkspaceRecord, WorkspaceRole]]:
        return await self._workspaces.list_for_user(user_id)

    async def get_workspace(self, workspace_id: UUID) -> WorkspaceRecord:
        workspace = await self._workspaces.get(workspace_id)
        if not workspace:
            raise NotFoundError("Workspace not found")
        return workspace

    async def get_workspace_by_slug(self, slug: str) -> WorkspaceRecord:
        workspace = await self._workspaces.get_by_slug(slug)
        if not workspace:
            raise NotFoundError("Workspace not found")
        return workspace

    async def list_members(
        self, workspace_id: UUID, user_id: UUID
    ) -> list[MembershipRecord]:
        """List members of a workspace. Caller must be a member."""
        member = await self._workspaces.get_membership(workspace_id, user_id)
        if not member:
            raise AuthorizationError("Not a member of this workspace")
        return await self._workspaces.list_members(workspace_id)

    # ─── Commands ──────────────────────────────────────────────────

    async def create_workspace(
        self,
        *,
        name: str,
        owner_id: UUID,
        slug: str | None = None,
        description: str | None = None,
        ip_address: str | None,
        user_agent: str | None,
    ) -> tuple[WorkspaceRecord, WorkspaceRole]:
        final_slug = (slug or slugify(name)).lower()
        if not _SLUG_RE.match(final_slug):
            raise DomainError(
                "Slug must be 2-140 characters: lowercase letters, digits, and hyphens",
                code="invalid_slug",
            )

        # Ensure slug uniqueness.
        existing = await self._workspaces.get_by_slug(final_slug)
        if existing:
            raise ConflictError("Workspace slug already taken", code="slug_taken")

        workspace = await self._workspaces.create(
            name=name.strip(), slug=final_slug, description=description
        )
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
            payload={
                "workspace_id": str(workspace.id),
                "slug": final_slug,
            },
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
        if not member or member.role not in _RENAME_ROLES:
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

    async def update_workspace(
        self,
        *,
        workspace_id: UUID,
        user_id: UUID,
        name: str | None = None,
        slug: str | None = None,
        description: str | None = ...,
        ip_address: str | None,
        user_agent: str | None,
    ) -> WorkspaceRecord:
        """Update workspace metadata. Requires OWNER or ADMIN role."""
        member = await self._workspaces.get_membership(workspace_id, user_id)
        if not member or member.role not in _MANAGE_ROLES:
            raise AuthorizationError("Insufficient workspace role")

        if slug is not None:
            slug = slug.lower()
            if not _SLUG_RE.match(slug):
                raise DomainError(
                    "Slug must be 2-140 characters: lowercase letters, digits, and hyphens",
                    code="invalid_slug",
                )
            existing = await self._workspaces.get_by_slug(slug)
            if existing and existing.id != workspace_id:
                raise ConflictError("Workspace slug already taken", code="slug_taken")

        workspace = await self._workspaces.update(
            workspace_id,
            name=name.strip() if name else None,
            slug=slug,
            description=description,
        )
        if not workspace:
            raise NotFoundError("Workspace not found")

        self._audit.log(
            AuditEventType.WORKSPACE_UPDATED,
            user_id=user_id,
            ip_address=ip_address,
            user_agent=user_agent,
            payload={"workspace_id": str(workspace_id)},
        )
        return workspace

    async def delete_workspace(
        self,
        *,
        workspace_id: UUID,
        user_id: UUID,
        ip_address: str | None,
        user_agent: str | None,
    ) -> None:
        """Soft-delete a workspace. Only the OWNER may delete."""
        member = await self._workspaces.get_membership(workspace_id, user_id)
        if not member or member.role != WorkspaceRole.OWNER:
            raise AuthorizationError("Only the workspace owner can delete it")

        deleted = await self._workspaces.soft_delete(workspace_id)
        if not deleted:
            raise NotFoundError("Workspace not found")

        self._audit.log(
            AuditEventType.WORKSPACE_DELETED,
            user_id=user_id,
            ip_address=ip_address,
            user_agent=user_agent,
            payload={"workspace_id": str(workspace_id)},
        )

    # ─── Membership management ─────────────────────────────────────

    async def add_member(
        self,
        *,
        workspace_id: UUID,
        actor_id: UUID,
        target_user_id: UUID,
        role: WorkspaceRole,
        ip_address: str | None,
        user_agent: str | None,
    ) -> None:
        """Add a member to a workspace. Actor must be OWNER or ADMIN."""
        actor = await self._workspaces.get_membership(workspace_id, actor_id)
        if not actor or actor.role not in _MANAGE_ROLES:
            raise AuthorizationError("Insufficient workspace role")

        if role == WorkspaceRole.OWNER:
            raise DomainError(
                "Cannot add a member as owner; transfer ownership instead",
                code="invalid_role_assignment",
            )

        existing = await self._workspaces.get_membership(workspace_id, target_user_id)
        if existing:
            raise ConflictError("User is already a member", code="already_member")

        await self._workspaces.add_member(
            workspace_id=workspace_id,
            user_id=target_user_id,
            role=role,
        )
        self._audit.log(
            AuditEventType.WORKSPACE_MEMBER_ADDED,
            user_id=actor_id,
            ip_address=ip_address,
            user_agent=user_agent,
            payload={
                "workspace_id": str(workspace_id),
                "target_user_id": str(target_user_id),
                "role": role.value,
            },
        )

    async def remove_member(
        self,
        *,
        workspace_id: UUID,
        actor_id: UUID,
        target_user_id: UUID,
        ip_address: str | None,
        user_agent: str | None,
    ) -> None:
        """Remove a member from a workspace. Actor must be OWNER or ADMIN."""
        actor = await self._workspaces.get_membership(workspace_id, actor_id)
        if not actor or actor.role not in _MANAGE_ROLES:
            raise AuthorizationError("Insufficient workspace role")

        target = await self._workspaces.get_membership(workspace_id, target_user_id)
        if not target:
            raise NotFoundError("Member not found")

        if target.role == WorkspaceRole.OWNER:
            raise DomainError(
                "Cannot remove the workspace owner",
                code="cannot_remove_owner",
            )

        removed = await self._workspaces.remove_member(workspace_id, target_user_id)
        if not removed:
            raise NotFoundError("Member not found")

        self._audit.log(
            AuditEventType.WORKSPACE_MEMBER_REMOVED,
            user_id=actor_id,
            ip_address=ip_address,
            user_agent=user_agent,
            payload={
                "workspace_id": str(workspace_id),
                "target_user_id": str(target_user_id),
            },
        )

    async def change_member_role(
        self,
        *,
        workspace_id: UUID,
        actor_id: UUID,
        target_user_id: UUID,
        role: WorkspaceRole,
        ip_address: str | None,
        user_agent: str | None,
    ) -> None:
        """Change a member's role. Actor must be OWNER or ADMIN."""
        actor = await self._workspaces.get_membership(workspace_id, actor_id)
        if not actor or actor.role not in _MANAGE_ROLES:
            raise AuthorizationError("Insufficient workspace role")

        if role == WorkspaceRole.OWNER:
            raise DomainError(
                "Cannot assign owner role; transfer ownership instead",
                code="invalid_role_assignment",
            )

        target = await self._workspaces.get_membership(workspace_id, target_user_id)
        if not target:
            raise NotFoundError("Member not found")

        if target.role == WorkspaceRole.OWNER:
            raise DomainError(
                "Cannot change the owner's role",
                code="cannot_change_owner_role",
            )

        updated = await self._workspaces.update_member_role(
            workspace_id, target_user_id, role
        )
        if not updated:
            raise NotFoundError("Member not found")

        self._audit.log(
            AuditEventType.WORKSPACE_MEMBER_ROLE_CHANGED,
            user_id=actor_id,
            ip_address=ip_address,
            user_agent=user_agent,
            payload={
                "workspace_id": str(workspace_id),
                "target_user_id": str(target_user_id),
                "new_role": role.value,
            },
        )
