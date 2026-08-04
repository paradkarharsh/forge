"""Unit tests for workspace tenancy service."""
from __future__ import annotations

from uuid import uuid4

import pytest

from forge_api.application.workspaces.workspace_service import WorkspaceService, slugify
from forge_api.domain.audit import AuditEventType
from forge_api.domain.auth import WorkspaceRole
from forge_api.domain.errors import (
    AuthorizationError,
    ConflictError,
    DomainError,
    NotFoundError,
)


@pytest.fixture
def workspace_svc(fake_workspaces, fake_audit):
    return WorkspaceService(workspaces=fake_workspaces, audit=fake_audit)


# ─── Slugify ───────────────────────────────────────────────────────


class TestSlugify:
    def test_simple_name(self):
        assert slugify("My Project") == "my-project"

    def test_special_characters(self):
        assert slugify("Hello & World!") == "hello-world"

    def test_leading_trailing_spaces(self):
        assert slugify("  spaces  ") == "spaces"

    def test_empty_fallback(self):
        assert slugify("!!!") == "workspace"

    def test_truncation(self):
        long = "a" * 200
        assert len(slugify(long)) <= 140


# ─── Create workspace ─────────────────────────────────────────────


class TestCreateWorkspace:
    @pytest.mark.asyncio
    async def test_create_assigns_owner_role(self, workspace_svc, fake_audit):
        workspace, role = await workspace_svc.create_workspace(
            name="Dev Team",
            owner_id=uuid4(),
            ip_address=None,
            user_agent=None,
        )
        assert workspace.name == "Dev Team"
        assert workspace.slug == "dev-team"
        assert role == WorkspaceRole.OWNER

    @pytest.mark.asyncio
    async def test_create_with_custom_slug(self, workspace_svc):
        w, _ = await workspace_svc.create_workspace(
            name="Dev Team",
            slug="custom-slug",
            owner_id=uuid4(),
            ip_address=None,
            user_agent=None,
        )
        assert w.slug == "custom-slug"

    @pytest.mark.asyncio
    async def test_create_with_description(self, workspace_svc):
        w, _ = await workspace_svc.create_workspace(
            name="Team",
            description="A great workspace",
            owner_id=uuid4(),
            ip_address=None,
            user_agent=None,
        )
        assert w.description == "A great workspace"

    @pytest.mark.asyncio
    async def test_duplicate_slug_raises_conflict(self, workspace_svc):
        owner = uuid4()
        await workspace_svc.create_workspace(
            name="alpha", owner_id=owner, ip_address=None, user_agent=None,
        )
        with pytest.raises(ConflictError, match="slug already taken"):
            await workspace_svc.create_workspace(
                name="Alpha", owner_id=owner, ip_address=None, user_agent=None,
            )

    @pytest.mark.asyncio
    async def test_create_emits_audit(self, workspace_svc, fake_audit):
        await workspace_svc.create_workspace(
            name="audit-me",
            owner_id=uuid4(),
            ip_address="1.2.3.4",
            user_agent="test",
        )
        assert any(e["event"] == AuditEventType.WORKSPACE_CREATED for e in fake_audit.events)


# ─── Get workspace ────────────────────────────────────────────────


class TestGetWorkspace:
    @pytest.mark.asyncio
    async def test_get_by_id(self, workspace_svc):
        w, _ = await workspace_svc.create_workspace(
            name="findme", owner_id=uuid4(), ip_address=None, user_agent=None,
        )
        found = await workspace_svc.get_workspace(w.id)
        assert found.id == w.id

    @pytest.mark.asyncio
    async def test_get_by_slug(self, workspace_svc):
        await workspace_svc.create_workspace(
            name="slug test", owner_id=uuid4(), ip_address=None, user_agent=None,
        )
        found = await workspace_svc.get_workspace_by_slug("slug-test")
        assert found.name == "slug test"

    @pytest.mark.asyncio
    async def test_get_nonexistent_raises(self, workspace_svc):
        with pytest.raises(NotFoundError):
            await workspace_svc.get_workspace(uuid4())


