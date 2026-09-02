"""Comprehensive unit and flow tests for AgentOrchestrator."""
import json
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest

from forge_api.application.agent.orchestrator import AgentOrchestrator
from forge_api.application.llm.gateway import LLMGateway
from forge_api.application.llm.prompt_builder import PromptBuilder
from forge_api.application.tools.policy_engine import PolicyEngine
from forge_api.application.tools.tool_registry import ToolRegistry
from forge_api.domain.agent import (
    AgentEventType,
    AgentLimits,
    AgentSessionRecord,
    AgentStatus,
    AgentStepRecord,
    AgentToolCallRecord,
    ExecutionMetrics,
    RiskLevel,
    StepStatus,
    ToolCallStatus,
)
from forge_api.domain.approval import (
    AgentApprovalRecord,
    ApprovalStatus,
    compute_arguments_hash,
)
from forge_api.domain.auth import WorkspaceRole
from forge_api.domain.errors import DomainError, ValidationError
from forge_api.domain.llm import (
    ChatRequest,
    ChatResponse,
    FinishReason,
    LLMProviderType,
    ModelCapabilities,
    ModelSpec,
    TokenUsage,
)
from forge_api.domain.memory import ContextEntry, ContextSource, ContextWindow, MemoryScope
from forge_api.domain.tool import (
    ToolCategory,
    ToolExecutionContext,
    ToolResult,
)
from forge_api.domain.workspaces import MembershipRecord
from forge_api.infrastructure.agent.event_publisher import (
    InMemoryAgentEventPublisher,
)
from forge_api.infrastructure.llm import FakeLLMProvider, FakeProviderConfig
from forge_api.infrastructure.llm.model_registry import ModelRegistry

# ─── In-Memory Repositories for Isolated Testing ──────────────────────


class InMemoryAgentSessionRepository:
    def __init__(self) -> None:
        self.sessions: dict[UUID, AgentSessionRecord] = {}

    async def get(self, session_id: UUID) -> AgentSessionRecord | None:
        return self.sessions.get(session_id)

    async def list_by_workspace(self, workspace_id: UUID, **kwargs) -> list[AgentSessionRecord]:
        return [s for s in self.sessions.values() if s.workspace_id == workspace_id]

    async def create(
        self,
        *,
        workspace_id: UUID,
        user_id: UUID,
        objective: str,
        status: AgentStatus = AgentStatus.CREATED,
        repository_id: UUID | None = None,
        conversation_id: UUID | None = None,
        model: str | None = None,
        limits: AgentLimits | None = None,
        metrics: ExecutionMetrics | None = None,
        metadata: dict | None = None,
    ) -> AgentSessionRecord:
        record = AgentSessionRecord(
            id=uuid4(),
            workspace_id=workspace_id,
            user_id=user_id,
            objective=objective,
            status=status,
            created_at=datetime.now(UTC),
            repository_id=repository_id,
            conversation_id=conversation_id,
            model=model,
            limits=limits or AgentLimits(),
            metrics=metrics or ExecutionMetrics(),
            metadata=metadata or {},
        )
        self.sessions[record.id] = record
        return record

    async def update_status(
        self,
        session_id: UUID,
        status: AgentStatus,
        *,
        started_at: datetime | None = None,
        completed_at: datetime | None = None,
        cancelled_at: datetime | None = None,
    ) -> AgentSessionRecord | None:
        rec = self.sessions.get(session_id)
        if not rec:
            return None
        updated = AgentSessionRecord(
            id=rec.id,
            workspace_id=rec.workspace_id,
            user_id=rec.user_id,
            objective=rec.objective,
            status=status,
            created_at=rec.created_at,
            repository_id=rec.repository_id,
            conversation_id=rec.conversation_id,
            model=rec.model,
            limits=rec.limits,
            metrics=rec.metrics,
            current_step=rec.current_step,
            started_at=started_at or rec.started_at,
            completed_at=completed_at or rec.completed_at,
            cancelled_at=cancelled_at or rec.cancelled_at,
            metadata=rec.metadata,
        )
        self.sessions[session_id] = updated
        return updated

    async def update_metrics(
        self,
        session_id: UUID,
        metrics: ExecutionMetrics,
        *,
        current_step: int | None = None,
    ) -> AgentSessionRecord | None:
        rec = self.sessions.get(session_id)
        if not rec:
            return None
        updated = AgentSessionRecord(
            id=rec.id,
            workspace_id=rec.workspace_id,
            user_id=rec.user_id,
            objective=rec.objective,
            status=rec.status,
            created_at=rec.created_at,
            repository_id=rec.repository_id,
            conversation_id=rec.conversation_id,
            model=rec.model,
            limits=rec.limits,
            metrics=metrics,
            current_step=current_step if current_step is not None else rec.current_step,
            started_at=rec.started_at,
            completed_at=rec.completed_at,
            cancelled_at=rec.cancelled_at,
            metadata=rec.metadata,
        )
        self.sessions[session_id] = updated
        return updated

    async def soft_delete(self, session_id: UUID) -> bool:
        return self.sessions.pop(session_id, None) is not None


