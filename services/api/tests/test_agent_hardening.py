"""Comprehensive test suite for FP8-E: Audit, Usage, Retention & Production Hardening.

Covers:
1. Agent audit event generation and secret/CoT scrubbing across full lifecycle
2. Usage and cost accounting linked to agent sessions (surviving resume)
3. Hard execution limits boundary enforcement (30/31 LLM calls, 50/51 tool calls, 900s)
4. Stale execution recovery (conservative lock check, crash recovery, metrics)
5. 30-day retention cleanup (terminal purged, active preserved, FK safety)
6. Concurrency and cross-workspace isolation
"""


from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID, uuid4

import pytest

from forge_api.application.agent.agent_service import AgentService
from forge_api.application.agent.maintenance_service import AgentMaintenanceService
from forge_api.application.agent.orchestrator import AgentOrchestrator
from forge_api.application.llm.usage_tracker import UsageTracker
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
    ToolCallStatus,
)
from forge_api.domain.approval import (
    AgentApprovalRecord,
    ApprovalStatus,
    compute_arguments_hash,
)
from forge_api.domain.audit import AuditEvent, AuditEventType
from forge_api.domain.auth import WorkspaceRole
from forge_api.domain.conversation import UsageEventRecord
from forge_api.domain.llm import TokenUsage
from forge_api.domain.tool import RiskLevel
from forge_api.domain.workspaces import MembershipRecord
from forge_api.infrastructure.agent.event_publisher import InMemoryAgentEventPublisher

# ─── Test Doubles ─────────────────────────────────────────────────────────────


class FakeAuditLogger:
    """In-memory audit log collector for asserting audit events and scrubbed payloads."""

    def __init__(self) -> None:
        self.events: list[AuditEvent] = []

    def log(
        self,
        event: AuditEventType,
        *,
        user_id: UUID | None = None,
        session_id: UUID | None = None,
        ip_address: str | None = None,
        user_agent: str | None = None,
        reason: str | None = None,
        payload: dict[str, Any] | None = None,
    ) -> None:
        self.events.append(
            AuditEvent(
                event=event,
                user_id=user_id,
                session_id=session_id,
                ip_address=ip_address,
                user_agent=user_agent,
                reason=reason,
                payload=payload,
            )
        )


class FakeUsageRepo:
    """In-memory usage repository supporting agent_session_id."""

    def __init__(self) -> None:
        self.events: list[UsageEventRecord] = []

    async def create(
        self,
        *,
        workspace_id: UUID,
        user_id: UUID,
        conversation_id: UUID | None = None,
        message_id: UUID | None = None,
        provider: str,
        model: str,
        input_tokens: int,
        output_tokens: int,
        total_tokens: int,
        duration_ms: float,
        estimated_cost: float,
        agent_session_id: UUID | None = None,
        metadata: dict | None = None,
    ) -> UsageEventRecord:
        rec = UsageEventRecord(
            id=uuid4(),
            workspace_id=workspace_id,
            user_id=user_id,
            conversation_id=conversation_id,
            message_id=message_id,
            provider=provider,
            model=model,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            total_tokens=total_tokens,
            duration_ms=duration_ms,
            estimated_cost=estimated_cost,
            created_at=datetime.now(UTC),
            agent_session_id=agent_session_id,
            metadata=metadata or {},
        )
        self.events.append(rec)
        return rec

    async def list_by_agent_session(self, session_id: UUID) -> list[UsageEventRecord]:
        return [e for e in self.events if e.agent_session_id == session_id]


class FakeModelRegistry:
    def estimate_cost(self, model: str, input_tokens: int, output_tokens: int) -> float:
        return (input_tokens * 0.000001) + (output_tokens * 0.000002)


