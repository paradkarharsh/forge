"""Unit tests for the deterministic PolicyEngine and RBAC matrix."""
import pytest

from forge_api.application.tools.policy_engine import PolicyEngine
from forge_api.domain.auth import WorkspaceRole
from forge_api.infrastructure.tools.default_registry import (
    create_default_tool_registry,
)


@pytest.fixture
def policy_engine() -> PolicyEngine:
    return PolicyEngine()


@pytest.fixture
def tools():
    registry = create_default_tool_registry()
    return {t.name: t for t in registry.list_tools(enabled_only=False)}


class TestPolicyEngineViewer:
    """VIEWER role: Read-only tools permitted; all writes, git commits, and terminal denied."""

    @pytest.mark.parametrize(
        "tool_name",
        [
            "repository.list_files",
            "repository.read_file",
            "repository.search",
            "code.search_symbol",
            "code.find_references",
            "git.status",
            "git.diff",
        ],
    )
    def test_viewer_allowed_read_tools(
        self, policy_engine: PolicyEngine, tools, tool_name: str
    ) -> None:
        decision = policy_engine.authorize(WorkspaceRole.VIEWER, tools[tool_name])
        assert decision.allowed is True
        assert decision.requires_approval is False

    @pytest.mark.parametrize(
        "tool_name",
        [
            "file.create",
            "file.modify",
            "file.delete",
            "git.commit",
            "terminal.execute",
        ],
    )
    def test_viewer_denied_write_and_execution_tools(
        self, policy_engine: PolicyEngine, tools, tool_name: str
    ) -> None:
        decision = policy_engine.authorize(WorkspaceRole.VIEWER, tools[tool_name])
        assert decision.allowed is False
        assert decision.requires_approval is False
        assert decision.reason is not None


class TestPolicyEngineDeveloper:
    """DEVELOPER role: Read tools permitted, Controlled Writes with approval;
    NO terminal, NO git commit.
    """

    @pytest.mark.parametrize(
        "tool_name",
        [
            "repository.list_files",
            "repository.read_file",
            "repository.search",
            "code.search_symbol",
            "code.find_references",
            "git.status",
            "git.diff",
        ],
    )
    def test_developer_allowed_read_tools(
        self, policy_engine: PolicyEngine, tools, tool_name: str
    ) -> None:
        decision = policy_engine.authorize(WorkspaceRole.DEVELOPER, tools[tool_name])
        assert decision.allowed is True
        assert decision.requires_approval is False

    @pytest.mark.parametrize(
        "tool_name",
        [
            "file.create",
            "file.modify",
            "file.delete",
        ],
    )
    def test_developer_requires_approval_for_writes(
        self, policy_engine: PolicyEngine, tools, tool_name: str
    ) -> None:
        decision = policy_engine.authorize(WorkspaceRole.DEVELOPER, tools[tool_name])
        assert decision.allowed is True
        assert decision.requires_approval is True

    @pytest.mark.parametrize(
        "tool_name",
        [
            "git.commit",
            "terminal.execute",
        ],
    )
    def test_developer_denied_commit_and_terminal(
        self, policy_engine: PolicyEngine, tools, tool_name: str
    ) -> None:
        decision = policy_engine.authorize(WorkspaceRole.DEVELOPER, tools[tool_name])
        assert decision.allowed is False
        assert decision.requires_approval is False

    def test_legacy_member_role_matches_developer(
        self, policy_engine: PolicyEngine, tools
    ) -> None:
        # MEMBER role alias behaves identically to DEVELOPER
        dec_read = policy_engine.authorize(WorkspaceRole.MEMBER, tools["repository.read_file"])
        assert dec_read.allowed is True
        assert dec_read.requires_approval is False

        dec_write = policy_engine.authorize(WorkspaceRole.MEMBER, tools["file.create"])
        assert dec_write.allowed is True
        assert dec_write.requires_approval is True

        dec_term = policy_engine.authorize(WorkspaceRole.MEMBER, tools["terminal.execute"])
        assert dec_term.allowed is False


class TestPolicyEngineMaintainer:
    """MAINTAINER role: Read tools, Write tools, git.commit (approval),
    terminal.execute (approval).
    """


    @pytest.mark.parametrize(
        "tool_name",
        [
            "repository.list_files",
            "repository.read_file",
            "repository.search",
            "code.search_symbol",
            "code.find_references",
            "git.status",
            "git.diff",
            "file.create",
            "file.modify",
            "file.delete",
        ],
    )
    def test_maintainer_allowed_read_and_write_tools(
        self, policy_engine: PolicyEngine, tools, tool_name: str
    ) -> None:
        decision = policy_engine.authorize(WorkspaceRole.MAINTAINER, tools[tool_name])
        assert decision.allowed is True
        assert decision.requires_approval is False

    @pytest.mark.parametrize(
        "tool_name",
        [
            "git.commit",
            "terminal.execute",
        ],
    )
    def test_maintainer_requires_approval_for_high_risk(
        self, policy_engine: PolicyEngine, tools, tool_name: str
    ) -> None:
        decision = policy_engine.authorize(WorkspaceRole.MAINTAINER, tools[tool_name])
        assert decision.allowed is True
        assert decision.requires_approval is True


class TestPolicyEngineAdminAndOwner:
    """ADMIN & OWNER roles: All tools authorized; high-risk tools still require approval."""

    @pytest.mark.parametrize("role", [WorkspaceRole.ADMIN, WorkspaceRole.OWNER])
    @pytest.mark.parametrize(
        "tool_name",
        [
            "repository.list_files",
            "repository.read_file",
            "repository.search",
            "code.search_symbol",
            "code.find_references",
            "git.status",
            "git.diff",
            "file.create",
            "file.modify",
            "file.delete",
        ],
    )
    def test_admin_and_owner_preapproved_tools(
        self, policy_engine: PolicyEngine, tools, role: WorkspaceRole, tool_name: str
    ) -> None:
        decision = policy_engine.authorize(role, tools[tool_name])
        assert decision.allowed is True
        assert decision.requires_approval is False

    @pytest.mark.parametrize("role", [WorkspaceRole.ADMIN, WorkspaceRole.OWNER])
    @pytest.mark.parametrize(
        "tool_name",
        [
            "git.commit",
            "terminal.execute",
        ],
    )
    def test_admin_and_owner_risk_approval_required(
        self, policy_engine: PolicyEngine, tools, role: WorkspaceRole, tool_name: str
    ) -> None:
        decision = policy_engine.authorize(role, tools[tool_name])
        assert decision.allowed is True
        assert decision.requires_approval is True