class InMemoryAgentStepRepository:
    def __init__(self) -> None:
        self.steps: dict[UUID, AgentStepRecord] = {}

    async def get(self, step_id: UUID) -> AgentStepRecord | None:
        return self.steps.get(step_id)

    async def list_by_session(self, session_id: UUID) -> list[AgentStepRecord]:
        return [s for s in self.steps.values() if s.session_id == session_id]

    async def create(self, **kwargs) -> AgentStepRecord:
        record = AgentStepRecord(
            id=uuid4(),
            session_id=kwargs["session_id"],
            sequence=kwargs["sequence"],
            objective=kwargs["objective"],
            status=kwargs.get("status", StepStatus.PENDING),
            created_at=datetime.now(UTC),
            metadata=kwargs.get("metadata", {}),
        )
        self.steps[record.id] = record
        return record

    async def update_status(
        self, step_id: UUID, status: StepStatus, **kwargs
    ) -> AgentStepRecord | None:

        rec = self.steps.get(step_id)
        if not rec:
            return None
        updated = AgentStepRecord(
            id=rec.id,
            session_id=rec.session_id,
            sequence=rec.sequence,
            objective=rec.objective,
            status=status,
            created_at=rec.created_at,
            started_at=kwargs.get("started_at", rec.started_at),
            completed_at=kwargs.get("completed_at", rec.completed_at),
            metadata=rec.metadata,
        )
        self.steps[step_id] = updated
        return updated


class InMemoryAgentToolCallRepository:
    def __init__(self) -> None:
        self.calls: dict[UUID, AgentToolCallRecord] = {}

    async def get(self, tool_call_id: UUID) -> AgentToolCallRecord | None:
        return self.calls.get(tool_call_id)

    async def list_by_session(self, session_id: UUID, **kwargs) -> list[AgentToolCallRecord]:
        return [c for c in self.calls.values() if c.session_id == session_id]

    async def create(
        self,
        *,
        session_id: UUID,
        tool_name: str,
        arguments: dict,
        risk_level: RiskLevel,
        status: ToolCallStatus = ToolCallStatus.PENDING_APPROVAL,
        step_id: UUID | None = None,
        approval_id: UUID | None = None,
        metadata: dict | None = None,
    ) -> AgentToolCallRecord:
        record = AgentToolCallRecord(
            id=uuid4(),
            session_id=session_id,
            tool_name=tool_name,
            arguments=arguments,
            risk_level=risk_level,
            status=status,
            created_at=datetime.now(UTC),
            step_id=step_id,
            approval_id=approval_id,
            metadata=metadata or {},
        )
        self.calls[record.id] = record
        return record

    async def complete(
        self,
        tool_call_id: UUID,
        *,
        status: ToolCallStatus,
        output: str | None = None,
        error_message: str | None = None,
        duration_ms: float | None = None,
        completed_at: datetime | None = None,
    ) -> AgentToolCallRecord | None:
        rec = self.calls.get(tool_call_id)
        if not rec:
            return None
        updated = AgentToolCallRecord(
            id=rec.id,
            session_id=rec.session_id,
            tool_name=rec.tool_name,
            arguments=rec.arguments,
            risk_level=rec.risk_level,
            status=status,
            created_at=rec.created_at,
            step_id=rec.step_id,
            approval_id=rec.approval_id,
            output=output if output is not None else rec.output,
            error_message=error_message if error_message is not None else rec.error_message,
            duration_ms=duration_ms if duration_ms is not None else rec.duration_ms,
            started_at=rec.started_at,
            completed_at=completed_at or rec.completed_at,
            metadata=rec.metadata,
        )
        self.calls[tool_call_id] = updated
        return updated


