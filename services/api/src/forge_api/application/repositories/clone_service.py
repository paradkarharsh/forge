"""Repository clone service.

Handles git clone operations, branch discovery, metadata extraction,
and clone status tracking. Clone operations run synchronously in this
implementation; the background job service queues them for async execution.
"""
import asyncio
import logging
import os
import tempfile
from uuid import UUID

from forge_api.domain.audit import AuditEventType
from forge_api.domain.auth import WorkspaceRole
from forge_api.domain.errors import AuthorizationError, DomainError, NotFoundError
from forge_api.domain.repositories import (
    RepositoryBranchRepository,
    RepositoryEventRepository,
    RepositoryRepository,
    WorkspaceRepository,
)
from forge_api.domain.repository import CloneStatus, RepositoryRecord
from forge_api.infrastructure.audit import AuditLogger

logger = logging.getLogger(__name__)

_CLONE_ROLES = frozenset(
    {WorkspaceRole.OWNER, WorkspaceRole.ADMIN, WorkspaceRole.MAINTAINER}
)


class RepositoryCloneService:
    """Handles cloning repositories, discovering branches, and extracting metadata."""

    def __init__(
        self,
        *,
        repositories: RepositoryRepository,
        branches: RepositoryBranchRepository,
        workspaces: WorkspaceRepository,
        events: RepositoryEventRepository,
        audit: AuditLogger,
        clone_base_dir: str | None = None,
    ) -> None:
        self._repos = repositories
        self._branches = branches
        self._workspaces = workspaces
        self._events = events
        self._audit = audit
        self._clone_base_dir = clone_base_dir or tempfile.gettempdir()

    async def _require_role(
        self, workspace_id: UUID, user_id: UUID
    ) -> WorkspaceRole:
        member = await self._workspaces.get_membership(workspace_id, user_id)
        if not member:
            raise AuthorizationError("Not a member of this workspace")
        if member.role not in _CLONE_ROLES:
            raise AuthorizationError("Insufficient workspace role")
        return member.role

    async def clone_repository(
        self,
        *,
        repository_id: UUID,
        user_id: UUID,
        ip_address: str | None,
        user_agent: str | None,
    ) -> RepositoryRecord:
        """Start cloning a repository. Updates status through pending → cloning → ready/failed."""
        repo = await self._repos.get(repository_id)
        if not repo:
            raise NotFoundError("Repository not found")

        await self._require_role(repo.workspace_id, user_id)

        if not repo.remote_url:
            raise DomainError(
                "Repository has no remote URL to clone from",
                code="no_remote_url",
            )

        if repo.clone_status == CloneStatus.CLONING:
            raise DomainError("Repository is already being cloned", code="clone_in_progress")

        # Mark as cloning
        await self._repos.update(repository_id, clone_status="cloning")

        try:
            # Validate the remote URL
            await self._validate_remote(repo.remote_url)

            # Execute clone
            clone_dir = os.path.join(
                self._clone_base_dir, "forge_repos", str(repo.workspace_id), str(repo.id)
            )
            await self._git_clone(repo.remote_url, clone_dir)

            # Extract metadata
            metadata = await self._extract_metadata(clone_dir)

            # Discover branches
            branch_list = await self._discover_branches(clone_dir)

            # Store branches
            for branch_info in branch_list:
                await self._branches.upsert(
                    repository_id=repository_id,
                    name=branch_info["name"],
                    commit_hash=branch_info.get("commit_hash"),
                    is_default=branch_info.get("is_default", False),
                )

            # Update repository with metadata
            updated = await self._repos.update(
                repository_id,
                clone_status="ready",
                local_path=clone_dir,
                default_branch=metadata.get("default_branch"),
                current_branch=metadata.get("default_branch"),
                last_commit_hash=metadata.get("last_commit_hash"),
                size_bytes=metadata.get("size_bytes"),
            )

            self._audit.log(
                AuditEventType.REPOSITORY_CLONED,
                user_id=user_id,
                ip_address=ip_address,
                user_agent=user_agent,
                payload={
                    "repository_id": str(repository_id),
                    "branch_count": len(branch_list),
                    "default_branch": metadata.get("default_branch"),
                },
            )
            await self._events.create(
                repository_id=repository_id,
                event_type=AuditEventType.REPOSITORY_CLONED.value,
                actor_id=user_id,
                payload={
                    "branch_count": len(branch_list),
                    "default_branch": metadata.get("default_branch"),
                },
            )

            return updated

        except Exception as exc:
            logger.exception("Clone failed for repository %s", repository_id)
            await self._repos.update(
                repository_id,
                clone_status="failed",
            )
            raise DomainError(
                f"Clone failed: {exc}",
                code="clone_failed",
            ) from exc

    async def _validate_remote(self, url: str) -> None:
        """Validate the remote URL using git ls-remote."""
        proc = await asyncio.create_subprocess_exec(
            "git", "ls-remote", "--exit-code", url,
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.PIPE,
        )
        _, stderr = await asyncio.wait_for(proc.communicate(), timeout=30)
        if proc.returncode != 0:
            raise DomainError(
                f"Remote URL is not accessible: {stderr.decode().strip()}",
                code="invalid_remote",
            )

    async def _git_clone(self, url: str, target_dir: str) -> None:
        """Clone the repository into the target directory."""
        os.makedirs(target_dir, exist_ok=True)
        proc = await asyncio.create_subprocess_exec(
            "git", "clone", "--no-checkout", url, target_dir,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        _, stderr = await asyncio.wait_for(proc.communicate(), timeout=300)
        if proc.returncode != 0:
            raise DomainError(
                f"Git clone failed: {stderr.decode().strip()}",
                code="clone_failed",
            )

    async def _extract_metadata(self, repo_dir: str) -> dict:
        """Extract metadata from a cloned repository."""
        metadata: dict = {}

        # Default branch
        proc = await asyncio.create_subprocess_exec(
            "git", "-C", repo_dir, "symbolic-ref", "refs/remotes/origin/HEAD",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.DEVNULL,
        )
        stdout, _ = await proc.communicate()
        if proc.returncode == 0:
            ref = stdout.decode().strip()
            metadata["default_branch"] = ref.split("/")[-1]

        # Last commit hash
        proc = await asyncio.create_subprocess_exec(
            "git", "-C", repo_dir, "rev-parse", "HEAD",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.DEVNULL,
        )
        stdout, _ = await proc.communicate()
        if proc.returncode == 0:
            metadata["last_commit_hash"] = stdout.decode().strip()

        # Repository size
        try:
            total_size = 0
            for dirpath, _dirnames, filenames in os.walk(repo_dir):
                for f in filenames:
                    fp = os.path.join(dirpath, f)
                    if os.path.isfile(fp):
                        total_size += os.path.getsize(fp)
            metadata["size_bytes"] = total_size
        except OSError:
            metadata["size_bytes"] = None

        return metadata

    async def _discover_branches(self, repo_dir: str) -> list[dict]:
        """Discover all branches in a cloned repository."""
        proc = await asyncio.create_subprocess_exec(
            "git",
            "-C",
            repo_dir,
            "branch",
            "-r",
            "--format",
            "%(refname:short) %(objectname:short)",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.DEVNULL,
        )
        stdout, _ = await proc.communicate()
        if proc.returncode != 0:
            return []

        branches: list[dict] = []
        default_branch = None

        # Detect default branch
        proc2 = await asyncio.create_subprocess_exec(
            "git", "-C", repo_dir, "symbolic-ref", "refs/remotes/origin/HEAD",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.DEVNULL,
        )
        stdout2, _ = await proc2.communicate()
        if proc2.returncode == 0:
            default_branch = stdout2.decode().strip().split("/")[-1]

        for line in stdout.decode().strip().splitlines():
            parts = line.strip().split(None, 1)
            if not parts:
                continue
            ref = parts[0]
            commit = parts[1] if len(parts) > 1 else None

            # Skip origin/HEAD
            if ref == "origin/HEAD":
                continue

            name = ref.replace("origin/", "", 1)
            branches.append({
                "name": name,
                "commit_hash": commit,
                "is_default": name == default_branch,
            })

        return branches

    async def get_repository_status(
        self, repository_id: UUID, user_id: UUID
    ) -> dict:
        """Get detailed clone and sync status for a repository."""
        repo = await self._repos.get(repository_id)
        if not repo:
            raise NotFoundError("Repository not found")
        await self._require_role(repo.workspace_id, user_id)

        return {
            "repository_id": str(repo.id),
            "clone_status": repo.clone_status.value,
            "sync_status": repo.sync_status.value,
            "default_branch": repo.default_branch,
            "current_branch": repo.current_branch,
            "last_commit_hash": repo.last_commit_hash,
            "last_synced_at": repo.last_synced_at.isoformat() if repo.last_synced_at else None,
            "size_bytes": repo.size_bytes,
        }
