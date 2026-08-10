"""Unit tests for the repository application service (CRUD)."""
from __future__ import annotations

from uuid import uuid4

import pytest

from forge_api.application.repositories.repository_service import RepositoryService
from forge_api.domain.audit import AuditEventType
from forge_api.domain.auth import WorkspaceRole
from forge_api.domain.errors import (
    AuthorizationError,
    NotFoundError,
)


@pytest.fixture
def repo_svc(fake_repositories, fake_workspaces, fake_repo_events, fake_audit):
    return RepositoryService(
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


class TestCreateRepository:
    @pytest.mark.asyncio
    async def test_owner_can_create(self, repo_svc, fake_workspaces, fake_audit):
        w, owner = await _setup_workspace(fake_workspaces)
        repo = await repo_svc.create_repository(
            workspace_id=w.id,
            user_id=owner,
            name="My Repo",
            owner="alice",
            provider="github",
            remote_url="https://github.com/alice/my-repo",
            ip_address=None,
            user_agent=None,
        )
        assert repo.name == "My Repo"
        assert repo.owner == "alice"
        assert repo.provider == "github"
        assert repo.clone_status.value == "pending"
        assert any(
            e["event"] == AuditEventType.REPOSITORY_CREATED
            for e in fake_audit.events
        )

    @pytest.mark.asyncio
    async def test_member_cannot_create(self, repo_svc, fake_workspaces):
        w, owner = await _setup_workspace(fake_workspaces)
        member = uuid4()
        await fake_workspaces.add_member(
            workspace_id=w.id, user_id=member, role=WorkspaceRole.VIEWER,
        )
        with pytest.raises(AuthorizationError):
            await repo_svc.create_repository(
                workspace_id=w.id,
                user_id=member,
                name="No",
                owner="x",
                provider="github",
                ip_address=None,
                user_agent=None,
            )

    @pytest.mark.asyncio
    async def test_non_member_cannot_create(self, repo_svc, fake_workspaces):
        w, _ = await _setup_workspace(fake_workspaces)
        with pytest.raises(AuthorizationError):
            await repo_svc.create_repository(
                workspace_id=w.id,
                user_id=uuid4(),
                name="No",
                owner="x",
                provider="github",
                ip_address=None,
                user_agent=None,
            )


class TestGetRepository:
    @pytest.mark.asyncio
    async def test_get_returns_repository(self, repo_svc, fake_workspaces):
        w, owner = await _setup_workspace(fake_workspaces)
        repo = await repo_svc.create_repository(
            workspace_id=w.id, user_id=owner, name="find",
            owner="alice", provider="github",
            ip_address=None, user_agent=None,
        )
        found = await repo_svc.get_repository(repo.id, owner)
        assert found.id == repo.id

    @pytest.mark.asyncio
    async def test_get_nonexistent_raises(self, repo_svc):
        with pytest.raises(NotFoundError):
            await repo_svc.get_repository(uuid4(), uuid4())

    @pytest.mark.asyncio
    async def test_get_forbidden_for_outsider(self, repo_svc, fake_workspaces):
        w, owner = await _setup_workspace(fake_workspaces)
        repo = await repo_svc.create_repository(
            workspace_id=w.id, user_id=owner, name="private",
            owner="alice", provider="github",
            ip_address=None, user_agent=None,
        )
        with pytest.raises(AuthorizationError):
            await repo_svc.get_repository(repo.id, uuid4())


class TestListRepositories:
    @pytest.mark.asyncio
    async def test_list_scoped_to_workspace(self, repo_svc, fake_workspaces):
        w1, o1 = await _setup_workspace(fake_workspaces)
        w2, o2 = await _setup_workspace(fake_workspaces)
        await repo_svc.create_repository(
            workspace_id=w1.id, user_id=o1, name="a",
            owner="alice", provider="github",
            ip_address=None, user_agent=None,
        )
        await repo_svc.create_repository(
            workspace_id=w2.id, user_id=o2, name="b",
            owner="bob", provider="local",
            ip_address=None, user_agent=None,
        )
        listing = await repo_svc.list_repositories(w1.id, o1)
        assert len(listing) == 1
        assert listing[0].name == "a"

    @pytest.mark.asyncio
    async def test_list_requires_membership(self, repo_svc, fake_workspaces):
        w, _ = await _setup_workspace(fake_workspaces)
        with pytest.raises(AuthorizationError):
            await repo_svc.list_repositories(w.id, uuid4())


class TestUpdateRepository:
    @pytest.mark.asyncio
    async def test_update_name_and_description(self, repo_svc, fake_workspaces, fake_audit):
        w, owner = await _setup_workspace(fake_workspaces)
        repo = await repo_svc.create_repository(
            workspace_id=w.id, user_id=owner, name="old",
            owner="alice", provider="github",
            ip_address=None, user_agent=None,
        )
        updated = await repo_svc.update_repository(
            repository_id=repo.id,
            user_id=owner,
            name="new",
            description="a description",
            ip_address=None,
            user_agent=None,
        )
        assert updated.name == "new"
        assert updated.description == "a description"
        assert any(
            e["event"] == AuditEventType.REPOSITORY_UPDATED
            for e in fake_audit.events
        )

    @pytest.mark.asyncio
    async def test_member_cannot_update(self, repo_svc, fake_workspaces):
        w, owner = await _setup_workspace(fake_workspaces)
        member = uuid4()
        await fake_workspaces.add_member(
            workspace_id=w.id, user_id=member, role=WorkspaceRole.VIEWER,
        )
        repo = await repo_svc.create_repository(
            workspace_id=w.id, user_id=owner, name="x",
            owner="alice", provider="github",
            ip_address=None, user_agent=None,
        )
        with pytest.raises(AuthorizationError):
            await repo_svc.update_repository(
                repository_id=repo.id, user_id=member, name="hacked",
                ip_address=None, user_agent=None,
            )


class TestArchiveRestore:
    @pytest.mark.asyncio
    async def test_owner_can_archive(self, repo_svc, fake_workspaces, fake_audit):
        w, owner = await _setup_workspace(fake_workspaces)
        repo = await repo_svc.create_repository(
            workspace_id=w.id, user_id=owner, name="arch",
            owner="alice", provider="github",
            ip_address=None, user_agent=None,
        )
        await repo_svc.archive_repository(
            repository_id=repo.id, user_id=owner,
            ip_address=None, user_agent=None,
        )
        assert any(
            e["event"] == AuditEventType.REPOSITORY_ARCHIVED
            for e in fake_audit.events
        )
        listing = await repo_svc.list_repositories(w.id, owner)
        assert len(listing) == 0

    @pytest.mark.asyncio
    async def test_archived_hidden_by_default(self, repo_svc, fake_workspaces):
        w, owner = await _setup_workspace(fake_workspaces)
        repo = await repo_svc.create_repository(
            workspace_id=w.id, user_id=owner, name="arch",
            owner="alice", provider="github",
            ip_address=None, user_agent=None,
        )
        await repo_svc.archive_repository(
            repository_id=repo.id, user_id=owner,
            ip_address=None, user_agent=None,
        )
        listing = await repo_svc.list_repositories(w.id, owner, include_archived=True)
        assert len(listing) == 1

    @pytest.mark.asyncio
    async def test_restore(self, repo_svc, fake_workspaces, fake_audit):
        w, owner = await _setup_workspace(fake_workspaces)
        repo = await repo_svc.create_repository(
            workspace_id=w.id, user_id=owner, name="restore-me",
            owner="alice", provider="github",
            ip_address=None, user_agent=None,
        )
        await repo_svc.archive_repository(
            repository_id=repo.id, user_id=owner,
            ip_address=None, user_agent=None,
        )
        restored = await repo_svc.restore_repository(
            repository_id=repo.id, user_id=owner,
            ip_address=None, user_agent=None,
        )
        assert restored.id == repo.id
        assert any(
            e["event"] == AuditEventType.REPOSITORY_RESTORED
            for e in fake_audit.events
        )

    @pytest.mark.asyncio
    async def test_member_cannot_archive(self, repo_svc, fake_workspaces):
        w, owner = await _setup_workspace(fake_workspaces)
        member = uuid4()
        await fake_workspaces.add_member(
            workspace_id=w.id, user_id=member, role=WorkspaceRole.VIEWER,
        )
        repo = await repo_svc.create_repository(
            workspace_id=w.id, user_id=owner, name="x",
            owner="alice", provider="github",
            ip_address=None, user_agent=None,
        )
        with pytest.raises(AuthorizationError):
            await repo_svc.archive_repository(
                repository_id=repo.id, user_id=member,
                ip_address=None, user_agent=None,
            )


class TestDeleteRepository:
    @pytest.mark.asyncio
    async def test_owner_can_delete(self, repo_svc, fake_workspaces, fake_audit):
        w, owner = await _setup_workspace(fake_workspaces)
        repo = await repo_svc.create_repository(
            workspace_id=w.id, user_id=owner, name="del",
            owner="alice", provider="github",
            ip_address=None, user_agent=None,
        )
        await repo_svc.delete_repository(
            repository_id=repo.id, user_id=owner,
            ip_address=None, user_agent=None,
        )
        with pytest.raises(NotFoundError):
            await repo_svc.get_repository(repo.id, owner)
        assert any(
            e["event"] == AuditEventType.REPOSITORY_DELETED
            for e in fake_audit.events
        )

    @pytest.mark.asyncio
    async def test_member_cannot_delete(self, repo_svc, fake_workspaces):
        w, owner = await _setup_workspace(fake_workspaces)
        member = uuid4()
        await fake_workspaces.add_member(
            workspace_id=w.id, user_id=member, role=WorkspaceRole.MEMBER,
        )
        repo = await repo_svc.create_repository(
            workspace_id=w.id, user_id=owner, name="x",
            owner="alice", provider="github",
            ip_address=None, user_agent=None,
        )
        with pytest.raises(AuthorizationError):
            await repo_svc.delete_repository(
                repository_id=repo.id, user_id=member,
                ip_address=None, user_agent=None,
            )