class InMemoryAgentApprovalRepository:
    def __init__(self) -> None:
        self.approvals: dict[UUID, AgentApprovalRecord] = {}

    async def get(self, approval_id: UUID) -> AgentApprovalRecord | None:
        return self.approvals.get(approval_id)

    async def get_by_tool_call(self, tool_call_id: UUID) -> AgentApprovalRecord | None:
        for app in self.approvals.values():
            if app.tool_call_id == tool_call_id:
                return app
        return None

    async def list_pending_by_session(self, session_id: UUID) -> list[AgentApprovalRecord]:
        return [
            a
            for a in self.approvals.values()
            if a.session_id == session_id and a.status == ApprovalStatus.PENDING
        ]

    async def list_by_session(self, session_id: UUID) -> list[AgentApprovalRecord]:
        return [
            a
            for a in self.approvals.values()
            if a.session_id == session_id
        ]


    async def create(
        self,
        *,
        session_id: UUID,
        tool_call_id: UUID,
        tool_name: str,
        arguments_hash: str,
        requested_by: UUID | None = None,
        expires_at: datetime | None = None,
        metadata: dict | None = None,
    ) -> AgentApprovalRecord:
        record = AgentApprovalRecord(
            id=uuid4(),
            session_id=session_id,
            tool_call_id=tool_call_id,
            tool_name=tool_name,
            arguments_hash=arguments_hash,
            status=ApprovalStatus.PENDING,
            requested_at=datetime.now(UTC),
            requested_by=requested_by,
            expires_at=expires_at,
            metadata=metadata or {},
        )
        self.approvals[record.id] = record
        return record

    async def decide(
        self,
        approval_id: UUID,
        *,
        status: ApprovalStatus,
        decided_by: UUID,
        reason: str | None = None,
        decided_at: datetime | None = None,
    ) -> AgentApprovalRecord | None:
        rec = self.approvals.get(approval_id)
        if not rec:
            return None
        updated = AgentApprovalRecord(
            id=rec.id,
            session_id=rec.session_id,
            tool_call_id=rec.tool_call_id,
            tool_name=rec.tool_name,
            arguments_hash=rec.arguments_hash,
            status=status,
            requested_at=rec.requested_at,
            requested_by=rec.requested_by,
            decided_by=decided_by,
            reason=reason,
            decided_at=decided_at or datetime.now(UTC),
            expires_at=rec.expires_at,
            metadata=rec.metadata,
        )
        self.approvals[approval_id] = updated
        return updated


class MockWorkspaceRepository:
    def __init__(self, role: WorkspaceRole = WorkspaceRole.DEVELOPER) -> None:
        self.role = role

    async def get_membership(self, workspace_id: UUID, user_id: UUID):
        return MembershipRecord(
            workspace_id=workspace_id,
            user_id=user_id,
            role=self.role,
            created_at=datetime.now(UTC),
        )



class MockContextAssemblyService:
    async def assemble(self, **kwargs) -> ContextWindow:
        return ContextWindow(
            total_tokens=100,
            truncated=False,
            repository_id=None,
            workspace_id=uuid4(),
            assembled_at=datetime.now(UTC),
            entries=(
                ContextEntry(
                    source=ContextSource.MEMORY,
                    scope=MemoryScope.WORKSPACE,
                    content="Project uses Python 3.13 and FastAPI.",
                    relevance_score=0.9,
                    source_id=None,
                    file_path=None,
                    metadata={},
                ),
            ),
        )



class MockAuditLogger:
    def log(self, *args, **kwargs) -> None:
        pass


class MockTool:
    def __init__(
        self,
        name: str,
        category: ToolCategory = ToolCategory.REPOSITORY,
        risk_level: RiskLevel = RiskLevel.READ_ONLY,
        output: str = "Tool executed successfully.",
        success: bool = True,
    ) -> None:
        self._name = name
        self._category = category
        self._risk_level = risk_level
        self._output = output
        self._success = success
        self.call_count = 0

    @property
    def name(self) -> str:
        return self._name

    @property
    def description(self) -> str:
        return f"Mock tool {self._name}"

    @property
    def category(self) -> ToolCategory:
        return self._category

    @property
    def risk_level(self) -> RiskLevel:
        return self._risk_level

    @property
    def input_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {"param": {"type": "string"}},
            "required": ["param"],
        }

    @property
    def output_schema(self) -> dict:
        return {"type": "object"}

    @property
    def enabled(self) -> bool:
        return True

    def validate(self, input_data: dict) -> dict:
        if "param" not in input_data:
            raise ValidationError("Missing required field 'param'")
        return input_data

    async def execute(self, context: ToolExecutionContext, input_data: dict) -> ToolResult:
        self.call_count += 1
        return ToolResult(
            success=self._success,
            output=self._output,
            data={"result": "ok"},
        )


