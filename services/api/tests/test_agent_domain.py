"""Unit tests for FP8 agent domain models, state machine, approval hashing, and limits."""
import dataclasses
from datetime import UTC, datetime
from uuid import uuid4

import pytest

from forge_api.domain.agent import (
    TERMINAL_AGENT_STATUSES,
    VALID_AGENT_STATUS_TRANSITIONS,
    AgentLimits,
    AgentSessionRecord,
    AgentStatus,
    AgentStepRecord,
    AgentToolCallRecord,
    ExecutionMetrics,
    StepStatus,
    ToolCallStatus,
    is_terminal_agent_status,
    is_valid_agent_transition,
    validate_agent_transition,
)
from forge_api.domain.approval import (
    AgentApprovalRecord,
    ApprovalStatus,
    compute_arguments_hash,
)
from forge_api.domain.errors import DomainError
from forge_api.domain.tool import (
    RiskLevel,
    ToolCategory,
    ToolExecutionContext,
    ToolResult,
)

# ─── Domain Records Tests ─────────────────────────────────────────────


class TestAgentDomainRecords:
    def test_agent_limits_defaults(self) -> None:
        limits = AgentLimits()
        assert limits.max_wall_time_seconds == 900
        assert limits.max_llm_calls == 30
        assert limits.max_tool_calls == 50
        assert limits.max_output_bytes == 65_536
        assert limits.max_observation_bytes == 8_192

    def test_agent_limits_is_frozen(self) -> None:
        limits = AgentLimits()
        with pytest.raises(dataclasses.FrozenInstanceError):
            limits.max_llm_calls = 50  # type: ignore[misc]

    def test_execution_metrics_defaults(self) -> None:
        metrics = ExecutionMetrics()
        assert metrics.total_llm_calls == 0
        assert metrics.total_tool_calls == 0
        assert metrics.total_input_tokens == 0
        assert metrics.total_output_tokens == 0
        assert metrics.wall_time_seconds == 0.0
        assert metrics.estimated_cost_usd == 0.0

    def test_agent_session_record_creation_and_immutability(self) -> None:
        session_id = uuid4()
        workspace_id = uuid4()
        user_id = uuid4()
        now = datetime.now(UTC)

        session = AgentSessionRecord(
            id=session_id,
            workspace_id=workspace_id,
            user_id=user_id,
            objective="Implement feature pack 8",
            status=AgentStatus.CREATED,
            created_at=now,
        )

        assert session.id == session_id
        assert session.workspace_id == workspace_id
        assert session.user_id == user_id
        assert session.objective == "Implement feature pack 8"
        assert session.status == AgentStatus.CREATED
        assert session.current_step == 0
        assert session.limits.max_wall_time_seconds == 900
        assert session.metrics.total_llm_calls == 0
        assert session.created_at == now
        assert session.deleted_at is None

        with pytest.raises(dataclasses.FrozenInstanceError):
            session.status = AgentStatus.RUNNING  # type: ignore[misc]

    def test_agent_step_record_creation(self) -> None:
        step_id = uuid4()
        session_id = uuid4()
        now = datetime.now(UTC)

        step = AgentStepRecord(
            id=step_id,
            session_id=session_id,
            sequence=1,
            objective="Inspect repository files",
            status=StepStatus.PENDING,
            created_at=now,
        )

        assert step.id == step_id
        assert step.session_id == session_id
        assert step.sequence == 1
        assert step.status == StepStatus.PENDING

    def test_agent_tool_call_record_creation(self) -> None:
        call_id = uuid4()
        session_id = uuid4()
        now = datetime.now(UTC)

        call = AgentToolCallRecord(
            id=call_id,
            session_id=session_id,
            tool_name="repository.read_file",
            arguments={"path": "src/main.py"},
            risk_level=RiskLevel.READ_ONLY,
            status=ToolCallStatus.RUNNING,
            created_at=now,
        )

        assert call.id == call_id
        assert call.tool_name == "repository.read_file"
        assert call.arguments == {"path": "src/main.py"}
        assert call.risk_level == RiskLevel.READ_ONLY
        assert call.status == ToolCallStatus.RUNNING

    def test_agent_approval_record_creation(self) -> None:
        approval_id = uuid4()
        session_id = uuid4()
        call_id = uuid4()
        now = datetime.now(UTC)

        approval = AgentApprovalRecord(
            id=approval_id,
            session_id=session_id,
            tool_call_id=call_id,
            tool_name="file.modify",
            arguments_hash="abc123hash",
            status=ApprovalStatus.PENDING,
            requested_at=now,
        )

        assert approval.id == approval_id
        assert approval.tool_name == "file.modify"
        assert approval.arguments_hash == "abc123hash"
        assert approval.status == ApprovalStatus.PENDING


