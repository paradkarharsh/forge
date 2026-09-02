"""Deterministic policy engine for agent tool authorization and approval gating."""
from dataclasses import dataclass
from typing import Any

from forge_api.domain.auth import WorkspaceRole
from forge_api.domain.tool import RiskLevel, Tool, ToolCategory


@dataclass(frozen=True, slots=True)
class PolicyDecision:
    """Outcome of policy evaluation for a specific tool invocation."""

    allowed: bool
    requires_approval: bool
    reason: str | None = None


class PolicyEngine:
    """Authoritative, deterministic policy evaluator for agent tool execution.

    Implements the approved Forge RBAC role-to-tool matrix:
    - OWNER: All tools authorized; risk policies apply for high-risk operations.
    - ADMIN: All tools authorized; risk policies apply for high-risk operations.
    - MAINTAINER: Read tools, Controlled Write tools, git.commit (approval),
      terminal.execute (approval).
    - DEVELOPER: Read tools, Controlled Write tools (approval required). No
      terminal execution, no git commit.
    - VIEWER: Read-only tools only. No write, no git mutation, no terminal execution.
    """

    def authorize(
        self,
        role: WorkspaceRole | str,
        tool: Tool,
        arguments: dict[str, Any] | None = None,
    ) -> PolicyDecision:
        """Evaluate if the given workspace role is authorized to execute the tool."""
        role_enum = (
            WorkspaceRole(role) if isinstance(role, str) else role
        )

        # 1. VIEWER: Read-only tools only
        if role_enum == WorkspaceRole.VIEWER:
            is_read_tool = (
                tool.risk_level == RiskLevel.READ_ONLY
                or tool.category in (ToolCategory.REPOSITORY, ToolCategory.CODE)
                or tool.name in ("git.status", "git.diff")
            )
            is_mutation_or_terminal = (
                tool.category == ToolCategory.FILE
                or tool.name in ("terminal.execute", "git.commit")
            )
            if is_read_tool and not is_mutation_or_terminal:
                return PolicyDecision(allowed=True, requires_approval=False)
            return PolicyDecision(
                allowed=False,
                requires_approval=False,
                reason="VIEWER role cannot perform write, git commit, or terminal operations.",
            )

        # 2. DEVELOPER (and legacy MEMBER alias): Read + Write (approval); no terminal, no commit
        if role_enum in (WorkspaceRole.DEVELOPER, WorkspaceRole.MEMBER):
            if tool.name == "terminal.execute" or tool.category == ToolCategory.TERMINAL:
                return PolicyDecision(
                    allowed=False,
                    requires_approval=False,
                    reason="DEVELOPER role is not permitted to execute terminal commands.",
                )
            if tool.name == "git.commit":
                return PolicyDecision(
                    allowed=False,
                    requires_approval=False,
                    reason="DEVELOPER role is not permitted to create git commits directly.",
                )
            if tool.category == ToolCategory.FILE:
                # Controlled file writes are allowed for developers with mandatory approval
                return PolicyDecision(
                    allowed=True,
                    requires_approval=True,
                    reason="File write operations require human approval for DEVELOPER role.",
                )
            # Read-only tools
            if tool.risk_level == RiskLevel.READ_ONLY:
                return PolicyDecision(allowed=True, requires_approval=False)
            # Any other tool
            requires_appr = tool.risk_level in (RiskLevel.HIGH, RiskLevel.CRITICAL)
            return PolicyDecision(allowed=True, requires_approval=requires_appr)

        # 3. MAINTAINER: Read tools + Write tools + git.commit (approval)
        #    + terminal.execute (approval)
        if role_enum == WorkspaceRole.MAINTAINER:

            if tool.name == "terminal.execute":
                return PolicyDecision(
                    allowed=True,
                    requires_approval=True,
                    reason="Terminal execution requires human approval.",
                )
            if tool.name == "git.commit":
                return PolicyDecision(
                    allowed=True,
                    requires_approval=True,
                    reason="Git commit operations require human approval.",
                )
            if tool.category == ToolCategory.FILE:
                return PolicyDecision(allowed=True, requires_approval=False)
            if tool.risk_level in (RiskLevel.HIGH, RiskLevel.CRITICAL):
                return PolicyDecision(allowed=True, requires_approval=True)
            return PolicyDecision(allowed=True, requires_approval=False)

        # 4. ADMIN & OWNER: All tools authorized; high-risk operations still require approval
        if role_enum in (WorkspaceRole.ADMIN, WorkspaceRole.OWNER):
            if tool.name == "terminal.execute":
                return PolicyDecision(
                    allowed=True,
                    requires_approval=True,
                    reason="Terminal execution requires human approval.",
                )
            if tool.name == "git.commit":
                return PolicyDecision(
                    allowed=True,
                    requires_approval=True,
                    reason="Git commit operations require human approval.",
                )
            if tool.risk_level in (RiskLevel.HIGH, RiskLevel.CRITICAL):
                return PolicyDecision(allowed=True, requires_approval=True)
            return PolicyDecision(allowed=True, requires_approval=False)

        # Fallback default deny
        return PolicyDecision(
            allowed=False,
            requires_approval=False,
            reason=f"Role '{role_enum.value}' is not recognized.",
        )