# ─── Rename workspace ─────────────────────────────────────────────


class TestRenameWorkspace:
    @pytest.mark.asyncio
    async def test_owner_can_rename(self, workspace_svc, fake_audit):
        owner = uuid4()
        w, _ = await workspace_svc.create_workspace(
            name="old", owner_id=owner, ip_address=None, user_agent=None,
        )
        renamed = await workspace_svc.rename_workspace(
            workspace_id=w.id, user_id=owner, name="new",
            ip_address=None, user_agent=None,
        )
        assert renamed.name == "new"

    @pytest.mark.asyncio
    async def test_non_member_cannot_rename(self, workspace_svc):
        owner = uuid4()
        w, _ = await workspace_svc.create_workspace(
            name="private", owner_id=owner, ip_address=None, user_agent=None,
        )
        with pytest.raises(AuthorizationError):
            await workspace_svc.rename_workspace(
                workspace_id=w.id, user_id=uuid4(), name="hacked",
                ip_address=None, user_agent=None,
            )

    @pytest.mark.asyncio
    async def test_viewer_cannot_rename(self, workspace_svc, fake_workspaces):
        owner = uuid4()
        viewer = uuid4()
        w, _ = await workspace_svc.create_workspace(
            name="guarded", owner_id=owner, ip_address=None, user_agent=None,
        )
        await fake_workspaces.add_member(
            workspace_id=w.id, user_id=viewer, role=WorkspaceRole.VIEWER,
        )
        with pytest.raises(AuthorizationError):
            await workspace_svc.rename_workspace(
                workspace_id=w.id, user_id=viewer, name="nope",
                ip_address=None, user_agent=None,
            )

    @pytest.mark.asyncio
    async def test_admin_can_rename(self, workspace_svc, fake_workspaces):
        owner = uuid4()
        admin = uuid4()
        w, _ = await workspace_svc.create_workspace(
            name="shared", owner_id=owner, ip_address=None, user_agent=None,
        )
        await fake_workspaces.add_member(
            workspace_id=w.id, user_id=admin, role=WorkspaceRole.ADMIN,
        )
        renamed = await workspace_svc.rename_workspace(
            workspace_id=w.id, user_id=admin, name="updated",
            ip_address=None, user_agent=None,
        )
        assert renamed.name == "updated"


# ─── Delete workspace ─────────────────────────────────────────────


class TestDeleteWorkspace:
    @pytest.mark.asyncio
    async def test_owner_can_delete(self, workspace_svc, fake_audit):
        owner = uuid4()
        w, _ = await workspace_svc.create_workspace(
            name="deleteme", owner_id=owner, ip_address=None, user_agent=None,
        )
        await workspace_svc.delete_workspace(
            workspace_id=w.id, user_id=owner, ip_address=None, user_agent=None,
        )
        with pytest.raises(NotFoundError):
            await workspace_svc.get_workspace(w.id)
        assert any(e["event"] == AuditEventType.WORKSPACE_DELETED for e in fake_audit.events)

    @pytest.mark.asyncio
    async def test_admin_cannot_delete(self, workspace_svc, fake_workspaces):
        owner = uuid4()
        admin = uuid4()
        w, _ = await workspace_svc.create_workspace(
            name="nope", owner_id=owner, ip_address=None, user_agent=None,
        )
        await fake_workspaces.add_member(
            workspace_id=w.id, user_id=admin, role=WorkspaceRole.ADMIN,
        )
        with pytest.raises(AuthorizationError, match="owner"):
            await workspace_svc.delete_workspace(
                workspace_id=w.id, user_id=admin, ip_address=None, user_agent=None,
            )

    @pytest.mark.asyncio
    async def test_deleted_workspace_not_in_list(self, workspace_svc):
        owner = uuid4()
        w, _ = await workspace_svc.create_workspace(
            name="gone", owner_id=owner, ip_address=None, user_agent=None,
        )
        await workspace_svc.delete_workspace(
            workspace_id=w.id, user_id=owner, ip_address=None, user_agent=None,
        )
        listing = await workspace_svc.list_workspaces(owner)
        assert len(listing) == 0


