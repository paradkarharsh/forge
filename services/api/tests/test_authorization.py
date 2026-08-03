"""Workspace authorization tests."""
from datetime import UTC, datetime
from uuid import uuid4

import pytest

from forge_api.application.workspaces.workspace_service import WorkspaceService
from forge_api.domain.auth import WorkspaceRole
from forge_api.domain.errors import AuthorizationError, NotFoundError


@pytest.fixture
def workspace_service(fake_workspaces, fake_audit):
    return WorkspaceService(workspaces=fake_workspaces, audit=fake_audit)


@pytest.fixture
def owner_id():
    return uuid4()


class TestCreateWorkspace:
    @pytest.mark.asyncio
    async def test_create_assigns_owner_role(
        self, workspace_service, owner_id
    ) -> None:
        workspace, role = await workspace_service.create_workspace(
            name="My Project",
            owner_id=owner_id,
            ip_address="10.0.0.1",
            user_agent="TestUA",
        )
        assert workspace.name == "My Project"
        assert role == WorkspaceRole.OWNER


class TestRenameWorkspace:
    @pytest.mark.asyncio
    async def test_owner_can_rename(
        self, workspace_service, owner_id
    ) -> None:
        workspace, _ = await workspace_service.create_workspace(
            name="Old Name",
            owner_id=owner_id,
            ip_address=None,
            user_agent=None,
        )
        renamed = await workspace_service.rename_workspace(
            workspace_id=workspace.id,
            user_id=owner_id,
            name="New Name",
            ip_address=None,
            user_agent=None,
        )
        assert renamed.name == "New Name"

    @pytest.mark.asyncio
    async def test_non_member_cannot_rename(self, workspace_service) -> None:
        owner = uuid4()
        stranger = uuid4()
        workspace, _ = await workspace_service.create_workspace(
            name="Private",
            owner_id=owner,
            ip_address=None,
            user_agent=None,
        )
        with pytest.raises(AuthorizationError, match="Insufficient"):
            await workspace_service.rename_workspace(
                workspace_id=workspace.id,
                user_id=stranger,
                name="Hacked",
                ip_address=None,
                user_agent=None,
            )

    @pytest.mark.asyncio
    async def test_viewer_cannot_rename(
        self, workspace_service, fake_workspaces
    ) -> None:
        owner = uuid4()
        viewer = uuid4()
        workspace, _ = await workspace_service.create_workspace(
            name="ViewOnly",
            owner_id=owner,
            ip_address=None,
            user_agent=None,
        )
        await fake_workspaces.add_member(
            workspace_id=workspace.id,
            user_id=viewer,
            role=WorkspaceRole.VIEWER,
        )
        with pytest.raises(AuthorizationError, match="Insufficient"):
            await workspace_service.rename_workspace(
                workspace_id=workspace.id,
                user_id=viewer,
                name="NotAllowed",
                ip_address=None,
                user_agent=None,
            )

    @pytest.mark.asyncio
    async def test_admin_can_rename(
        self, workspace_service, fake_workspaces
    ) -> None:
        owner = uuid4()
        admin = uuid4()
        workspace, _ = await workspace_service.create_workspace(
            name="AdminTest",
            owner_id=owner,
            ip_address=None,
            user_agent=None,
        )
        await fake_workspaces.add_member(
            workspace_id=workspace.id,
            user_id=admin,
            role=WorkspaceRole.ADMIN,
        )
        renamed = await workspace_service.rename_workspace(
            workspace_id=workspace.id,
            user_id=admin,
            name="Renamed",
            ip_address=None,
            user_agent=None,
        )
        assert renamed.name == "Renamed"

    @pytest.mark.asyncio
    async def test_rename_nonexistent_workspace_raises(
        self, workspace_service, fake_workspaces
    ) -> None:
        owner = uuid4()
        ws_id = uuid4()
        # Add membership for a workspace that doesn't exist in the store
        from forge_api.domain.workspaces import MembershipRecord

        fake_workspaces._memberships.append(
            MembershipRecord(
                workspace_id=ws_id,
                user_id=owner,
                role=WorkspaceRole.OWNER,
                created_at=datetime.now(UTC),
            )
        )
        with pytest.raises(NotFoundError, match="not found"):
            await workspace_service.rename_workspace(
                workspace_id=ws_id,
                user_id=owner,
                name="Nope",
                ip_address=None,
                user_agent=None,
            )


class TestListWorkspaces:
    @pytest.mark.asyncio
    async def test_list_returns_user_workspaces(
        self, workspace_service, owner_id
    ) -> None:
        await workspace_service.create_workspace(
            name="WS1", owner_id=owner_id, ip_address=None, user_agent=None
        )
        await workspace_service.create_workspace(
            name="WS2", owner_id=owner_id, ip_address=None, user_agent=None
        )
        results = await workspace_service.list_workspaces(owner_id)
        assert len(results) == 2
        names = {w.name for w, _ in results}
        assert names == {"WS1", "WS2"}

    @pytest.mark.asyncio
    async def test_list_excludes_other_users(
        self, workspace_service, owner_id
    ) -> None:
        await workspace_service.create_workspace(
            name="MyWS", owner_id=owner_id, ip_address=None, user_agent=None
        )
        stranger = uuid4()
        results = await workspace_service.list_workspaces(stranger)
        assert len(results) == 0


class TestAuditIntegration:
    @pytest.mark.asyncio
    async def test_create_emits_audit(
        self, workspace_service, fake_audit, owner_id
    ) -> None:
        await workspace_service.create_workspace(
            name="Audited", owner_id=owner_id, ip_address="1.2.3.4", user_agent="UA"
        )
        assert any(
            e.get("event")
            and hasattr(e["event"], "value")
            and e["event"].value == "workspace.created"
            for e in fake_audit.events
        )

    @pytest.mark.asyncio
    async def test_rename_emits_audit(
        self, workspace_service, fake_audit, owner_id
    ) -> None:
        ws, _ = await workspace_service.create_workspace(
            name="Before", owner_id=owner_id, ip_address=None, user_agent=None
        )
        await workspace_service.rename_workspace(
            workspace_id=ws.id,
            user_id=owner_id,
            name="After",
            ip_address="1.2.3.4",
            user_agent="UA",
        )
        assert any(
            e.get("event")
            and hasattr(e["event"], "value")
            and e["event"].value == "workspace.renamed"
            for e in fake_audit.events
        )