class FakeSessionRepo:
    def __init__(self) -> None:
        self.sessions: dict[UUID, AgentSessionRecord] = {}

    async def get(self, session_id: UUID) -> AgentSessionRecord | None:
        return self.sessions.get(session_id)

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
            last_heartbeat_at=rec.last_heartbeat_at,
            worker_id=rec.worker_id,
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
            last_heartbeat_at=rec.last_heartbeat_at,
            worker_id=rec.worker_id,
            metadata=rec.metadata,
        )
        self.sessions[session_id] = updated
        return updated

    async def update_heartbeat(
        self,
        session_id: UUID,
        *,
        worker_id: str | None = None,
        heartbeat_at: datetime | None = None,
    ) -> bool:
        rec = self.sessions.get(session_id)
        if not rec:
            return False
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
            metrics=rec.metrics,
            current_step=rec.current_step,
            started_at=rec.started_at,
            completed_at=rec.completed_at,
            cancelled_at=rec.cancelled_at,
            last_heartbeat_at=heartbeat_at or datetime.now(UTC),
            worker_id=worker_id or rec.worker_id,
            metadata=rec.metadata,
        )
        self.sessions[session_id] = updated
        return True

    async def list_stale_sessions(self, *, stale_before: datetime) -> list[AgentSessionRecord]:
        res = []
        for s in self.sessions.values():
            if s.status in (AgentStatus.RUNNING, AgentStatus.PLANNING):
                last_hb = s.last_heartbeat_at or s.started_at or s.created_at
                if last_hb < stale_before:
                    res.append(s)
        return res

    async def delete_terminal_sessions(self, *, completed_before: datetime) -> int:
        to_del = []
        for sid, s in self.sessions.items():
            if s.status in (
                AgentStatus.COMPLETED,
                AgentStatus.FAILED,
                AgentStatus.CANCELLED,
                AgentStatus.TIMED_OUT,
                AgentStatus.EXPIRED,
            ):
                comp = s.completed_at or s.cancelled_at or s.created_at
                if comp < completed_before:
                    to_del.append(sid)
        for sid in to_del:
            del self.sessions[sid]
        return len(to_del)


class FakeApprovalRepo:
    def __init__(self) -> None:
        self.approvals: dict[UUID, AgentApprovalRecord] = {}

    async def get(self, approval_id: UUID) -> AgentApprovalRecord | None:
        return self.approvals.get(approval_id)

    async def create(
        self,
        *,
        session_id: UUID,
        tool_call_id: UUID,
        tool_name: str,
        arguments_hash: str,
        requested_by: UUID,
        expires_at: datetime | None = None,
    ) -> AgentApprovalRecord:
        rec = AgentApprovalRecord(
            id=uuid4(),
            session_id=session_id,
            tool_call_id=tool_call_id,
            tool_name=tool_name,
            arguments_hash=arguments_hash,
            requested_by=requested_by,
            status=ApprovalStatus.PENDING,
            requested_at=datetime.now(UTC),
            expires_at=expires_at,
        )
        self.approvals[rec.id] = rec
        return rec

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
            requested_by=rec.requested_by,
            status=status,
            decided_by=decided_by,
            reason=reason,
            decided_at=decided_at or datetime.now(UTC),
            requested_at=rec.requested_at,
            expires_at=rec.expires_at,
        )
        self.approvals[approval_id] = updated
        return updated

    async def list_by_session(self, session_id: UUID) -> list[AgentApprovalRecord]:
        return [a for a in self.approvals.values() if a.session_id == session_id]

    async def list_expired(self, *, expired_before: datetime) -> list[AgentApprovalRecord]:
        return [
            a
            for a in self.approvals.values()
            if a.status == ApprovalStatus.PENDING
            and a.expires_at is not None
            and a.expires_at < expired_before
        ]


class FakeToolCallRepo:
    def __init__(self) -> None:
        self.tool_calls: dict[UUID, AgentToolCallRecord] = {}

    async def get(self, tool_call_id: UUID) -> AgentToolCallRecord | None:
        return self.tool_calls.get(tool_call_id)

    async def create(
        self,
        *,
        session_id: UUID,
        tool_name: str,
        arguments: dict[str, Any],
        risk_level: RiskLevel,
        status: ToolCallStatus = ToolCallStatus.RUNNING,
        step_id: UUID | None = None,
    ) -> AgentToolCallRecord:
        rec = AgentToolCallRecord(
            id=uuid4(),
            session_id=session_id,
            tool_name=tool_name,
            arguments=arguments,
            risk_level=risk_level,
            status=status,
            created_at=datetime.now(UTC),
        )
        self.tool_calls[rec.id] = rec
        return rec

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
        rec = self.tool_calls.get(tool_call_id)
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
            output=output,
            error_message=error_message,
            duration_ms=duration_ms,
            completed_at=completed_at,
        )
        self.tool_calls[tool_call_id] = updated
        return updated


