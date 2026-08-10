"""Unit tests for the repository import service."""
from __future__ import annotations

from uuid import uuid4

import pytest

from forge_api.application.repositories.import_service import RepositoryImportService
from forge_api.domain.audit import AuditEventType
from forge_api.domain.auth import WorkspaceRole
from forge_api.domain.errors import (
    AuthorizationError,
    ValidationError,
)


@pytest.fixture
def import_svc(fake_repositories, fake_workspaces, fake_repo_events, fake_audit):
    return RepositoryImportService(
        repositories=fake_repositories,
        workspaces=fake_workspaces,
        events=fake_repo_events,
        audit=fake_audit,
    )


async def _setup_workspace(fake_workspaces, role=WorkspaceRole.OWNER):
    owner = uuid4()
    w = await fake_workspaces.create(name="Team", slug="team")
    await fake_workspaces.add_member(
        workspace_id=w.id, user_id=owner, role=role,
    )
    return w, owner


class TestImportGitHub:
    @pytest.mark.asyncio
    async def test_import_github_by_url(self, import_svc, fake_workspaces, fake_audit):
        w, owner = await _setup_workspace(fake_workspaces)
        repo = await import_svc.import_github(
            workspace_id=w.id,
            user_id=owner,
            url="https://github.com/octocat/Hello-World",
            ip_address=None,
            user_agent=None,
        )
        assert repo.provider == "github"
        assert repo.owner == "octocat"
        assert repo.name == "Hello-World"
        assert repo.remote_url == "https://github.com/octocat/Hello-World"
        assert repo.clone_status.value == "pending"
        assert any(
            e["event"] == AuditEventType.REPOSITORY_IMPORTED
            for e in fake_audit.events
        )

    @pytest.mark.asyncio
    async def test_import_github_with_git_suffix(self, import_svc, fake_workspaces):
        w, owner = await _setup_workspace(fake_workspaces)
        repo = await import_svc.import_github(
            workspace_id=w.id,
            user_id=owner,
            url="https://github.com/acme/widget.git",
            ip_address=None,
            user_agent=None,
        )
        assert repo.name == "widget"
        assert repo.owner == "acme"

    @pytest.mark.asyncio
    async def test_invalid_github_url(self, import_svc, fake_workspaces):
        w, owner = await _setup_workspace(fake_workspaces)
        with pytest.raises(ValidationError, match="GitHub"):
            await import_svc.import_github(
                workspace_id=w.id,
                user_id=owner,
                url="https://gitlab.com/foo/bar",
                ip_address=None,
                user_agent=None,
            )

    @pytest.mark.asyncio
    async def test_member_cannot_import(self, import_svc, fake_workspaces):
        w, owner = await _setup_workspace(fake_workspaces)
        member = uuid4()
        await fake_workspaces.add_member(
            workspace_id=w.id, user_id=member, role=WorkspaceRole.VIEWER,
        )
        with pytest.raises(AuthorizationError):
            await import_svc.import_github(
                workspace_id=w.id,
                user_id=member,
                url="https://github.com/octocat/Hello-World",
                ip_address=None,
                user_agent=None,
            )


class TestImportLocal:
    @pytest.mark.asyncio
    async def test_import_local_folder(self, import_svc, fake_workspaces, fake_audit):
        w, owner = await _setup_workspace(fake_workspaces)
        repo = await import_svc.import_local(
            workspace_id=w.id,
            user_id=owner,
            path="/home/alice/projects/widget",
            ip_address=None,
            user_agent=None,
        )
        assert repo.provider == "local"
        assert repo.local_path == "/home/alice/projects/widget"
        assert repo.name == "widget"
        assert repo.clone_status.value == "ready"
        assert any(
            e["event"] == AuditEventType.REPOSITORY_IMPORTED
            for e in fake_audit.events
        )

    @pytest.mark.asyncio
    async def test_import_local_with_custom_name(self, import_svc, fake_workspaces):
        w, owner = await _setup_workspace(fake_workspaces)
        repo = await import_svc.import_local(
            workspace_id=w.id,
            user_id=owner,
            path="/home/alice/projects/widget",
            name="renamed",
            ip_address=None,
            user_agent=None,
        )
        assert repo.name == "renamed"

    @pytest.mark.asyncio
    async def test_empty_path_rejected(self, import_svc, fake_workspaces):
        w, owner = await _setup_workspace(fake_workspaces)
        with pytest.raises(ValidationError, match="must not be empty"):
            await import_svc.import_local(
                workspace_id=w.id,
                user_id=owner,
                path="   ",
                ip_address=None,
                user_agent=None,
            )