# ─── Test Fixture & Setup ─────────────────────────────────────────────


class SequentialFakeLLMProvider(FakeLLMProvider):
    """Returns responses in sequence for multi-turn conversations."""

    def __init__(self, sequence: list[str]) -> None:
        super().__init__()
        self._sequence = sequence
        self._seq_idx = 0

    async def complete(self, request: ChatRequest) -> ChatResponse:
        self._call_count += 1
        if self._seq_idx < len(self._sequence):
            resp_content = self._sequence[self._seq_idx]
            self._seq_idx += 1
        else:
            resp_content = self._sequence[-1]

        return ChatResponse(
            content=resp_content,
            finish_reason=FinishReason.STOP,
            usage=TokenUsage(input_tokens=15, output_tokens=25, total_tokens=40),
            model=request.model,
            provider="fake",
        )


def _tc_json(tool_name: str, args: dict) -> str:
    payload = {"type": "tool_call", "tool_name": tool_name, "arguments": args}
    return f"```json\n{json.dumps(payload)}\n```"


def _complete_json(reason: str) -> str:
    payload = {"type": "complete", "reason": reason}
    return f"```json\n{json.dumps(payload)}\n```"



@pytest.fixture
def test_env():
    sessions = InMemoryAgentSessionRepository()
    steps = InMemoryAgentStepRepository()
    tool_calls = InMemoryAgentToolCallRepository()
    approvals = InMemoryAgentApprovalRepository()
    events = InMemoryAgentEventPublisher()
    workspaces = MockWorkspaceRepository(role=WorkspaceRole.DEVELOPER)

    # Tools
    tool_reg = ToolRegistry()
    read_tool = MockTool(

        "repo.read", ToolCategory.REPOSITORY, RiskLevel.READ_ONLY, output="File content"
    )
    write_tool = MockTool(
        "file.create", ToolCategory.FILE, RiskLevel.MEDIUM, output="File created"
    )
    term_tool = MockTool(
        "terminal.execute", ToolCategory.TERMINAL, RiskLevel.HIGH, output="Tests passed"
    )

    tool_reg.register(read_tool)
    tool_reg.register(write_tool)
    tool_reg.register(term_tool)

    policy_engine = PolicyEngine()
    context_assembly = MockContextAssemblyService()
    prompt_builder = PromptBuilder()

    # Model registry
    registry = ModelRegistry(
        extra_models=[
            ModelSpec(
                provider=LLMProviderType.FAKE,
                model_id="fake/default",
                display_name="Fake Default",
                capabilities=ModelCapabilities(chat=True),
            )
        ]
    )


    return {
        "sessions": sessions,
        "steps": steps,
        "tool_calls": tool_calls,
        "approvals": approvals,
        "events": events,
        "workspaces": workspaces,
        "tool_reg": tool_reg,
        "policy_engine": policy_engine,
        "context_assembly": context_assembly,
        "prompt_builder": prompt_builder,
        "registry": registry,
        "read_tool": read_tool,
        "write_tool": write_tool,
        "term_tool": term_tool,
    }


def make_orchestrator(test_env, llm_provider, cancellation_checker=None):
    gateway = LLMGateway(
        registry=test_env["registry"],
        providers={"fake": llm_provider},
        audit=MockAuditLogger(),
    )
    return AgentOrchestrator(
        sessions=test_env["sessions"],
        steps=test_env["steps"],
        tool_calls=test_env["tool_calls"],
        approvals=test_env["approvals"],
        tool_registry=test_env["tool_reg"],
        policy_engine=test_env["policy_engine"],
        context_assembly=test_env["context_assembly"],
        prompt_builder=test_env["prompt_builder"],
        gateway=gateway,
        events=test_env["events"],
        workspaces=test_env["workspaces"],
        cancellation_checker=cancellation_checker,
    )


