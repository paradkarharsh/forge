"""Unit tests for the repository clone service and status tracking."""
from __future__ import annotations

from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest

from forge_api.application.repositories.clone_service import RepositoryCloneService
from forge_api.domain.audit import AuditEventType
from forge_api.domain.auth import WorkspaceRole
from forge_api.domain.errors import AuthorizationError, DomainError, NotFoundError


@pytest.fixture
def clone_svc(fake_repositories, fake_branches, fake_workspaces, fake_repo_events, fake_audit):
    return RepositoryCloneService(
        repositories=fake_repositories,
        branches=fake_branches,
        workspaces=fake_workspaces,
        events=fake_repo_events,
        audit=fake_audit,
    )


async def _setup_repo(fake_repositories, fake_workspaces, **overrides):
    owner = uuid4()
    w = await fake_workspaces.create(name="Team", slug="team")
    await fake_workspaces.add_member(
        workspace_id=w.id, user_id=owner, role=WorkspaceRole.OWNER,
    )
    params = {
        "workspace_id": w.id,
        "name": "widget",
        "owner": "alice",
        "provider": "github",
        "remote_url": "https://github.com/alice/widget",
    }
    params.update(overrides)
    repo = await fake_repositories.create(**params)
    return repo, owner, w


class TestCloneRepository:
    @pytest.mark.asyncio
    async def test_successful_clone(
        self, clone_svc, fake_repositories, fake_workspaces, fake_branches, fake_audit
    ):
        repo, owner, _ = await _setup_repo(fake_repositories, fake_workspaces)
        # Simulate successful git operations
        with patch.object(
            clone_svc, "_validate_remote", new_callable=AsyncMock
        ) as validate, patch.object(
            clone_svc, "_git_clone", new_callable=AsyncMock
        ) as git_clone, patch.object(
            clone_svc, "_extract_metadata", new_callable=AsyncMock, return_value={
                "default_branch": "main",
                "last_commit_hash": "abc123",
                "size_bytes": 1024,
            }
        ) as metadata, patch.object(
            clone_svc, "_discover_branches", new_callable=AsyncMock, return_value=[
                {"name": "main", "commit_hash": "abc123", "is_default": True},
                {"name": "dev", "commit_hash": "def456", "is_default": False},
            ]
        ) as branches:
            updated = await clone_svc.clone_repository(
                repository_id=repo.id,
                user_id=owner,
                ip_address=None,
                user_agent=None,
            )

        assert updated.clone_status.value == "ready"
        assert updated.default_branch == "main"
        assert updated.last_commit_hash == "abc123"
        validate.assert_awaited_once()
        git_clone.assert_awaited_once()
        metadata.assert_awaited_once()
        branches.assert_awaited_once()
        assert any(
            e["event"] == AuditEventType.REPOSITORY_CLONED
            for e in fake_audit.events
        )
        # Branches were persisted
        stored = await fake_branches.list_by_repository(repo.id)
        assert len(stored) == 2

    @pytest.mark.asyncio
    async def test_clone_marks_failed_on_error(
        self, clone_svc, fake_repositories, fake_workspaces
    ):
        repo, owner, _ = await _setup_repo(fake_repositories, fake_workspaces)
        with patch.object(
            clone_svc, "_validate_remote", new_callable=AsyncMock,
            side_effect=DomainError("no remote"),
        ):
            with pytest.raises(DomainError, match="Clone failed"):
                await clone_svc.clone_repository(
                    repository_id=repo.id,
                    user_id=owner,
                    ip_address=None,
                    user_agent=None,
                )
        failed = await fake_repositories.get(repo.id)
        assert failed.clone_status.value == "failed"

    @pytest.mark.asyncio
    async def test_clone_nonexistent_repo(self, clone_svc):
        with pytest.raises(NotFoundError):
            await clone_svc.clone_repository(
                repository_id=uuid4(),
                user_id=uuid4(),
                ip_address=None,
                user_agent=None,
            )

    @pytest.mark.asyncio
    async def test_clone_requires_membership(self, clone_svc, fake_repositories, fake_workspaces):
        repo, _, _ = await _setup_repo(fake_repositories, fake_workspaces)
        with pytest.raises(AuthorizationError):
            await clone_svc.clone_repository(
                repository_id=repo.id,
                user_id=uuid4(),
                ip_address=None,
                user_agent=None,
            )

    @pytest.mark.asyncio
    async def test_clone_without_remote_url(
        self, clone_svc, fake_repositories, fake_workspaces
    ):
        repo, owner, _ = await _setup_repo(
            fake_repositories, fake_workspaces, remote_url=None, provider="local",
        )
        with pytest.raises(DomainError, match="no remote URL"):
            await clone_svc.clone_repository(
                repository_id=repo.id,
                user_id=owner,
                ip_address=None,
                user_agent=None,
            )


class TestRepositoryStatus:
    @pytest.mark.asyncio
    async def test_get_status(self, clone_svc, fake_repositories, fake_workspaces):
        repo, owner, _ = await _setup_repo(fake_repositories, fake_workspaces)
        status = await clone_svc.get_repository_status(repo.id, owner)
        assert status["repository_id"] == str(repo.id)
        assert status["clone_status"] == "pending"
        assert status["sync_status"] == "idle"

    @pytest.mark.asyncio
    async def test_get_status_forbidden(self, clone_svc, fake_repositories, fake_workspaces):
        repo, _, _ = await _setup_repo(fake_repositories, fake_workspaces)
        with pytest.raises(AuthorizationError):
            await clone_svc.get_repository_status(repo.id, uuid4())


class TestMetadataExtraction:
    @pytest.mark.asyncio
    async def test_branch_discovery_persists_all_branches(
        self, clone_svc, fake_repositories, fake_workspaces, fake_branches
    ):
        repo, owner, _ = await _setup_repo(fake_repositories, fake_workspaces)
        # Patch the underlying clone operations
        with patch.object(
            clone_svc, "_validate_remote", new_callable=AsyncMock
        ), patch.object(
            clone_svc, "_git_clone", new_callable=AsyncMock
        ), patch.object(
            clone_svc, "_extract_metadata", new_callable=AsyncMock, return_value={
                "default_branch": "main",
                "last_commit_hash": "abc123",
                "size_bytes": 100,
            }
        ), patch.object(
            clone_svc, "_discover_branches", new_callable=AsyncMock, return_value=[
                {"name": "main", "commit_hash": "abc123", "is_default": True},
                {"name": "dev", "commit_hash": "def456", "is_default": False},
                {"name": "feature/x", "commit_hash": "789abc", "is_default": False},
            ]
        ):
            await clone_svc.clone_repository(
                repository_id=repo.id,
                user_id=owner,
                ip_address=None,
                user_agent=None,
            )
        # All three branches persisted
        stored = await fake_branches.list_by_repository(repo.id)
        assert len(stored) == 3
        default = [b for b in stored if b.is_default]
        assert len(default) == 1
        assert default[0].name == "main"