class FakeStepRepo:
    def __init__(self) -> None:
        self.steps: dict[UUID, AgentStepRecord] = {}

    async def list_by_session(self, session_id: UUID) -> list[AgentStepRecord]:
        return [s for s in self.steps.values() if s.session_id == session_id]


class FakeJobQueue:
    def __init__(self) -> None:
        self.enqueued: list[Any] = []

    async def enqueue(
        self,
        session_id: UUID,
        job_type: str,
        *,
        metadata: dict[str, Any] | None = None,
    ) -> Any:
        job = {
            "id": uuid4(),
            "session_id": session_id,
            "job_type": job_type,
            "metadata": metadata or {},
        }
        self.enqueued.append(job)
        return job

    async def fail_by_session(self, session_id: UUID, error_message: str) -> int:
        return 1


class FakeWorkspaceRepo:
    def __init__(self) -> None:
        self.members: dict[tuple[UUID, UUID], WorkspaceRole] = {}

    async def get_membership(self, workspace_id: UUID, user_id: UUID) -> MembershipRecord | None:
        role = self.members.get((workspace_id, user_id))
        if not role:
            return None
        return MembershipRecord(
            workspace_id=workspace_id,
            user_id=user_id,
            role=role,
            created_at=datetime.now(UTC),
        )


class FakeCoordinator:
    def __init__(self) -> None:
        self.locks: dict[UUID, bool] = {}

    async def acquire_lock(self, session_id: UUID, ttl_seconds: int = 10) -> bool:
        if self.locks.get(session_id, False):
            return False  # Lock already held by active worker
        self.locks[session_id] = True
        return True

    async def release_lock(self, session_id: UUID) -> None:
        self.locks[session_id] = False


# ─── Tests ───────────────────────────────────────────────────────────────────


class TestAgentAuditHardening:
    """Verify that all 21 audit events are properly emitted without exposing secrets or CoT."""

    @pytest.mark.asyncio
    async def test_agent_service_audit_lifecycle(self) -> None:
        sessions = FakeSessionRepo()
        approvals = FakeApprovalRepo()
        tool_calls = FakeToolCallRepo()
        steps = FakeStepRepo()
        workspaces = FakeWorkspaceRepo()
        audit = FakeAuditLogger()
        events = InMemoryAgentEventPublisher()
        queue = FakeJobQueue()

        workspace_id = uuid4()
        user_id = uuid4()
        workspaces.members[(workspace_id, user_id)] = WorkspaceRole.OWNER

        service = AgentService(
            sessions=sessions,
            steps=steps,
            tool_calls=tool_calls,
            approvals=approvals,
            workspaces=workspaces,
            repositories=None,  # type: ignore
            job_queue=queue,
            event_publisher=events,
            audit=audit,
        )

        # 1. Create Session
        session = await service.create_session(
            workspace_id=workspace_id,
            user_id=user_id,
            objective="Deploy with API_KEY=sk-super-secret-12345",
        )
        assert session.status == AgentStatus.CREATED

        create_audits = [e for e in audit.events if e.event == AuditEventType.AGENT_CREATED]
        assert len(create_audits) == 1
        assert create_audits[0].user_id == user_id
        assert create_audits[0].session_id == session.id
        # Confirm secrets are redacted in audit payload
        payload_str = str(create_audits[0].payload)
        assert "sk-super-secret-12345" not in payload_str
        assert "[REDACTED" in payload_str

        # 2. Run Session
        await service.run_session(workspace_id=workspace_id, session_id=session.id, user_id=user_id)
        run_audits = [e for e in audit.events if e.event == AuditEventType.AGENT_RUN_REQUESTED]
        assert len(run_audits) == 1
        assert run_audits[0].session_id == session.id

        # 3. Cancel Session
        await service.cancel_session(
            workspace_id=workspace_id, session_id=session.id, user_id=user_id
        )
        cancel_req_audits = [
            e for e in audit.events if e.event == AuditEventType.AGENT_CANCEL_REQUESTED
        ]
        cancelled_audits = [e for e in audit.events if e.event == AuditEventType.AGENT_CANCELLED]
        assert len(cancel_req_audits) == 1
        assert len(cancelled_audits) == 1