# ─── Orchestrator Tests ───────────────────────────────────────────────


class TestAgentOrchestratorFlows:
    @pytest.mark.asyncio
    async def test_direct_completion_without_tools(self, test_env) -> None:
        provider = SequentialFakeLLMProvider([
            _complete_json("Task finished without tools")
        ])
        orchestrator = make_orchestrator(test_env, provider)

        session = await test_env["sessions"].create(
            workspace_id=uuid4(),
            user_id=uuid4(),
            objective="Answer question",
            model="fake/default",
        )

        final_session = await orchestrator.run_session(session.id)
        assert final_session.status == AgentStatus.COMPLETED

        event_types = [e.event_type for e in test_env["events"].events]
        assert AgentEventType.STARTED in event_types
        assert AgentEventType.COMPLETED in event_types

    @pytest.mark.asyncio
    async def test_successful_single_tool_task(self, test_env) -> None:
        provider = SequentialFakeLLMProvider([
            _tc_json("repo.read", {"param": "src/app.py"}),
            _complete_json("Read app.py successfully"),
        ])
        orchestrator = make_orchestrator(test_env, provider)

        session = await test_env["sessions"].create(
            workspace_id=uuid4(),
            user_id=uuid4(),
            objective="Inspect app.py",
            model="fake/default",
        )

        final_session = await orchestrator.run_session(session.id)
        assert final_session.status == AgentStatus.COMPLETED
        assert final_session.metrics.total_llm_calls == 2
        assert final_session.metrics.total_tool_calls == 1

        calls = await test_env["tool_calls"].list_by_session(session.id)
        assert len(calls) == 1
        assert calls[0].tool_name == "repo.read"
        assert calls[0].status == ToolCallStatus.COMPLETED

    @pytest.mark.asyncio
    async def test_malformed_model_response_continues_loop(self, test_env) -> None:
        provider = SequentialFakeLLMProvider([
            "I am not returning JSON here, just plain text thinking.",
            _complete_json("Recovered from formatting error"),
        ])
        orchestrator = make_orchestrator(test_env, provider)

        session = await test_env["sessions"].create(
            workspace_id=uuid4(),
            user_id=uuid4(),
            objective="Test malformed parsing",
            model="fake/default",
        )

        final_session = await orchestrator.run_session(session.id)
        assert final_session.status == AgentStatus.COMPLETED
        assert final_session.metrics.total_llm_calls == 2

    @pytest.mark.asyncio
    async def test_unknown_tool_records_observation_without_execution(self, test_env) -> None:
        provider = SequentialFakeLLMProvider([
            _tc_json("nonexistent.tool", {"param": "foo"}),
            _complete_json("Stopped after error"),
        ])
        orchestrator = make_orchestrator(test_env, provider)

        session = await test_env["sessions"].create(
            workspace_id=uuid4(),
            user_id=uuid4(),
            objective="Run nonexistent tool",
            model="fake/default",
        )

        final_session = await orchestrator.run_session(session.id)
        assert final_session.status == AgentStatus.COMPLETED

        event_types = [e.event_type for e in test_env["events"].events]
        assert AgentEventType.TOOL_FAILED in event_types

    @pytest.mark.asyncio
    async def test_unauthorized_tool_policy_denial(self, test_env) -> None:
        # User role is DEVELOPER. Terminal execution is strictly forbidden for DEVELOPER.
        provider = SequentialFakeLLMProvider([
            _tc_json("terminal.execute", {"param": "pytest"}),
            _complete_json("Acknowledged denial"),
        ])
        orchestrator = make_orchestrator(test_env, provider)

        session = await test_env["sessions"].create(
            workspace_id=uuid4(),
            user_id=uuid4(),
            objective="Try to execute terminal as developer",
            model="fake/default",
        )

        final_session = await orchestrator.run_session(session.id)
        assert final_session.status == AgentStatus.COMPLETED

        calls = await test_env["tool_calls"].list_by_session(session.id)
        assert len(calls) == 1
        assert calls[0].status == ToolCallStatus.REJECTED

    @pytest.mark.asyncio
    async def test_approval_suspension_exits_worker_immediately(self, test_env) -> None:
        # file.create requires approval for DEVELOPER role
        provider = SequentialFakeLLMProvider([
            _tc_json("file.create", {"param": "new_file.txt"}),
        ])
        orchestrator = make_orchestrator(test_env, provider)

        session = await test_env["sessions"].create(
            workspace_id=uuid4(),
            user_id=uuid4(),
            objective="Create a new file",
            model="fake/default",
        )

        suspended_session = await orchestrator.run_session(session.id)
        # Verify non-blocking suspension
        assert suspended_session.status == AgentStatus.WAITING_FOR_APPROVAL

        # Verify tool call was created with PENDING_APPROVAL
        calls = await test_env["tool_calls"].list_by_session(session.id)
        assert len(calls) == 1
        assert calls[0].status == ToolCallStatus.PENDING_APPROVAL

        # Verify approval record created with canonical argument hash
        pending = await test_env["approvals"].list_pending_by_session(session.id)
        assert len(pending) == 1
        expected_hash = compute_arguments_hash({"param": "new_file.txt"})
        assert pending[0].arguments_hash == expected_hash

        # Verify event emitted
        event_types = [e.event_type for e in test_env["events"].events]
        assert AgentEventType.APPROVAL_REQUIRED in event_types

    @pytest.mark.asyncio
    async def test_approval_resumption_with_hash_match(self, test_env) -> None:
        # 1. Start session that suspends for approval
        provider = SequentialFakeLLMProvider([
            _tc_json("file.create", {"param": "target.py"}),
            _complete_json("Finished after write approved"),
        ])
        orchestrator = make_orchestrator(test_env, provider)

        session = await test_env["sessions"].create(
            workspace_id=uuid4(),
            user_id=uuid4(),
            objective="Create file",
            model="fake/default",
        )

        suspended = await orchestrator.run_session(session.id)
        assert suspended.status == AgentStatus.WAITING_FOR_APPROVAL

        # 2. Simulate human approval decision
        pending = await test_env["approvals"].list_pending_by_session(session.id)
        app = pending[0]
        await test_env["approvals"].decide(
            app.id,
            status=ApprovalStatus.GRANTED,
            decided_by=uuid4(),
        )

        # 3. Resume session
        resumed = await orchestrator.resume_session(session.id)
        assert resumed.status == AgentStatus.COMPLETED

        # Verify tool executed
        calls = await test_env["tool_calls"].list_by_session(session.id)
        assert len(calls) == 1
        assert calls[0].status == ToolCallStatus.COMPLETED

        # Verify cumulative tool call counter preserved
        assert resumed.metrics.total_tool_calls == 1
        assert resumed.metrics.total_llm_calls == 2

    @pytest.mark.asyncio
    async def test_approval_resumption_hash_mismatch_rejected(self, test_env) -> None:
        provider = SequentialFakeLLMProvider([
            _tc_json("file.create", {"param": "original.txt"}),
        ])
        orchestrator = make_orchestrator(test_env, provider)

        session = await test_env["sessions"].create(
            workspace_id=uuid4(),
            user_id=uuid4(),
            objective="Create file with tamper test",
            model="fake/default",
        )
        await orchestrator.run_session(session.id)

        # Grant approval
        pending = await test_env["approvals"].list_pending_by_session(session.id)
        app = pending[0]
        await test_env["approvals"].decide(
            app.id, status=ApprovalStatus.GRANTED, decided_by=uuid4()
        )

        # Tamper with tool call arguments
        tc = (await test_env["tool_calls"].list_by_session(session.id))[0]
        tampered = AgentToolCallRecord(
            id=tc.id,
            session_id=tc.session_id,
            tool_name=tc.tool_name,
            arguments={"param": "TAMPERED_CONTENT"},
            risk_level=tc.risk_level,
            status=tc.status,
            created_at=tc.created_at,
        )
        test_env["tool_calls"].calls[tc.id] = tampered

        # Resumption must reject execution with DomainError
        with pytest.raises(DomainError) as exc_info:
            await orchestrator.resume_session(session.id)
        assert exc_info.value.code == "approval_hash_mismatch"

        # Tool was not executed
        assert test_env["write_tool"].call_count == 0

    @pytest.mark.asyncio
    async def test_approval_resumption_rejected_if_tool_call_already_executed(
        self, test_env
    ) -> None:
        provider = SequentialFakeLLMProvider([
            _tc_json("file.create", {"param": "idempotent.txt"}),
        ])
        orchestrator = make_orchestrator(test_env, provider)

        session = await test_env["sessions"].create(
            workspace_id=uuid4(),
            user_id=uuid4(),
            objective="Idempotency test",
            model="fake/default",
        )
        await orchestrator.run_session(session.id)

        # Grant approval
        pending = await test_env["approvals"].list_pending_by_session(session.id)
        app = pending[0]
        await test_env["approvals"].decide(
            app.id, status=ApprovalStatus.GRANTED, decided_by=uuid4()
        )

        # Simulate tool call already executed / completed (e.g. race condition)
        tc = (await test_env["tool_calls"].list_by_session(session.id))[0]
        already_run = AgentToolCallRecord(
            id=tc.id,
            session_id=tc.session_id,
            tool_name=tc.tool_name,
            arguments=tc.arguments,
            risk_level=tc.risk_level,
            status=ToolCallStatus.COMPLETED,
            created_at=tc.created_at,
        )
        test_env["tool_calls"].calls[tc.id] = already_run

        with pytest.raises(DomainError) as exc_info:
            await orchestrator.resume_session(session.id)
        assert exc_info.value.code == "tool_call_already_executed"


    @pytest.mark.asyncio
    async def test_approval_expiration(self, test_env) -> None:
        provider = SequentialFakeLLMProvider([
            _tc_json("file.create", {"param": "expired.txt"}),
        ])
        orchestrator = make_orchestrator(test_env, provider)

        session = await test_env["sessions"].create(
            workspace_id=uuid4(),
            user_id=uuid4(),
            objective="Expiration test",
            model="fake/default",
        )
        await orchestrator.run_session(session.id)

        # Expire the pending approval
        pending = (await test_env["approvals"].list_pending_by_session(session.id))[0]
        expired_app = AgentApprovalRecord(
            id=pending.id,
            session_id=pending.session_id,
            tool_call_id=pending.tool_call_id,
            tool_name=pending.tool_name,
            arguments_hash=pending.arguments_hash,
            status=ApprovalStatus.PENDING,
            requested_at=pending.requested_at,
            expires_at=datetime.now(UTC) - timedelta(hours=1),
        )
        test_env["approvals"].approvals[pending.id] = expired_app

        res = await orchestrator.resume_session(session.id)
        assert res.status == AgentStatus.EXPIRED

    @pytest.mark.asyncio
    async def test_approval_denial(self, test_env) -> None:
        provider = SequentialFakeLLMProvider([
            _tc_json("file.create", {"param": "file.txt"}),
            _complete_json("Acknowledged denial and stopped"),
        ])
        orchestrator = make_orchestrator(test_env, provider)

        session = await test_env["sessions"].create(
            workspace_id=uuid4(),
            user_id=uuid4(),
            objective="Denial test",
            model="fake/default",
        )
        await orchestrator.run_session(session.id)

        # Deny approval
        pending = (await test_env["approvals"].list_pending_by_session(session.id))[0]
        await test_env["approvals"].decide(
            pending.id,
            status=ApprovalStatus.DENIED,
            decided_by=uuid4(),
            reason="Not approved by security team.",
        )

        res = await orchestrator.resume_session(session.id)
        assert res.status == AgentStatus.COMPLETED

        event_types = [e.event_type for e in test_env["events"].events]
        assert AgentEventType.APPROVAL_DENIED in event_types

    @pytest.mark.asyncio
    async def test_cancellation_detection(self, test_env) -> None:
        class MockCanceller:
            async def is_cancelled(self, session_id):
                return True

        provider = SequentialFakeLLMProvider([
            _complete_json("Won't reach here")
        ])
        orchestrator = make_orchestrator(test_env, provider, cancellation_checker=MockCanceller())

        session = await test_env["sessions"].create(
            workspace_id=uuid4(),
            user_id=uuid4(),
            objective="Cancellation test",
            model="fake/default",
        )

        final_session = await orchestrator.run_session(session.id)
        assert final_session.status == AgentStatus.CANCELLED
        event_types = [e.event_type for e in test_env["events"].events]
        assert AgentEventType.CANCELLED in event_types

    @pytest.mark.asyncio
    async def test_llm_calls_limit_enforced(self, test_env) -> None:
        # LLM loops indefinitely calling repo.read
        provider = SequentialFakeLLMProvider([
            _tc_json("repo.read", {"param": "foo"})
        ])
        orchestrator = make_orchestrator(test_env, provider)

        # Restrict limits to 2 LLM calls
        limits = AgentLimits(max_llm_calls=2, max_wall_time_seconds=900, max_tool_calls=50)
        session = await test_env["sessions"].create(
            workspace_id=uuid4(),
            user_id=uuid4(),
            objective="Infinite loop test",
            model="fake/default",
            limits=limits,
        )

        final_session = await orchestrator.run_session(session.id)
        assert final_session.status == AgentStatus.TIMED_OUT
        assert final_session.metrics.total_llm_calls == 2

    @pytest.mark.asyncio
    async def test_tool_calls_limit_enforced(self, test_env) -> None:
        provider = SequentialFakeLLMProvider([
            _tc_json("repo.read", {"param": "foo"})
        ])
        orchestrator = make_orchestrator(test_env, provider)

        # Restrict limits to 1 tool call
        limits = AgentLimits(max_llm_calls=30, max_wall_time_seconds=900, max_tool_calls=1)
        session = await test_env["sessions"].create(
            workspace_id=uuid4(),
            user_id=uuid4(),
            objective="Tool limit test",
            model="fake/default",
            limits=limits,
        )

        final_session = await orchestrator.run_session(session.id)
        assert final_session.status == AgentStatus.TIMED_OUT
        assert final_session.metrics.total_tool_calls == 1

    @pytest.mark.asyncio
    async def test_multi_step_task_execution(self, test_env) -> None:
        provider = SequentialFakeLLMProvider([
            _tc_json("repo.read", {"param": "file1.txt"}),
            _tc_json("repo.read", {"param": "file2.txt"}),
            _complete_json("Both files inspected"),
        ])
        orchestrator = make_orchestrator(test_env, provider)

        session = await test_env["sessions"].create(
            workspace_id=uuid4(),
            user_id=uuid4(),
            objective="Inspect two files",
            model="fake/default",
        )

        final_session = await orchestrator.run_session(session.id)
        assert final_session.status == AgentStatus.COMPLETED
        assert final_session.metrics.total_llm_calls == 3
        assert final_session.metrics.total_tool_calls == 2

        calls = await test_env["tool_calls"].list_by_session(session.id)
        assert len(calls) == 2

    @pytest.mark.asyncio
    async def test_cumulative_limits_preserved_across_resume(self, test_env) -> None:
        # Step 1: Tool call requiring approval (file.create)
        # Step 2: Resumed execution achieves completion
        provider = SequentialFakeLLMProvider([
            _tc_json("file.create", {"param": "target.py"}),
            _complete_json("Done"),
        ])
        orchestrator = make_orchestrator(test_env, provider)

        # Set execution limits
        limits = AgentLimits(max_llm_calls=30, max_wall_time_seconds=900, max_tool_calls=5)

        session = await test_env["sessions"].create(
            workspace_id=uuid4(),
            user_id=uuid4(),
            objective="Preserve counters test",
            model="fake/default",
            limits=limits,
        )

        suspended = await orchestrator.run_session(session.id)
        assert suspended.status == AgentStatus.WAITING_FOR_APPROVAL
        assert suspended.metrics.total_llm_calls == 1
        assert suspended.metrics.total_tool_calls == 0

        # Decide approval
        app = (await test_env["approvals"].list_by_session(session.id))[0]
        await test_env["approvals"].decide(
            app.id, status=ApprovalStatus.GRANTED, decided_by=uuid4()
        )

        # Resume execution
        resumed = await orchestrator.resume_session(session.id)
        # Metrics must reflect cumulative counts
        assert resumed.metrics.total_llm_calls == 2
        assert resumed.metrics.total_tool_calls == 1

    @pytest.mark.asyncio
    async def test_non_transient_llm_failure_terminates_session(self, test_env) -> None:
        failing_provider = FakeLLMProvider(
            FakeProviderConfig(fail_with=RuntimeError("Permanent LLM provider error"))
        )
        orchestrator = make_orchestrator(test_env, failing_provider)

        session = await test_env["sessions"].create(
            workspace_id=uuid4(),
            user_id=uuid4(),
            objective="Fail gracefully",
            model="fake/default",
        )

        final_session = await orchestrator.run_session(session.id)
        assert final_session.status == AgentStatus.FAILED
        event_types = [e.event_type for e in test_env["events"].events]
        assert AgentEventType.FAILED in event_types