# ─── State Machine Tests ──────────────────────────────────────────────


class TestAgentStateMachine:
    def test_terminal_statuses_set(self) -> None:
        expected_terminals = {
            AgentStatus.COMPLETED,
            AgentStatus.FAILED,
            AgentStatus.CANCELLED,
            AgentStatus.TIMED_OUT,
            AgentStatus.EXPIRED,
        }
        assert TERMINAL_AGENT_STATUSES == expected_terminals

    def test_is_terminal_agent_status(self) -> None:
        for status in TERMINAL_AGENT_STATUSES:
            assert is_terminal_agent_status(status) is True

        non_terminals = [
            AgentStatus.CREATED,
            AgentStatus.PLANNING,
            AgentStatus.RUNNING,
            AgentStatus.WAITING_FOR_APPROVAL,
        ]
        for status in non_terminals:
            assert is_terminal_agent_status(status) is False

    @pytest.mark.parametrize(
        ("current", "target"),
        [
            # From CREATED
            (AgentStatus.CREATED, AgentStatus.PLANNING),
            (AgentStatus.CREATED, AgentStatus.CANCELLED),
            # From PLANNING
            (AgentStatus.PLANNING, AgentStatus.RUNNING),
            (AgentStatus.PLANNING, AgentStatus.FAILED),
            (AgentStatus.PLANNING, AgentStatus.CANCELLED),
            # From RUNNING
            (AgentStatus.RUNNING, AgentStatus.WAITING_FOR_APPROVAL),
            (AgentStatus.RUNNING, AgentStatus.COMPLETED),
            (AgentStatus.RUNNING, AgentStatus.FAILED),
            (AgentStatus.RUNNING, AgentStatus.CANCELLED),
            (AgentStatus.RUNNING, AgentStatus.TIMED_OUT),
            # From WAITING_FOR_APPROVAL
            (AgentStatus.WAITING_FOR_APPROVAL, AgentStatus.RUNNING),
            (AgentStatus.WAITING_FOR_APPROVAL, AgentStatus.CANCELLED),
            (AgentStatus.WAITING_FOR_APPROVAL, AgentStatus.TIMED_OUT),
            (AgentStatus.WAITING_FOR_APPROVAL, AgentStatus.EXPIRED),
        ],
    )
    def test_valid_transitions_pass(
        self, current: AgentStatus, target: AgentStatus
    ) -> None:
        assert is_valid_agent_transition(current, target) is True
        # validate_agent_transition should not raise
        validate_agent_transition(current, target)

    @pytest.mark.parametrize(
        ("current", "target"),
        [
            # Invalid from CREATED
            (AgentStatus.CREATED, AgentStatus.RUNNING),
            (AgentStatus.CREATED, AgentStatus.COMPLETED),
            (AgentStatus.CREATED, AgentStatus.FAILED),
            (AgentStatus.CREATED, AgentStatus.WAITING_FOR_APPROVAL),
            # Invalid from PLANNING
            (AgentStatus.PLANNING, AgentStatus.COMPLETED),
            (AgentStatus.PLANNING, AgentStatus.WAITING_FOR_APPROVAL),
            # Invalid from WAITING_FOR_APPROVAL
            (AgentStatus.WAITING_FOR_APPROVAL, AgentStatus.PLANNING),
            (AgentStatus.WAITING_FOR_APPROVAL, AgentStatus.COMPLETED),
            # Invalid from TERMINAL states (no transitions allowed)
            (AgentStatus.COMPLETED, AgentStatus.RUNNING),
            (AgentStatus.COMPLETED, AgentStatus.CREATED),
            (AgentStatus.FAILED, AgentStatus.RUNNING),
            (AgentStatus.FAILED, AgentStatus.PLANNING),
            (AgentStatus.CANCELLED, AgentStatus.RUNNING),
            (AgentStatus.TIMED_OUT, AgentStatus.RUNNING),
            (AgentStatus.EXPIRED, AgentStatus.RUNNING),
        ],
    )
    def test_invalid_transitions_fail(
        self, current: AgentStatus, target: AgentStatus
    ) -> None:
        assert is_valid_agent_transition(current, target) is False
        with pytest.raises(DomainError) as exc_info:
            validate_agent_transition(current, target)
        assert exc_info.value.code == "invalid_state_transition"
        assert f"'{current.value}'" in str(exc_info.value)
        assert f"'{target.value}'" in str(exc_info.value)

    def test_terminal_states_have_no_outbound_transitions(self) -> None:
        for status in TERMINAL_AGENT_STATUSES:
            assert VALID_AGENT_STATUS_TRANSITIONS[status] == frozenset()