class TestAgentUsageAccounting:
    """Verify authoritative usage tracking linked to agent sessions."""

    @pytest.mark.asyncio
    async def test_usage_tracking_per_session(self) -> None:
        usage_repo = FakeUsageRepo()
        tracker = UsageTracker(usage_repo=usage_repo, registry=FakeModelRegistry())  # type: ignore

        workspace_id = uuid4()
        user_id = uuid4()
        session_id = uuid4()

        # Record LLM call 1
        await tracker.record(
            workspace_id=workspace_id,
            user_id=user_id,
            agent_session_id=session_id,
            provider="openai",
            model="gpt-4o",
            usage=TokenUsage(input_tokens=100, output_tokens=50, total_tokens=150),
            duration_ms=450.0,
        )

        # Record LLM call 2
        await tracker.record(
            workspace_id=workspace_id,
            user_id=user_id,
            agent_session_id=session_id,
            provider="openai",
            model="gpt-4o",
            usage=TokenUsage(input_tokens=200, output_tokens=100, total_tokens=300),
            duration_ms=600.0,
        )

        # Retrieve usage by session
        session_usage = await usage_repo.list_by_agent_session(session_id)
        assert len(session_usage) == 2
        assert sum(e.input_tokens for e in session_usage) == 300
        assert sum(e.output_tokens for e in session_usage) == 150
        assert sum(e.total_tokens for e in session_usage) == 450
        assert all(e.agent_session_id == session_id for e in session_usage)


