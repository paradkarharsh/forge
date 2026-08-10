"""Repository import service.

Supports importing repositories from GitHub or local folders.
Designed so GitLab and Bitbucket providers can be added later
without modifying existing code — each provider is a strategy.
"""
import re
from uuid import UUID

from forge_api.domain.audit import AuditEventType
from forge_api.domain.auth import WorkspaceRole
from forge_api.domain.errors import AuthorizationError, ValidationError
from forge_api.domain.repositories import (
    RepositoryEventRepository,
    RepositoryRepository,
    WorkspaceRepository,
)
from forge_api.domain.repository import RepositoryRecord
from forge_api.infrastructure.audit import AuditLogger

_IMPORT_ROLES = frozenset(
    {WorkspaceRole.OWNER, WorkspaceRole.ADMIN, WorkspaceRole.MAINTAINER}
)

_GITHUB_URL_RE = re.compile(
    r"^https?://github\.com/(?P<owner>[^/]+)/(?P<name>[^/]+?)(?:\.git)?$"
)


class RepositoryImportService:
    """Handles repository import from external providers and local paths."""

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

    async def _require_import_role(
        self, workspace_id: UUID, user_id: UUID
    ) -> WorkspaceRole:
        member = await self._workspaces.get_membership(workspace_id, user_id)
        if not member:
            raise AuthorizationError("Not a member of this workspace")
        if member.role not in _IMPORT_ROLES:
            raise AuthorizationError("Insufficient workspace role")
        return member.role

    async def import_github(
        self,
        *,
        workspace_id: UUID,
        user_id: UUID,
        url: str,
        description: str | None = None,
        visibility: str = "private",
        ip_address: str | None,
        user_agent: str | None,
    ) -> RepositoryRecord:
        """Import a GitHub repository by URL."""
        await self._require_import_role(workspace_id, user_id)

        match = _GITHUB_URL_RE.match(url.strip())
        if not match:
            raise ValidationError(
                "Invalid GitHub repository URL",
                code="invalid_github_url",
            )

        owner = match.group("owner")
        name = match.group("name")

        repo = await self._repos.create(
            workspace_id=workspace_id,
            name=name,
            owner=owner,
            provider="github",
            remote_url=url.strip(),
            visibility=visibility,
            description=description,
            clone_status="pending",
        )

        self._audit.log(
            AuditEventType.REPOSITORY_IMPORTED,
            user_id=user_id,
            ip_address=ip_address,
            user_agent=user_agent,
            payload={
                "repository_id": str(repo.id),
                "workspace_id": str(workspace_id),
                "provider": "github",
                "url": url.strip(),
            },
        )
        await self._events.create(
            repository_id=repo.id,
            event_type=AuditEventType.REPOSITORY_IMPORTED.value,
            actor_id=user_id,
            payload={"provider": "github", "url": url.strip()},
        )
        return repo

    async def import_local(
        self,
        *,
        workspace_id: UUID,
        user_id: UUID,
        path: str,
        name: str | None = None,
        description: str | None = None,
        ip_address: str | None,
        user_agent: str | None,
    ) -> RepositoryRecord:
        """Import a local folder as a repository."""
        await self._require_import_role(workspace_id, user_id)

        path = path.strip()
        if not path:
            raise ValidationError("Local path must not be empty", code="invalid_path")

        repo_name = name or path.rstrip("/\\").split("/")[-1].split("\\")[-1]
        if not repo_name:
            repo_name = "local-repo"

        repo = await self._repos.create(
            workspace_id=workspace_id,
            name=repo_name,
            owner="local",
            provider="local",
            local_path=path,
            visibility="private",
            description=description,
            clone_status="ready",
            sync_status="idle",
        )

        self._audit.log(
            AuditEventType.REPOSITORY_IMPORTED,
            user_id=user_id,
            ip_address=ip_address,
            user_agent=user_agent,
            payload={
                "repository_id": str(repo.id),
                "workspace_id": str(workspace_id),
                "provider": "local",
                "path": path,
            },
        )
        await self._events.create(
            repository_id=repo.id,
            event_type=AuditEventType.REPOSITORY_IMPORTED.value,
            actor_id=user_id,
            payload={"provider": "local", "path": path},
        )
        return repo