# ─── Approval Hashing Tests ───────────────────────────────────────────


class TestApprovalHashing:
    def test_hash_determinism(self) -> None:
        args = {"path": "src/app.py", "content": "print('hello')"}
        hash1 = compute_arguments_hash(args)
        hash2 = compute_arguments_hash(args)
        assert hash1 == hash2
        assert len(hash1) == 64  # SHA-256 hex digest length

    def test_hash_key_ordering_independence(self) -> None:
        args_a = {"z": 100, "a": "first", "m": [1, 2, 3]}
        args_b = {"a": "first", "m": [1, 2, 3], "z": 100}
        args_c = {"m": [1, 2, 3], "z": 100, "a": "first"}
        assert compute_arguments_hash(args_a) == compute_arguments_hash(args_b)
        assert compute_arguments_hash(args_b) == compute_arguments_hash(args_c)

    def test_hash_nested_key_ordering_independence(self) -> None:
        args_a = {"config": {"retries": 3, "timeout": 30}}
        args_b = {"config": {"timeout": 30, "retries": 3}}
        assert compute_arguments_hash(args_a) == compute_arguments_hash(args_b)

    def test_hash_modification_detection(self) -> None:
        base = {"path": "src/app.py", "content": "print('hello')"}
        mutated_val = {"path": "src/app.py", "content": "print('world')"}
        mutated_path = {"path": "src/main.py", "content": "print('hello')"}
        extra_key = {"path": "src/app.py", "content": "print('hello')", "force": True}

        h_base = compute_arguments_hash(base)
        assert h_base != compute_arguments_hash(mutated_val)
        assert h_base != compute_arguments_hash(mutated_path)
        assert h_base != compute_arguments_hash(extra_key)

    def test_hash_unicode_preservation(self) -> None:
        args_jp = {"message": "こんにちは世界", "emoji": "🚀"}
        h1 = compute_arguments_hash(args_jp)
        h2 = compute_arguments_hash(args_jp)
        assert h1 == h2
        assert len(h1) == 64


# ─── Tool Concepts Tests ──────────────────────────────────────────────