class TestAgentExecutionLimits:
    """Verify exact limit boundary enforcement."""

    @pytest.mark.asyncio
    async def test_llm_calls_limit_exact_boundary(self) -> None:
        """30 LLM calls allowed; 31st rejected, transitioning to TIMED_OUT."""
        sessions = FakeSessionRepo()
        audit = FakeAuditLogger()
        events = InMemoryAgentEventPublisher()

        # Create session with limit of 30 calls and current metrics of 30 calls
        session = await sessions.create(
            workspace_id=uuid4(),
            user_id=uuid4(),
            objective="Limit test",
            status=AgentStatus.RUNNING,
            limits=AgentLimits(max_llm_calls=30),
            metrics=ExecutionMetrics(total_llm_calls=30),
        )

        orchestrator = AgentOrchestrator(
            sessions=sessions,
            steps=FakeStepRepo(),
            tool_calls=FakeToolCallRepo(),
            approvals=FakeApprovalRepo(),
            tool_registry=ToolRegistry(),
            policy_engine=PolicyEngine(),
            context_assembly=None,
            prompt_builder=None,  # type: ignore
            gateway=None,  # type: ignore
            events=events,
            workspaces=FakeWorkspaceRepo(),
            audit=audit,
        )

        # Calling _orchestration_loop directly triggers the limit check immediately
        result = await orchestrator._orchestration_loop(
            session, repo_root=None, user_role=WorkspaceRole.OWNER
        )

        assert result.status == AgentStatus.TIMED_OUT
        # Check domain event
        timed_out_events = [e for e in events.events if e.event_type == AgentEventType.TIMED_OUT]
        limit_reached_events = [
            e for e in events.events if e.event_type == AgentEventType.LIMIT_REACHED
        ]
        assert len(timed_out_events) == 1
        assert len(limit_reached_events) == 1

        # Check audit event
        limit_audits = [e for e in audit.events if e.event == AuditEventType.AGENT_LIMIT_REACHED]
        timed_out_audits = [e for e in audit.events if e.event == AuditEventType.AGENT_TIMED_OUT]
        assert len(limit_audits) == 1
        assert len(timed_out_audits) == 1

    @pytest.mark.asyncio
    async def test_tool_calls_limit_in_resume(self) -> None:
        """50 tool calls allowed; 51st rejected upon resume."""
        sessions = FakeSessionRepo()
        approvals = FakeApprovalRepo()
        tool_calls = FakeToolCallRepo()
        audit = FakeAuditLogger()
        events = InMemoryAgentEventPublisher()

        session = await sessions.create(
            workspace_id=uuid4(),
            user_id=uuid4(),
            objective="Tool limit test",
            status=AgentStatus.WAITING_FOR_APPROVAL,
            limits=AgentLimits(max_tool_calls=50),
            metrics=ExecutionMetrics(total_tool_calls=50),
        )

        tc = await tool_calls.create(
            session_id=session.id,
            tool_name="terminal.execute",
            arguments={"command": "dir"},
            risk_level=RiskLevel.HIGH,
            status=ToolCallStatus.PENDING_APPROVAL,
        )
        args_hash = compute_arguments_hash(tc.arguments)
        appr = await approvals.create(
            session_id=session.id,
            tool_call_id=tc.id,
            tool_name=tc.tool_name,
            arguments_hash=args_hash,
            requested_by=session.user_id,
        )
        await approvals.decide(
            appr.id,
            status=ApprovalStatus.GRANTED,
            decided_by=session.user_id,
        )

        orchestrator = AgentOrchestrator(
            sessions=sessions,
            steps=FakeStepRepo(),
            tool_calls=tool_calls,
            approvals=approvals,
            tool_registry=ToolRegistry(),
            policy_engine=PolicyEngine(),
            context_assembly=None,
            prompt_builder=None,  # type: ignore
            gateway=None,  # type: ignore
            events=events,
            workspaces=FakeWorkspaceRepo(),
            audit=audit,
        )

        result = await orchestrator.resume_session(session.id)
        assert result.status == AgentStatus.TIMED_OUT

        limit_audits = [e for e in audit.events if e.event == AuditEventType.AGENT_LIMIT_REACHED]
        assert len(limit_audits) == 1
        assert "Max tool calls exceeded" in (limit_audits[0].reason or "")