# ─── Membership management ────────────────────────────────────────


class TestAddMember:
    @pytest.mark.asyncio
    async def test_owner_can_add_member(self, workspace_svc, fake_audit):
        owner = uuid4()
        member = uuid4()
        w, _ = await workspace_svc.create_workspace(
            name="team", owner_id=owner, ip_address=None, user_agent=None,
        )
        await workspace_svc.add_member(
            workspace_id=w.id, actor_id=owner, target_user_id=member,
            role=WorkspaceRole.MEMBER, ip_address=None, user_agent=None,
        )
        members = await workspace_svc.list_members(w.id, owner)
        assert len(members) == 2  # owner + member
        assert any(
            e["event"] == AuditEventType.WORKSPACE_MEMBER_ADDED
            for e in fake_audit.events
        )

    @pytest.mark.asyncio
    async def test_cannot_add_as_owner(self, workspace_svc):
        owner = uuid4()
        w, _ = await workspace_svc.create_workspace(
            name="team", owner_id=owner, ip_address=None, user_agent=None,
        )
        with pytest.raises(DomainError, match="owner"):
            await workspace_svc.add_member(
                workspace_id=w.id, actor_id=owner, target_user_id=uuid4(),
                role=WorkspaceRole.OWNER, ip_address=None, user_agent=None,
            )

    @pytest.mark.asyncio
    async def test_duplicate_member_raises_conflict(self, workspace_svc):
        owner = uuid4()
        member = uuid4()
        w, _ = await workspace_svc.create_workspace(
            name="team", owner_id=owner, ip_address=None, user_agent=None,
        )
        await workspace_svc.add_member(
            workspace_id=w.id, actor_id=owner, target_user_id=member,
            role=WorkspaceRole.MEMBER, ip_address=None, user_agent=None,
        )
        with pytest.raises(ConflictError, match="already a member"):
            await workspace_svc.add_member(
                workspace_id=w.id, actor_id=owner, target_user_id=member,
                role=WorkspaceRole.MEMBER, ip_address=None, user_agent=None,
            )

    @pytest.mark.asyncio
    async def test_viewer_cannot_add_member(self, workspace_svc, fake_workspaces):
        owner = uuid4()
        viewer = uuid4()
        w, _ = await workspace_svc.create_workspace(
            name="team", owner_id=owner, ip_address=None, user_agent=None,
        )
        await fake_workspaces.add_member(
            workspace_id=w.id, user_id=viewer, role=WorkspaceRole.VIEWER,
        )
        with pytest.raises(AuthorizationError):
            await workspace_svc.add_member(
                workspace_id=w.id, actor_id=viewer, target_user_id=uuid4(),
                role=WorkspaceRole.MEMBER, ip_address=None, user_agent=None,
            )


class TestRemoveMember:
    @pytest.mark.asyncio
    async def test_owner_can_remove_member(self, workspace_svc, fake_audit):
        owner = uuid4()
        member = uuid4()
        w, _ = await workspace_svc.create_workspace(
            name="team", owner_id=owner, ip_address=None, user_agent=None,
        )
        await workspace_svc.add_member(
            workspace_id=w.id, actor_id=owner, target_user_id=member,
            role=WorkspaceRole.MEMBER, ip_address=None, user_agent=None,
        )
        await workspace_svc.remove_member(
            workspace_id=w.id, actor_id=owner, target_user_id=member,
            ip_address=None, user_agent=None,
        )
        members = await workspace_svc.list_members(w.id, owner)
        assert len(members) == 1  # only owner left
        assert any(
            e["event"] == AuditEventType.WORKSPACE_MEMBER_REMOVED
            for e in fake_audit.events
        )

    @pytest.mark.asyncio
    async def test_cannot_remove_owner(self, workspace_svc):
        owner = uuid4()
        admin = uuid4()
        w, _ = await workspace_svc.create_workspace(
            name="team", owner_id=owner, ip_address=None, user_agent=None,
        )
        await workspace_svc.add_member(
            workspace_id=w.id, actor_id=owner, target_user_id=admin,
            role=WorkspaceRole.ADMIN, ip_address=None, user_agent=None,
        )
        with pytest.raises(DomainError, match="owner"):
            await workspace_svc.remove_member(
                workspace_id=w.id, actor_id=admin, target_user_id=owner,
                ip_address=None, user_agent=None,
            )