class TestToolConcepts:
    def test_tool_category_enum(self) -> None:
        categories = {c.value for c in ToolCategory}
        assert "repository" in categories
        assert "code" in categories
        assert "file" in categories
        assert "git" in categories
        assert "terminal" in categories
        assert "memory" in categories

    def test_risk_level_enum(self) -> None:
        levels = {r.value for r in RiskLevel}
        assert "read_only" in levels
        assert "low" in levels
        assert "medium" in levels
        assert "high" in levels
        assert "critical" in levels

    def test_tool_execution_context(self) -> None:
        workspace_id = uuid4()
        user_id = uuid4()
        session_id = uuid4()

        ctx = ToolExecutionContext(
            workspace_id=workspace_id,
            repository_id=None,
            user_id=user_id,
            session_id=session_id,
            timeout_seconds=45.0,
        )
        assert ctx.workspace_id == workspace_id
        assert ctx.timeout_seconds == 45.0

    def test_tool_result(self) -> None:
        res = ToolResult(
            success=True,
            output="File created successfully.",
            data={"bytes_written": 42},
        )
        assert res.success is True
        assert res.output == "File created successfully."
        assert res.data["bytes_written"] == 42
        assert res.error is None


# ─── Migration Structure Tests ────────────────────────────────────────


class TestMigrationStructure:
    def test_migration_0008_attributes(self) -> None:
        import importlib.util
        from pathlib import Path

        migration_path = (
            Path(__file__).parent.parent
            / "alembic"
            / "versions"
            / "0008_agent_engine.py"
        )
        assert migration_path.exists(), f"Migration file not found at {migration_path}"

        spec = importlib.util.spec_from_file_location("migration_0008", migration_path)
        assert spec is not None
        assert spec.loader is not None
        migration_0008 = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(migration_0008)

        assert migration_0008.revision == "0008_agent_engine"
        assert migration_0008.down_revision == "0007_llm_context"
        assert callable(migration_0008.upgrade)
        assert callable(migration_0008.downgrade)


# ─── Repository Ports & Protocol Tests ─────────────────────────────────


class TestProtocolsAndPorts:
    def test_tool_protocol_runtime_checkable(self) -> None:
        from forge_api.domain.tool import Tool

        class MockTool:
            @property
            def name(self) -> str:
                return "mock.tool"

            @property
            def description(self) -> str:
                return "A mock tool for testing."

            @property
            def category(self) -> ToolCategory:
                return ToolCategory.REPOSITORY

            @property
            def risk_level(self) -> RiskLevel:
                return RiskLevel.READ_ONLY

            @property
            def input_schema(self) -> dict:
                return {"type": "object"}

            @property
            def output_schema(self) -> dict:
                return {"type": "object"}

            @property
            def enabled(self) -> bool:
                return True

            def validate(self, input_data: dict) -> dict:
                return input_data

            async def execute(
                self, context: ToolExecutionContext, input_data: dict
            ) -> ToolResult:
                return ToolResult(success=True, output="ok")

        mock = MockTool()
        assert isinstance(mock, Tool)

    def test_repository_ports_signatures(self) -> None:
        from forge_api.domain.repositories import (
            AgentApprovalRepository,
            AgentSessionRepository,
            AgentStepRepository,
            AgentToolCallRepository,
        )

        assert hasattr(AgentSessionRepository, "get")
        assert hasattr(AgentSessionRepository, "list_by_workspace")
        assert hasattr(AgentSessionRepository, "count_by_workspace")
        assert hasattr(AgentSessionRepository, "create")
        assert hasattr(AgentSessionRepository, "update_status")
        assert hasattr(AgentSessionRepository, "update_metrics")
        assert hasattr(AgentSessionRepository, "soft_delete")

        assert hasattr(AgentStepRepository, "get")
        assert hasattr(AgentStepRepository, "list_by_session")
        assert hasattr(AgentStepRepository, "create")
        assert hasattr(AgentStepRepository, "update_status")

        assert hasattr(AgentToolCallRepository, "get")
        assert hasattr(AgentToolCallRepository, "list_by_session")
        assert hasattr(AgentToolCallRepository, "create")
        assert hasattr(AgentToolCallRepository, "complete")

        assert hasattr(AgentApprovalRepository, "get")
        assert hasattr(AgentApprovalRepository, "get_by_tool_call")
        assert hasattr(AgentApprovalRepository, "list_pending_by_session")
        assert hasattr(AgentApprovalRepository, "create")
        assert hasattr(AgentApprovalRepository, "decide")