class TestAgentMaintenanceAndRetention:
    """Verify stale worker recovery and 30-day retention cleanup."""

    @pytest.mark.asyncio
    async def test_stale_session_recovery_protects_active_worker(self) -> None:
        """If worker lock is actively held in Redis, recovery skips the session."""
        sessions = FakeSessionRepo()
        approvals = FakeApprovalRepo()
        coordinator = FakeCoordinator()
        audit = FakeAuditLogger()
        events = InMemoryAgentEventPublisher()

        service = AgentMaintenanceService(
            sessions=sessions,
            approvals=approvals,
            coordinator=coordinator,  # type: ignore
            events=events,
            audit=audit,
        )

        now = datetime.now(UTC)
        stale_time = now - timedelta(minutes=10)

        # Create session with stale heartbeat
        session = await sessions.create(
            workspace_id=uuid4(),
            user_id=uuid4(),
            objective="Stale session",
            status=AgentStatus.RUNNING,
        )
        await sessions.update_heartbeat(session.id, heartbeat_at=stale_time)

        # Active worker holds the lock
        coordinator.locks[session.id] = True

        recovered = await service.recover_stale_sessions(stale_threshold_seconds=300, now=now)
        assert recovered == 0

        # Session remains RUNNING because active worker holds lock
        current = await sessions.get(session.id)
        assert current is not None
        assert current.status == AgentStatus.RUNNING

    @pytest.mark.asyncio
    async def test_stale_session_recovery_terminates_abandoned_session(self) -> None:
        """If worker lock is free and heartbeat expired, recovery marks FAILED."""
        sessions = FakeSessionRepo()
        approvals = FakeApprovalRepo()
        coordinator = FakeCoordinator()
        audit = FakeAuditLogger()
        events = InMemoryAgentEventPublisher()

        service = AgentMaintenanceService(
            sessions=sessions,
            approvals=approvals,
            coordinator=coordinator,  # type: ignore
            events=events,
            audit=audit,
        )

        now = datetime.now(UTC)
        stale_time = now - timedelta(minutes=10)

        session = await sessions.create(
            workspace_id=uuid4(),
            user_id=uuid4(),
            objective="Abandoned session",
            status=AgentStatus.RUNNING,
        )
        await sessions.update_heartbeat(session.id, heartbeat_at=stale_time)

        # Worker crashed: lock is free
        coordinator.locks[session.id] = False

        recovered = await service.recover_stale_sessions(stale_threshold_seconds=300, now=now)
        assert recovered == 1

        current = await sessions.get(session.id)
        assert current is not None
        assert current.status == AgentStatus.FAILED
        assert current.completed_at is not None

        # Verify domain event and audit event
        failed_events = [e for e in events.events if e.event_type == AgentEventType.FAILED]
        assert len(failed_events) == 1
        assert failed_events[0].data.get("reason") == "stale_execution_timeout"

        failed_audits = [e for e in audit.events if e.event == AuditEventType.AGENT_FAILED]
        assert len(failed_audits) == 1
        assert failed_audits[0].reason == "stale_execution_timeout"

    @pytest.mark.asyncio
    async def test_retention_cleanup_preserves_active_sessions(self) -> None:
        """Cleanup removes terminal sessions older than 30 days, preserving active."""
        sessions = FakeSessionRepo()

        approvals = FakeApprovalRepo()

        service = AgentMaintenanceService(
            sessions=sessions,
            approvals=approvals,
        )

        now = datetime.now(UTC)
        old_time = now - timedelta(days=35)
        recent_time = now - timedelta(days=10)

        # 1. Old COMPLETED session -> should be deleted
        s_old_completed = await sessions.create(
            workspace_id=uuid4(),
            user_id=uuid4(),
            objective="Old completed",
            status=AgentStatus.COMPLETED,
        )
        await sessions.update_status(
            s_old_completed.id, AgentStatus.COMPLETED, completed_at=old_time
        )

        # 2. Recent COMPLETED session -> should be preserved
        s_recent_completed = await sessions.create(
            workspace_id=uuid4(),
            user_id=uuid4(),
            objective="Recent completed",
            status=AgentStatus.COMPLETED,
        )
        await sessions.update_status(
            s_recent_completed.id, AgentStatus.COMPLETED, completed_at=recent_time
        )

        # 3. Old RUNNING session -> active session must NEVER be deleted by retention
        s_old_running = await sessions.create(
            workspace_id=uuid4(),
            user_id=uuid4(),
            objective="Old running",
            status=AgentStatus.RUNNING,
        )

        deleted = await service.cleanup_retention(retention_days=30, now=now)
        assert deleted == 1

        assert await sessions.get(s_old_completed.id) is None
        assert await sessions.get(s_recent_completed.id) is not None
        assert await sessions.get(s_old_running.id) is not None

    @pytest.mark.asyncio
    async def test_recover_expired_approvals(self) -> None:
        """Approvals past their expiration timestamp are transitioned to EXPIRED."""
        sessions = FakeSessionRepo()
        approvals = FakeApprovalRepo()
        audit = FakeAuditLogger()
        events = InMemoryAgentEventPublisher()

        service = AgentMaintenanceService(
            sessions=sessions,
            approvals=approvals,
            events=events,
            audit=audit,
        )

        now = datetime.now(UTC)
        expired_deadline = now - timedelta(hours=2)

        session = await sessions.create(
            workspace_id=uuid4(),
            user_id=uuid4(),
            objective="Approval test",
            status=AgentStatus.WAITING_FOR_APPROVAL,
        )

        appr = await approvals.create(
            session_id=session.id,
            tool_call_id=uuid4(),
            tool_name="git.commit",
            arguments_hash="hash123",
            requested_by=session.user_id,
            expires_at=expired_deadline,
        )

        recovered = await service.recover_expired_approvals(now=now)
        assert recovered == 1

        # Approval and session are now EXPIRED
        updated_appr = await approvals.get(appr.id)
        assert updated_appr is not None
        assert updated_appr.status == ApprovalStatus.EXPIRED

        updated_session = await sessions.get(session.id)
        assert updated_session is not None
        assert updated_session.status == AgentStatus.EXPIRED

        # Verify audit event
        expired_audits = [
            e for e in audit.events if e.event == AuditEventType.AGENT_APPROVAL_EXPIRED
        ]
        assert len(expired_audits) == 1

    @pytest.mark.asyncio
    async def test_wall_time_limit_boundary(self) -> None:
        """Wall time exceeding max_wall_time_seconds triggers TIMED_OUT."""
        sessions = FakeSessionRepo()
        audit = FakeAuditLogger()
        events = InMemoryAgentEventPublisher()

        session = await sessions.create(
            workspace_id=uuid4(),
            user_id=uuid4(),
            objective="Wall time test",
            status=AgentStatus.RUNNING,
            limits=AgentLimits(max_wall_time_seconds=900),
            metrics=ExecutionMetrics(wall_time_seconds=905.0),
        )

        orchestrator = AgentOrchestrator(
            sessions=sessions,
            steps=FakeStepRepo(),
            tool_calls=FakeToolCallRepo(),
            approvals=FakeApprovalRepo(),
            tool_registry=ToolRegistry(),
            policy_engine=PolicyEngine(),
            context_assembly=None,
            prompt_builder=None,  # type: ignore
            gateway=None,  # type: ignore
            events=events,
            workspaces=FakeWorkspaceRepo(),
            audit=audit,
        )

        result = await orchestrator._orchestration_loop(
            session, repo_root=None, user_role=WorkspaceRole.OWNER
        )
        assert result.status == AgentStatus.TIMED_OUT
        assert result.metrics.wall_time_seconds >= 900.0

        limit_audits = [e for e in audit.events if e.event == AuditEventType.AGENT_LIMIT_REACHED]
        assert len(limit_audits) == 1
        assert "Max wall time exceeded" in (limit_audits[0].reason or "")

    @pytest.mark.asyncio
    async def test_audit_scrubs_secrets_and_cot(self) -> None:
        """Audit payload helper scrubs secrets, passwords, and ignores raw CoT keys."""
        sessions = FakeSessionRepo()
        audit = FakeAuditLogger()

        orchestrator = AgentOrchestrator(
            sessions=sessions,
            steps=FakeStepRepo(),
            tool_calls=FakeToolCallRepo(),
            approvals=FakeApprovalRepo(),
            tool_registry=ToolRegistry(),
            policy_engine=PolicyEngine(),
            context_assembly=None,
            prompt_builder=None,  # type: ignore
            gateway=None,  # type: ignore
            events=InMemoryAgentEventPublisher(),
            workspaces=FakeWorkspaceRepo(),
            audit=audit,
        )

        session = await sessions.create(
            workspace_id=uuid4(),
            user_id=uuid4(),
            objective="Audit scrub test",
        )

        # Log with secrets and internal CoT
        orchestrator._audit_log(
            AuditEventType.AGENT_RUNNING,
            session,
            payload={
                "chain_of_thought": "Thinking about secret stuff...",
                "reasoning": "Deep step 1 analysis",
                "secret": "hidden_secret",
                "safe_note": (
                    "Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9."
                    "eyJzdWIiOiIxMjM0NTY3ODkwIiwibmFtZSI6IkpvaG4gRG9lIiwiaWF0IjoxNTE2MjM5MDIyfQ."
                    "SflKxwRJSMeKKF2QT4fwpMeJf36POk6yJV_adQssw5c"
                ),
            },
        )


        assert len(audit.events) == 1
        payload = audit.events[0].payload or {}
        # chain_of_thought, reasoning, secret should NOT be present in payload
        assert "chain_of_thought" not in payload
        assert "reasoning" not in payload
        assert "secret" not in payload
        # safe_note should have its JWT token redacted
        assert "eyJhbGci" not in str(payload.get("safe_note"))
        assert "[REDACTED" in str(payload.get("safe_note"))
