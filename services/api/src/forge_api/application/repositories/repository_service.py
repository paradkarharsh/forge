"""Repository application service.

Handles repository CRUD, archive, restore, and soft delete with workspace
RBAC and audit logging. All persistence goes through repository ports.
"""
from uuid import UUID

from forge_api.domain.audit import AuditEventType
from forge_api.domain.auth import WorkspaceRole
from forge_api.domain.errors import (
    AuthorizationError,
    DomainError,
    NotFoundError,
)
from forge_api.domain.repositories import (
    RepositoryEventRepository,
    RepositoryRepository,
    WorkspaceRepository,
)
from forge_api.domain.repository import RepositoryRecord
from forge_api.infrastructure.audit import AuditLogger

_MANAGE_ROLES = frozenset({WorkspaceRole.OWNER, WorkspaceRole.ADMIN})
_CREATE_ROLES = frozenset(
    {WorkspaceRole.OWNER, WorkspaceRole.ADMIN, WorkspaceRole.MAINTAINER}
)


class RepositoryService:
    """Orchestrates repository operations behind clean domain boundaries."""

    def __init__(
        self,
        *,
        repositories: RepositoryRepository,
        workspaces: WorkspaceRepository,
        events: RepositoryEventRepository,
        audit: AuditLogger,
    ) -> None:
        self._repos = repositories
        self._workspaces = workspaces
        self._events = events
        self._audit = audit

    # ─── Authorization helpers ──────────────────────────────────────

    async def _require_membership(
        self,
        workspace_id: UUID,
        user_id: UUID,
        *,
        roles: frozenset[WorkspaceRole] | None = None,
    ) -> WorkspaceRole:
        member = await self._workspaces.get_membership(workspace_id, user_id)
        if not member:
            raise AuthorizationError("Not a member of this workspace")
        if roles and member.role not in roles:
            raise AuthorizationError("Insufficient workspace role")
        return member.role

    # ─── Queries ────────────────────────────────────────────────────

    async def list_repositories(
        self,
        workspace_id: UUID,
        user_id: UUID,
        *,
        include_archived: bool = False,
    ) -> list[RepositoryRecord]:
        await self._require_membership(workspace_id, user_id)
        return await self._repos.get_by_workspace(
            workspace_id, include_archived=include_archived
        )

    async def get_repository(
        self, repository_id: UUID, user_id: UUID
    ) -> RepositoryRecord:
        repo = await self._repos.get(repository_id)
        if not repo:
            raise NotFoundError("Repository not found")
        await self._require_membership(repo.workspace_id, user_id)
        return repo

    # ─── Commands ───────────────────────────────────────────────────

    async def create_repository(
        self,
        *,
        workspace_id: UUID,
        user_id: UUID,
        name: str,
        owner: str,
        provider: str,
        remote_url: str | None = None,
        local_path: str | None = None,
        default_branch: str | None = None,
        visibility: str = "private",
        description: str | None = None,
        ip_address: str | None,
        user_agent: str | None,
    ) -> RepositoryRecord:
        await self._require_membership(workspace_id, user_id, roles=_CREATE_ROLES)

        repo = await self._repos.create(
            workspace_id=workspace_id,
            name=name.strip(),
            owner=owner.strip(),
            provider=provider,
            remote_url=remote_url,
            local_path=local_path,
            default_branch=default_branch,
            visibility=visibility,
            description=description,
        )
        self._audit.log(
            AuditEventType.REPOSITORY_CREATED,
            user_id=user_id,
            ip_address=ip_address,
            user_agent=user_agent,
            payload={
                "repository_id": str(repo.id),
                "workspace_id": str(workspace_id),
                "provider": provider,
            },
        )
        await self._events.create(
            repository_id=repo.id,
            event_type=AuditEventType.REPOSITORY_CREATED.value,
            actor_id=user_id,
            payload={"provider": provider},
        )
        return repo

    async def update_repository(
        self,
        *,
        repository_id: UUID,
        user_id: UUID,
        name: str | None = None,
        description: str | None = ...,
        visibility: str | None = None,
        ip_address: str | None,
        user_agent: str | None,
    ) -> RepositoryRecord:
        repo = await self._repos.get(repository_id)
        if not repo:
            raise NotFoundError("Repository not found")
        await self._require_membership(repo.workspace_id, user_id, roles=_CREATE_ROLES)

        kwargs = {}
        if name is not None:
            kwargs["name"] = name.strip()
        if description is not ...:
            kwargs["description"] = description
        if visibility is not None:
            kwargs["visibility"] = visibility

        updated = await self._repos.update(repository_id, **kwargs)
        if not updated:
            raise NotFoundError("Repository not found")

        self._audit.log(
            AuditEventType.REPOSITORY_UPDATED,
            user_id=user_id,
            ip_address=ip_address,
            user_agent=user_agent,
            payload={"repository_id": str(repository_id)},
        )
        await self._events.create(
            repository_id=repository_id,
            event_type=AuditEventType.REPOSITORY_UPDATED.value,
            actor_id=user_id,
        )
        return updated

    async def archive_repository(
        self,
        *,
        repository_id: UUID,
        user_id: UUID,
        ip_address: str | None,
        user_agent: str | None,
    ) -> None:
        repo = await self._repos.get(repository_id)
        if not repo:
            raise NotFoundError("Repository not found")
        await self._require_membership(repo.workspace_id, user_id, roles=_MANAGE_ROLES)

        archived = await self._repos.archive(repository_id)
        if not archived:
            raise DomainError("Repository is already archived", code="already_archived")

        self._audit.log(
            AuditEventType.REPOSITORY_ARCHIVED,
            user_id=user_id,
            ip_address=ip_address,
            user_agent=user_agent,
            payload={"repository_id": str(repository_id)},
        )
        await self._events.create(
            repository_id=repository_id,
            event_type=AuditEventType.REPOSITORY_ARCHIVED.value,
            actor_id=user_id,
        )

    async def restore_repository(
        self,
        *,
        repository_id: UUID,
        user_id: UUID,
        ip_address: str | None,
        user_agent: str | None,
    ) -> RepositoryRecord:
        # Authorize before mutating. `get()` returns archived repositories
        # (it only hides soft-deleted rows), which is what restore targets.
        repo = await self._repos.get(repository_id)
        if not repo:
            raise NotFoundError("Repository not found")
        await self._require_membership(repo.workspace_id, user_id, roles=_MANAGE_ROLES)

        restored = await self._repos.restore(repository_id)
        if not restored:
            raise NotFoundError("Repository not found")

        self._audit.log(
            AuditEventType.REPOSITORY_RESTORED,
            user_id=user_id,
            ip_address=ip_address,
            user_agent=user_agent,
            payload={"repository_id": str(repository_id)},
        )
        await self._events.create(
            repository_id=repository_id,
            event_type=AuditEventType.REPOSITORY_RESTORED.value,
            actor_id=user_id,
        )
        return restored

    async def delete_repository(
        self,
        *,
        repository_id: UUID,
        user_id: UUID,
        ip_address: str | None,
        user_agent: str | None,
    ) -> None:
        repo = await self._repos.get(repository_id)
        if not repo:
            raise NotFoundError("Repository not found")
        await self._require_membership(repo.workspace_id, user_id, roles=_MANAGE_ROLES)

        deleted = await self._repos.soft_delete(repository_id)
        if not deleted:
            raise NotFoundError("Repository not found")

        self._audit.log(
            AuditEventType.REPOSITORY_DELETED,
            user_id=user_id,
            ip_address=ip_address,
            user_agent=user_agent,
            payload={
                "repository_id": str(repository_id),
                "workspace_id": str(repo.workspace_id),
            },
        )
        await self._events.create(
            repository_id=repository_id,
            event_type=AuditEventType.REPOSITORY_DELETED.value,
            actor_id=user_id,
            payload={"workspace_id": str(repo.workspace_id)},
        )