class TestChangeMemberRole:
    @pytest.mark.asyncio
    async def test_owner_can_change_role(self, workspace_svc, fake_audit):
        owner = uuid4()
        member = uuid4()
        w, _ = await workspace_svc.create_workspace(
            name="team", owner_id=owner, ip_address=None, user_agent=None,
        )
        await workspace_svc.add_member(
            workspace_id=w.id, actor_id=owner, target_user_id=member,
            role=WorkspaceRole.MEMBER, ip_address=None, user_agent=None,
        )
        await workspace_svc.change_member_role(
            workspace_id=w.id, actor_id=owner, target_user_id=member,
            role=WorkspaceRole.ADMIN, ip_address=None, user_agent=None,
        )
        assert any(
            e["event"] == AuditEventType.WORKSPACE_MEMBER_ROLE_CHANGED
            for e in fake_audit.events
        )

    @pytest.mark.asyncio
    async def test_cannot_assign_owner_role(self, workspace_svc):
        owner = uuid4()
        member = uuid4()
        w, _ = await workspace_svc.create_workspace(
            name="team", owner_id=owner, ip_address=None, user_agent=None,
        )
        await workspace_svc.add_member(
            workspace_id=w.id, actor_id=owner, target_user_id=member,
            role=WorkspaceRole.MEMBER, ip_address=None, user_agent=None,
        )
        with pytest.raises(DomainError, match="owner"):
            await workspace_svc.change_member_role(
                workspace_id=w.id, actor_id=owner, target_user_id=member,
                role=WorkspaceRole.OWNER, ip_address=None, user_agent=None,
            )

    @pytest.mark.asyncio
    async def test_cannot_change_owner_role(self, workspace_svc):
        owner = uuid4()
        admin = uuid4()
        w, _ = await workspace_svc.create_workspace(
            name="team", owner_id=owner, ip_address=None, user_agent=None,
        )
        await workspace_svc.add_member(
            workspace_id=w.id, actor_id=owner, target_user_id=admin,
            role=WorkspaceRole.ADMIN, ip_address=None, user_agent=None,
        )
        with pytest.raises(DomainError, match="owner"):
            await workspace_svc.change_member_role(
                workspace_id=w.id, actor_id=admin, target_user_id=owner,
                role=WorkspaceRole.MEMBER, ip_address=None, user_agent=None,
            )


# ─── List workspaces ──────────────────────────────────────────────


class TestListWorkspaces:
    @pytest.mark.asyncio
    async def test_list_returns_user_workspaces(self, workspace_svc):
        owner = uuid4()
        await workspace_svc.create_workspace(
            name="ws1", slug="ws1", owner_id=owner,
            ip_address=None, user_agent=None,
        )
        await workspace_svc.create_workspace(
            name="ws2", slug="ws2", owner_id=owner,
            ip_address=None, user_agent=None,
        )
        result = await workspace_svc.list_workspaces(owner)
        assert len(result) == 2

    @pytest.mark.asyncio
    async def test_list_excludes_other_users(self, workspace_svc):
        a, b = uuid4(), uuid4()
        await workspace_svc.create_workspace(
            name="a-ws", slug="a-ws", owner_id=a,
            ip_address=None, user_agent=None,
        )
        await workspace_svc.create_workspace(
            name="b-ws", slug="b-ws", owner_id=b,
            ip_address=None, user_agent=None,
        )
        result = await workspace_svc.list_workspaces(a)
        assert len(result) == 1
        assert result[0][0].name == "a-ws"
