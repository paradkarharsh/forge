"""Comprehensive test suite for FP8-D Agent HTTP API, Application Service, and SSE Streaming."""

import asyncio
import json
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID, uuid4

import pytest

from forge_api.application.agent.agent_service import AgentService
from forge_api.domain.agent import (
    AgentLimits,
    AgentSessionRecord,
    AgentStatus,
    AgentStepRecord,
    AgentToolCallRecord,
    ExecutionMetrics,
    StepStatus,
    ToolCallStatus,
)
from forge_api.domain.approval import (
    AgentApprovalRecord,
    ApprovalStatus,
    compute_arguments_hash,
)
from forge_api.domain.auth import WorkspaceRole
from forge_api.domain.repositories import AgentJobRecord
from forge_api.domain.security import AccessClaims
from forge_api.domain.tool import RiskLevel
from forge_api.infrastructure.agent.event_publisher import (
    EVENT_LOG_PREFIX,
    InMemoryAgentEventPublisher,
)
from forge_api.infrastructure.workers.agent_worker import RedisAgentCoordinator
from forge_api.presentation.http.dependencies import (
    get_agent_service,
    get_cache_client_optional,
    validated_claims,
)


class MockRedis:
    def __init__(self) -> None:
        self.data: dict[str, list[str]] = {}
        self.published: list[tuple[str, str]] = []
        self.channels: dict[str, list[asyncio.Queue]] = {}

    async def rpush(self, key: str, value: str):
        if key not in self.data:
            self.data[key] = []
        self.data[key].append(value)
        return len(self.data[key])

    async def ltrim(self, key: str, start: int, end: int):
        if key in self.data:
            lst = self.data[key]
            # convert negative python indices
            if end == -1:
                self.data[key] = lst[start:]
            else:
                self.data[key] = lst[start : end + 1]
        return True

    async def lrange(self, key: str, start: int, end: int):
        lst = self.data.get(key, [])
        if end == -1:
            return lst[start:]
        return lst[start : end + 1]

    async def expire(self, key: str, ttl: int):
        return True

    async def set(self, key: str, value: str, nx: bool = False, ex: int | None = None):
        return True

    async def get(self, key: str):
        return None

    async def publish(self, channel: str, message: str):
        self.published.append((channel, message))
        for q in self.channels.get(channel, []):
            await q.put(message)
        return 1

    def pubsub(self):
        return MockPubSub(self)


class MockPubSub:
    def __init__(self, redis: MockRedis) -> None:
        self._redis = redis
        self._queue: asyncio.Queue = asyncio.Queue()
        self._channel: str | None = None

    async def subscribe(self, channel: str):
        self._channel = channel
        if channel not in self._redis.channels:
            self._redis.channels[channel] = []
        self._redis.channels[channel].append(self._queue)

    async def unsubscribe(self, channel: str):
        if channel in self._redis.channels and self._queue in self._redis.channels[channel]:
            self._redis.channels[channel].remove(self._queue)

    async def aclose(self):
        if self._channel:
            await self.unsubscribe(self._channel)

    async def get_message(self, ignore_subscribe_messages: bool = True, timeout: float = 1.0):
        try:
            msg = await asyncio.wait_for(self._queue.get(), timeout=timeout)
            return {"type": "message", "data": msg}
        except TimeoutError:
            return None


class FakeAgentSessionRepository:
    def __init__(self) -> None:
        self.sessions: dict[UUID, AgentSessionRecord] = {}

    async def get(self, session_id: UUID) -> AgentSessionRecord | None:
        return self.sessions.get(session_id)

    async def list_by_workspace(
        self,
        workspace_id: UUID,
        *,
        user_id: UUID | None = None,
        repository_id: UUID | None = None,
        status: AgentStatus | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[AgentSessionRecord]:
        res = [
            s
            for s in self.sessions.values()
            if s.workspace_id == workspace_id
            and (user_id is None or s.user_id == user_id)
            and (repository_id is None or s.repository_id == repository_id)
            and (status is None or s.status == status)
        ]
        res.sort(key=lambda s: s.created_at, reverse=True)
        return res[offset : offset + limit]

    async def count_by_workspace(
        self,
        workspace_id: UUID,
        *,
        user_id: UUID | None = None,
        repository_id: UUID | None = None,
        status: AgentStatus | None = None,
    ) -> int:
        return len(
            [
                s
                for s in self.sessions.values()
                if s.workspace_id == workspace_id
                and (user_id is None or s.user_id == user_id)
                and (repository_id is None or s.repository_id == repository_id)
                and (status is None or s.status == status)
            ]
        )

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
                if s.completed_at and s.completed_at < completed_before:
                    to_del.append(sid)
        for sid in to_del:
            del self.sessions[sid]
        return len(to_del)


class FakeAgentStepRepository:
    def __init__(self) -> None:
        self.steps: dict[UUID, AgentStepRecord] = {}

    async def get(self, step_id: UUID) -> AgentStepRecord | None:
        return self.steps.get(step_id)

    async def list_by_session(self, session_id: UUID) -> list[AgentStepRecord]:
        steps = [s for s in self.steps.values() if s.session_id == session_id]
        steps.sort(key=lambda s: s.sequence)
        return steps

    async def create(
        self,
        *,
        session_id: UUID,
        sequence: int,
        objective: str,
        status: StepStatus = StepStatus.PENDING,
        metadata: dict | None = None,
    ) -> AgentStepRecord:
        record = AgentStepRecord(
            id=uuid4(),
            session_id=session_id,
            sequence=sequence,
            objective=objective,
            status=status,
            created_at=datetime.now(UTC),
            metadata=metadata or {},
        )
        self.steps[record.id] = record
        return record

    async def update_status(
        self,
        step_id: UUID,
        status: StepStatus,
        *,
        started_at: datetime | None = None,
        completed_at: datetime | None = None,
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
            started_at=started_at or rec.started_at,
            completed_at=completed_at or rec.completed_at,
            metadata=rec.metadata,
        )
        self.steps[step_id] = updated
        return updated


class FakeAgentToolCallRepository:
    def __init__(self) -> None:
        self.calls: dict[UUID, AgentToolCallRecord] = {}

    async def get(self, tool_call_id: UUID) -> AgentToolCallRecord | None:
        return self.calls.get(tool_call_id)

    async def list_by_session(
        self, session_id: UUID, *, limit: int = 100, offset: int = 0
    ) -> list[AgentToolCallRecord]:
        calls = [c for c in self.calls.values() if c.session_id == session_id]
        calls.sort(key=lambda c: c.created_at)
        return calls[offset : offset + limit]

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


class FakeAgentApprovalRepository:
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
        apps = [a for a in self.approvals.values() if a.session_id == session_id]
        apps.sort(key=lambda a: a.requested_at, reverse=True)
        return apps

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


class FakeAgentJobQueue:
    def __init__(self) -> None:
        self.enqueued: list[AgentJobRecord] = []

    async def enqueue(
        self,
        session_id: UUID,
        job_type: str,
        *,
        metadata: dict[str, Any] | None = None,
    ) -> AgentJobRecord:
        job = AgentJobRecord(
            id=uuid4(),
            session_id=session_id,
            job_type=job_type,
            status="pending",
            created_at=datetime.now(UTC),
            metadata=metadata or {},
        )
        self.enqueued.append(job)
        return job

    async def claim_next(self, job_types=None):
        return None

    async def start(self, job_id: UUID):
        return None

    async def complete(self, job_id: UUID):
        return None

    async def fail(self, job_id: UUID, *, error_message: str | None = None):
        return None


# ─── Test Fixtures ───────────────────────────────────────────────────


@pytest.fixture
def agent_env(fake_workspaces, fake_repositories):
    sessions = FakeAgentSessionRepository()
    steps = FakeAgentStepRepository()
    tool_calls = FakeAgentToolCallRepository()
    approvals = FakeAgentApprovalRepository()
    job_queue = FakeAgentJobQueue()
    redis = MockRedis()
    coordinator = RedisAgentCoordinator(redis)
    publisher = InMemoryAgentEventPublisher()

    service = AgentService(
        sessions=sessions,
        steps=steps,
        tool_calls=tool_calls,
        approvals=approvals,
        workspaces=fake_workspaces,
        repositories=fake_repositories,
        job_queue=job_queue,
        coordinator=coordinator,
        event_publisher=publisher,
    )

    return {
        "service": service,
        "sessions": sessions,
        "steps": steps,
        "tool_calls": tool_calls,
        "approvals": approvals,
        "job_queue": job_queue,
        "redis": redis,
        "coordinator": coordinator,
        "publisher": publisher,
        "workspaces": fake_workspaces,
        "repositories": fake_repositories,
    }


@pytest.fixture
def agent_client(test_client, agent_env):
    test_client.app.dependency_overrides[get_agent_service] = lambda: agent_env["service"]
    test_client.app.dependency_overrides[get_cache_client_optional] = lambda: agent_env["redis"]
    yield test_client
    test_client.app.dependency_overrides.pop(get_agent_service, None)
    test_client.app.dependency_overrides.pop(get_cache_client_optional, None)


async def _create_workspace_and_user(
    fake_workspaces, user_id: UUID | None = None, role: WorkspaceRole = WorkspaceRole.OWNER
):
    uid = user_id or uuid4()
    w = await fake_workspaces.create(name="Agent WS", slug=f"agent-ws-{uuid4().hex[:6]}")
    await fake_workspaces.add_member(workspace_id=w.id, user_id=uid, role=role)
    return w, uid


def _auth_override(app, user_id: UUID):
    claims = AccessClaims(user_id=user_id, session_id=uuid4())
    app.dependency_overrides[validated_claims] = lambda: claims
    return claims


# ─── Tests ───────────────────────────────────────────────────────────


class TestAgentSessionEndpoints:
    @pytest.mark.asyncio
    async def test_create_session_success(self, agent_client, agent_env):
        app = agent_client.app
        w, user_id = await _create_workspace_and_user(
            agent_env["workspaces"], role=WorkspaceRole.OWNER
        )
        _auth_override(app, user_id)

        resp = agent_client.post(
            f"/v1/workspaces/{w.id}/agents",
            json={"objective": "Build automated indexing pipeline"},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True
        assert body["data"]["objective"] == "Build automated indexing pipeline"
        assert body["data"]["status"] == "created"
        assert body["data"]["workspace_id"] == str(w.id)

    @pytest.mark.asyncio
    async def test_create_session_unauthorized_for_non_member(self, agent_client, agent_env):
        app = agent_client.app
        w, _ = await _create_workspace_and_user(agent_env["workspaces"], role=WorkspaceRole.OWNER)
        outsider_id = uuid4()
        _auth_override(app, outsider_id)

        resp = agent_client.post(
            f"/v1/workspaces/{w.id}/agents",
            json={"objective": "Infiltrate workspace"},
        )
        assert resp.status_code == 403
        assert resp.json()["error"]["code"] == "workspace_access_denied"

    @pytest.mark.asyncio
    async def test_list_and_get_session_cross_workspace_idor_blocked(self, agent_client, agent_env):
        app = agent_client.app
        w1, u1 = await _create_workspace_and_user(agent_env["workspaces"], role=WorkspaceRole.OWNER)
        w2, u2 = await _create_workspace_and_user(agent_env["workspaces"], role=WorkspaceRole.OWNER)

        # Create session in w1
        session = await agent_env["sessions"].create(
            workspace_id=w1.id, user_id=u1, objective="w1 secret task"
        )

        # u2 tries to access w1 session via w2 URL -> 404 (IDOR prevented)
        _auth_override(app, u2)
        resp = agent_client.get(f"/v1/workspaces/{w2.id}/agents/{session.id}")
        assert resp.status_code == 404
        assert resp.json()["error"]["code"] == "agent_session_not_found"

        # u2 tries to access w1 session directly in w1 -> 403 (membership denied)
        resp2 = agent_client.get(f"/v1/workspaces/{w1.id}/agents/{session.id}")
        assert resp2.status_code == 403


class TestAgentExecutionLifecycle:
    @pytest.mark.asyncio
    async def test_run_session_enqueues_background_job(self, agent_client, agent_env):
        app = agent_client.app
        w, user_id = await _create_workspace_and_user(
            agent_env["workspaces"], role=WorkspaceRole.DEVELOPER
        )
        _auth_override(app, user_id)

        session = await agent_env["sessions"].create(
            workspace_id=w.id, user_id=user_id, objective="Launchable session"
        )

        resp = agent_client.post(f"/v1/workspaces/{w.id}/agents/{session.id}/run")
        assert resp.status_code == 200
        assert resp.json()["success"] is True

        # Verify durable job was enqueued
        assert len(agent_env["job_queue"].enqueued) == 1
        job = agent_env["job_queue"].enqueued[0]
        assert job.session_id == session.id
        assert job.job_type == "agent_execute"

        # Verify Redis wake-up notification was published
        assert ("forge:queue:agent_notify", "new_job") in agent_env["redis"].published

    @pytest.mark.asyncio
    async def test_run_already_active_session_rejected(self, agent_client, agent_env):
        app = agent_client.app
        w, user_id = await _create_workspace_and_user(
            agent_env["workspaces"], role=WorkspaceRole.DEVELOPER
        )
        _auth_override(app, user_id)

        session = await agent_env["sessions"].create(
            workspace_id=w.id,
            user_id=user_id,
            objective="Running session",
            status=AgentStatus.RUNNING,
        )

        resp = agent_client.post(f"/v1/workspaces/{w.id}/agents/{session.id}/run")
        assert resp.status_code == 422
        assert resp.json()["error"]["code"] == "agent_already_running"

    @pytest.mark.asyncio
    async def test_cancel_session_idempotent(self, agent_client, agent_env):
        app = agent_client.app
        w, user_id = await _create_workspace_and_user(
            agent_env["workspaces"], role=WorkspaceRole.DEVELOPER
        )
        _auth_override(app, user_id)

        session = await agent_env["sessions"].create(
            workspace_id=w.id,
            user_id=user_id,
            objective="Session to cancel",
            status=AgentStatus.RUNNING,
        )

        resp = agent_client.post(f"/v1/workspaces/{w.id}/agents/{session.id}/cancel")
        assert resp.status_code == 200
        assert resp.json()["data"]["status"] == "cancelled"

        # Check domain event emitted
        events = [e for e in agent_env["publisher"].events if e.session_id == session.id]
        assert len(events) == 1
        assert events[0].event_type.value == "agent.cancelled"

        # Second cancel is idempotent
        resp2 = agent_client.post(f"/v1/workspaces/{w.id}/agents/{session.id}/cancel")
        assert resp2.status_code == 200
        assert resp2.json()["data"]["status"] == "cancelled"


class TestAgentApprovalsAPI:
    @pytest.mark.asyncio
    async def test_grant_approval_success_resumes_worker(self, agent_client, agent_env):
        app = agent_client.app
        w, owner_id = await _create_workspace_and_user(
            agent_env["workspaces"], role=WorkspaceRole.OWNER
        )
        _auth_override(app, owner_id)

        session = await agent_env["sessions"].create(
            workspace_id=w.id,
            user_id=owner_id,
            objective="Approval test",
            status=AgentStatus.WAITING_FOR_APPROVAL,
        )
        tc = await agent_env["tool_calls"].create(
            session_id=session.id,
            tool_name="file.modify",
            arguments={"path": "src/main.py", "content": "updated"},
            risk_level=RiskLevel.HIGH,
            status=ToolCallStatus.PENDING_APPROVAL,
        )
        args_hash = compute_arguments_hash(tc.arguments)
        approval = await agent_env["approvals"].create(
            session_id=session.id,
            tool_call_id=tc.id,
            tool_name=tc.tool_name,
            arguments_hash=args_hash,
            expires_at=datetime.now(UTC) + timedelta(hours=1),
        )

        resp = agent_client.post(
            f"/v1/workspaces/{w.id}/agents/{session.id}/approvals/{approval.id}/grant",
            json={"reason": "Approved by owner"},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["data"]["status"] == "granted"

        # Verify session transitioned to RUNNING
        updated_session = await agent_env["sessions"].get(session.id)
        assert updated_session.status == AgentStatus.RUNNING

        # Verify AGENT_RESUME job enqueued
        assert len(agent_env["job_queue"].enqueued) == 1
        job = agent_env["job_queue"].enqueued[0]
        assert job.session_id == session.id
        assert job.job_type == "agent_resume"

    @pytest.mark.asyncio
    async def test_grant_approval_denied_for_developer_role(self, agent_client, agent_env):
        app = agent_client.app
        w, dev_id = await _create_workspace_and_user(
            agent_env["workspaces"], role=WorkspaceRole.DEVELOPER
        )
        _auth_override(app, dev_id)

        session = await agent_env["sessions"].create(
            workspace_id=w.id,
            user_id=dev_id,
            objective="Dev task",
            status=AgentStatus.WAITING_FOR_APPROVAL,
        )
        tc = await agent_env["tool_calls"].create(
            session_id=session.id,
            tool_name="file.delete",
            arguments={"path": "a"},
            risk_level=RiskLevel.HIGH,
        )

        approval = await agent_env["approvals"].create(
            session_id=session.id,
            tool_call_id=tc.id,
            tool_name=tc.tool_name,
            arguments_hash=compute_arguments_hash(tc.arguments),
        )

        resp = agent_client.post(
            f"/v1/workspaces/{w.id}/agents/{session.id}/approvals/{approval.id}/grant"
        )
        assert resp.status_code == 403
        assert resp.json()["error"]["code"] == "permission_denied"

    @pytest.mark.asyncio
    async def test_deny_approval_fails_tool_and_resumes_agent(self, agent_client, agent_env):
        app = agent_client.app
        w, owner_id = await _create_workspace_and_user(
            agent_env["workspaces"], role=WorkspaceRole.OWNER
        )
        _auth_override(app, owner_id)

        session = await agent_env["sessions"].create(
            workspace_id=w.id,
            user_id=owner_id,
            objective="Deny test",
            status=AgentStatus.WAITING_FOR_APPROVAL,
        )

        tc = await agent_env["tool_calls"].create(
            session_id=session.id,
            tool_name="git.commit",
            arguments={"message": "bad commit"},
            risk_level=RiskLevel.HIGH,
            status=ToolCallStatus.PENDING_APPROVAL,
        )
        approval = await agent_env["approvals"].create(
            session_id=session.id,
            tool_call_id=tc.id,
            tool_name=tc.tool_name,
            arguments_hash=compute_arguments_hash(tc.arguments),
        )

        resp = agent_client.post(
            f"/v1/workspaces/{w.id}/agents/{session.id}/approvals/{approval.id}/deny",
            json={"reason": "Commit message is invalid"},
        )
        assert resp.status_code == 200
        assert resp.json()["data"]["status"] == "denied"

        # Verify tool call was completed as failed
        updated_tc = await agent_env["tool_calls"].get(tc.id)
        assert updated_tc.status == ToolCallStatus.FAILED
        assert "Commit message is invalid" in (updated_tc.error_message or "")

        # Verify AGENT_RESUME was enqueued so agent loop receives the denial
        job = agent_env["job_queue"].enqueued[0]
        assert job.job_type == "agent_resume"


class TestAgentSSEEvents:
    @pytest.mark.asyncio
    async def test_sse_replay_and_secret_redaction(self, agent_client, agent_env):
        app = agent_client.app
        w, user_id = await _create_workspace_and_user(
            agent_env["workspaces"], role=WorkspaceRole.OWNER
        )
        _auth_override(app, user_id)

        session = await agent_env["sessions"].create(
            workspace_id=w.id,
            user_id=user_id,
            objective="SSE test",
            status=AgentStatus.COMPLETED,
        )

        # Push events into Redis replay buffer with embedded secrets
        replay_key = f"{EVENT_LOG_PREFIX}{session.id}"
        raw_event = json.dumps(
            {
                "id": "evt-101",
                "event_type": "tool_executed",
                "session_id": str(session.id),
                "payload": {
                    "secret": "ghp_1234567890abcdefghijklmnopqrstuvwxyz",
                    "normal": "hello",
                },
            }
        )
        await agent_env["redis"].rpush(replay_key, raw_event)

        url = f"/v1/workspaces/{w.id}/agents/{session.id}/events"
        with agent_client.stream("GET", url) as response:
            assert response.status_code == 200
            assert "text/event-stream" in response.headers["content-type"]

            # Read first chunk
            lines = []
            for line in response.iter_lines():
                if line:
                    lines.append(line)
                if len(lines) >= 3:
                    break

            content = "\n".join(lines)
            assert "id: evt-101" in content
            assert "event: tool_executed" in content
            assert "[REDACTED_GITHUB_TOKEN]" in content

    @pytest.mark.asyncio
    async def test_sse_redis_unavailable_fallback(self, agent_client, agent_env):
        app = agent_client.app
        w, user_id = await _create_workspace_and_user(
            agent_env["workspaces"], role=WorkspaceRole.OWNER
        )
        _auth_override(app, user_id)

        session = await agent_env["sessions"].create(
            workspace_id=w.id,
            user_id=user_id,
            objective="Fallback test",
            status=AgentStatus.COMPLETED,
        )

        # Override cache client to None (simulating Redis down)
        app.dependency_overrides[get_cache_client_optional] = lambda: None

        url = f"/v1/workspaces/{w.id}/agents/{session.id}/events"
        with agent_client.stream("GET", url) as response:
            assert response.status_code == 200
            lines = []
            for line in response.iter_lines():
                if line:
                    lines.append(line)
                if len(lines) >= 3:
                    break

            content = "\n".join(lines)
            assert "event: session.status" in content
            assert "completed" in content

    @pytest.mark.asyncio
    async def test_sse_filtering_by_last_event_id(self, agent_client, agent_env):
        app = agent_client.app
        w, user_id = await _create_workspace_and_user(
            agent_env["workspaces"], role=WorkspaceRole.OWNER
        )
        _auth_override(app, user_id)

        session = await agent_env["sessions"].create(
            workspace_id=w.id,
            user_id=user_id,
            objective="Filter test",
            status=AgentStatus.COMPLETED,
        )

        replay_key = f"{EVENT_LOG_PREFIX}{session.id}"
        await agent_env["redis"].rpush(
            replay_key,
            json.dumps({"id": "evt-1", "event_type": "step_1", "session_id": str(session.id)}),
        )
        await agent_env["redis"].rpush(
            replay_key,
            json.dumps({"id": "evt-2", "event_type": "step_2", "session_id": str(session.id)}),
        )
        await agent_env["redis"].rpush(
            replay_key,
            json.dumps({"id": "evt-3", "event_type": "step_3", "session_id": str(session.id)}),
        )

        # Request with Last-Event-ID: evt-2, should only receive evt-3
        headers = {"Last-Event-ID": "evt-2"}
        url = f"/v1/workspaces/{w.id}/agents/{session.id}/events"
        with agent_client.stream("GET", url, headers=headers) as response:
            assert response.status_code == 200
            content = "\n".join([line for line in response.iter_lines() if line])
            assert "id: evt-1" not in content
            assert "id: evt-2" not in content
            assert "id: evt-3" in content


class TestAgentIntrospectionEndpoints:
    @pytest.mark.asyncio
    async def test_get_steps_returns_sequence_order(self, agent_client, agent_env):
        app = agent_client.app
        w, user_id = await _create_workspace_and_user(
            agent_env["workspaces"], role=WorkspaceRole.DEVELOPER
        )
        _auth_override(app, user_id)

        session = await agent_env["sessions"].create(
            workspace_id=w.id, user_id=user_id, objective="Steps test"
        )
        await agent_env["steps"].create(session_id=session.id, sequence=2, objective="Step two")
        await agent_env["steps"].create(session_id=session.id, sequence=1, objective="Step one")

        resp = agent_client.get(f"/v1/workspaces/{w.id}/agents/{session.id}/steps")
        assert resp.status_code == 200
        steps = resp.json()["data"]
        assert len(steps) == 2
        assert steps[0]["sequence"] == 1
        assert steps[1]["sequence"] == 2

    @pytest.mark.asyncio
    async def test_get_tool_calls_pagination(self, agent_client, agent_env):
        app = agent_client.app
        w, user_id = await _create_workspace_and_user(
            agent_env["workspaces"], role=WorkspaceRole.DEVELOPER
        )
        _auth_override(app, user_id)

        session = await agent_env["sessions"].create(
            workspace_id=w.id, user_id=user_id, objective="Tool calls test"
        )
        for i in range(5):
            await agent_env["tool_calls"].create(
                session_id=session.id,
                tool_name=f"tool_{i}",
                arguments={},
                risk_level=RiskLevel.LOW,
            )

        resp = agent_client.get(
            f"/v1/workspaces/{w.id}/agents/{session.id}/tool-calls?limit=2&offset=1"
        )
        assert resp.status_code == 200
        calls = resp.json()["data"]
        assert len(calls) == 2
        assert calls[0]["tool_name"] == "tool_1"
        assert calls[1]["tool_name"] == "tool_2"

    @pytest.mark.asyncio
    async def test_get_approvals_list(self, agent_client, agent_env):
        app = agent_client.app
        w, user_id = await _create_workspace_and_user(
            agent_env["workspaces"], role=WorkspaceRole.DEVELOPER
        )
        _auth_override(app, user_id)

        session = await agent_env["sessions"].create(
            workspace_id=w.id, user_id=user_id, objective="Approvals test"
        )
        tc = await agent_env["tool_calls"].create(
            session_id=session.id,
            tool_name="git.commit",
            arguments={"message": "feat: init"},
            risk_level=RiskLevel.HIGH,
        )
        await agent_env["approvals"].create(
            session_id=session.id,
            tool_call_id=tc.id,
            tool_name=tc.tool_name,
            arguments_hash=compute_arguments_hash(tc.arguments),
        )

        resp = agent_client.get(f"/v1/workspaces/{w.id}/agents/{session.id}/approvals")
        assert resp.status_code == 200
        approvals = resp.json()["data"]
        assert len(approvals) == 1
        assert approvals[0]["tool_name"] == "git.commit"
        assert approvals[0]["status"] == "pending"


class TestAgentSecurityEdgeCases:
    @pytest.mark.asyncio
    async def test_viewer_role_cannot_run_or_cancel(self, agent_client, agent_env):
        app = agent_client.app
        w, viewer_id = await _create_workspace_and_user(
            agent_env["workspaces"], role=WorkspaceRole.VIEWER
        )
        _auth_override(app, viewer_id)

        session = await agent_env["sessions"].create(
            workspace_id=w.id, user_id=viewer_id, objective="Viewer test"
        )

        # Viewer running session -> 403
        run_resp = agent_client.post(f"/v1/workspaces/{w.id}/agents/{session.id}/run")
        assert run_resp.status_code == 403
        assert run_resp.json()["error"]["code"] == "permission_denied"

        # Viewer cancelling session -> 403
        cancel_resp = agent_client.post(f"/v1/workspaces/{w.id}/agents/{session.id}/cancel")
        assert cancel_resp.status_code == 403
        assert cancel_resp.json()["error"]["code"] == "permission_denied"

    @pytest.mark.asyncio
    async def test_grant_approval_tampered_hash_rejected(self, agent_client, agent_env):
        app = agent_client.app
        w, owner_id = await _create_workspace_and_user(
            agent_env["workspaces"], role=WorkspaceRole.OWNER
        )
        _auth_override(app, owner_id)

        session = await agent_env["sessions"].create(
            workspace_id=w.id,
            user_id=owner_id,
            objective="Tampered test",
            status=AgentStatus.WAITING_FOR_APPROVAL,
        )
        tc = await agent_env["tool_calls"].create(
            session_id=session.id,
            tool_name="terminal.execute",
            arguments={"cmd": "echo safe"},
            risk_level=RiskLevel.CRITICAL,
            status=ToolCallStatus.PENDING_APPROVAL,
        )
        approval = await agent_env["approvals"].create(
            session_id=session.id,
            tool_call_id=tc.id,
            tool_name=tc.tool_name,
            arguments_hash="different_tampered_hash",
        )

        resp = agent_client.post(
            f"/v1/workspaces/{w.id}/agents/{session.id}/approvals/{approval.id}/grant"
        )
        assert resp.status_code == 422
        assert resp.json()["error"]["code"] == "approval_hash_mismatch"

    @pytest.mark.asyncio
    async def test_grant_approval_expired_rejected(self, agent_client, agent_env):
        app = agent_client.app
        w, owner_id = await _create_workspace_and_user(
            agent_env["workspaces"], role=WorkspaceRole.OWNER
        )
        _auth_override(app, owner_id)

        session = await agent_env["sessions"].create(
            workspace_id=w.id,
            user_id=owner_id,
            objective="Expired test",
            status=AgentStatus.WAITING_FOR_APPROVAL,
        )
        tc = await agent_env["tool_calls"].create(
            session_id=session.id,
            tool_name="file.delete",
            arguments={"path": "critical.py"},
            risk_level=RiskLevel.HIGH,
            status=ToolCallStatus.PENDING_APPROVAL,
        )
        approval = await agent_env["approvals"].create(
            session_id=session.id,
            tool_call_id=tc.id,
            tool_name=tc.tool_name,
            arguments_hash=compute_arguments_hash(tc.arguments),
            expires_at=datetime.now(UTC) - timedelta(minutes=5),  # Expired!
        )

        resp = agent_client.post(
            f"/v1/workspaces/{w.id}/agents/{session.id}/approvals/{approval.id}/grant"
        )
        assert resp.status_code == 422
        assert resp.json()["error"]["code"] == "approval_expired"

    @pytest.mark.asyncio
    async def test_grant_approval_duplicate_rejected(self, agent_client, agent_env):
        app = agent_client.app
        w, owner_id = await _create_workspace_and_user(
            agent_env["workspaces"], role=WorkspaceRole.OWNER
        )
        _auth_override(app, owner_id)

        session = await agent_env["sessions"].create(
            workspace_id=w.id,
            user_id=owner_id,
            objective="Duplicate grant test",
            status=AgentStatus.WAITING_FOR_APPROVAL,
        )
        tc = await agent_env["tool_calls"].create(
            session_id=session.id,
            tool_name="file.create",
            arguments={"path": "a.txt"},
            risk_level=RiskLevel.HIGH,
            status=ToolCallStatus.PENDING_APPROVAL,
        )
        approval = await agent_env["approvals"].create(
            session_id=session.id,
            tool_call_id=tc.id,
            tool_name=tc.tool_name,
            arguments_hash=compute_arguments_hash(tc.arguments),
        )

        # First grant succeeds
        resp1 = agent_client.post(
            f"/v1/workspaces/{w.id}/agents/{session.id}/approvals/{approval.id}/grant"
        )
        assert resp1.status_code == 200

        # Second grant is rejected as already decided (or idempotent, but session is now running)
        resp2 = agent_client.post(
            f"/v1/workspaces/{w.id}/agents/{session.id}/approvals/{approval.id}/grant"
        )
        assert resp2.status_code == 422
        assert resp2.json()["error"]["code"] in (
            "tool_call_already_executed",
            "approval_already_decided",
        )

    @pytest.mark.asyncio
    async def test_approval_belonging_to_another_agent_rejected(self, agent_client, agent_env):
        app = agent_client.app
        w, owner_id = await _create_workspace_and_user(
            agent_env["workspaces"], role=WorkspaceRole.OWNER
        )
        _auth_override(app, owner_id)

        session_a = await agent_env["sessions"].create(
            workspace_id=w.id, user_id=owner_id, objective="Agent A"
        )
        session_b = await agent_env["sessions"].create(
            workspace_id=w.id, user_id=owner_id, objective="Agent B"
        )
        tc_b = await agent_env["tool_calls"].create(
            session_id=session_b.id,
            tool_name="file.delete",
            arguments={},
            risk_level=RiskLevel.HIGH,
        )
        approval_b = await agent_env["approvals"].create(
            session_id=session_b.id,
            tool_call_id=tc_b.id,
            tool_name=tc_b.tool_name,
            arguments_hash="hash_b",
        )

        # Access approval_b using session_a's URL -> 404 (IDOR blocked)
        resp = agent_client.post(
            f"/v1/workspaces/{w.id}/agents/{session_a.id}/approvals/{approval_b.id}/grant"
        )
        assert resp.status_code == 404
        assert resp.json()["error"]["code"] == "approval_not_found"

    @pytest.mark.asyncio
    async def test_repository_mismatch_rejected(self, agent_client, agent_env):
        app = agent_client.app
        w1, owner_id = await _create_workspace_and_user(
            agent_env["workspaces"], role=WorkspaceRole.OWNER
        )
        w2, _ = await _create_workspace_and_user(agent_env["workspaces"], role=WorkspaceRole.OWNER)
        _auth_override(app, owner_id)

        # Create repo in workspace 2
        repo_w2 = await agent_env["repositories"].create(
            workspace_id=w2.id,
            name="w2-repo",
            owner="test-owner",
            provider="github",
            clone_status="ready",
        )

        # Attempt to create agent session in workspace 1 tied to repo_w2 -> 404
        resp = agent_client.post(
            f"/v1/workspaces/{w1.id}/agents",
            json={
                "objective": "Cross-repo test",
                "repository_id": str(repo_w2.id),
            },
        )
        assert resp.status_code == 404
        assert resp.json()["error"]["code"] == "repository_not_found"

    @pytest.mark.asyncio
    async def test_cancellation_with_redis_unavailable(self, agent_client, agent_env):
        app = agent_client.app
        w, user_id = await _create_workspace_and_user(
            agent_env["workspaces"], role=WorkspaceRole.DEVELOPER
        )
        _auth_override(app, user_id)

        session = await agent_env["sessions"].create(
            workspace_id=w.id,
            user_id=user_id,
            objective="Durable cancel test",
            status=AgentStatus.RUNNING,
        )

        # Simulate service with no coordinator (Redis unavailable)
        service_no_redis = AgentService(
            sessions=agent_env["sessions"],
            steps=agent_env["steps"],
            tool_calls=agent_env["tool_calls"],
            approvals=agent_env["approvals"],
            workspaces=agent_env["workspaces"],
            repositories=agent_env["repositories"],
            job_queue=agent_env["job_queue"],
            coordinator=None,
            event_publisher=None,
        )
        app.dependency_overrides[get_agent_service] = lambda: service_no_redis

        resp = agent_client.post(f"/v1/workspaces/{w.id}/agents/{session.id}/cancel")
        assert resp.status_code == 200
        assert resp.json()["data"]["status"] == "cancelled"

        # Verify durable persistence in repository
        updated = await agent_env["sessions"].get(session.id)
        assert updated.status == AgentStatus.CANCELLED
        assert updated.cancelled_at is not None

    @pytest.mark.asyncio
    async def test_api_does_not_execute_tool_directly(self, agent_client, agent_env):
        app = agent_client.app
        w, owner_id = await _create_workspace_and_user(
            agent_env["workspaces"], role=WorkspaceRole.OWNER
        )
        _auth_override(app, owner_id)

        session = await agent_env["sessions"].create(
            workspace_id=w.id,
            user_id=owner_id,
            objective="No direct exec test",
            status=AgentStatus.WAITING_FOR_APPROVAL,
        )
        tc = await agent_env["tool_calls"].create(
            session_id=session.id,
            tool_name="terminal.execute",
            arguments={"command": "rm -rf /"},
            risk_level=RiskLevel.CRITICAL,
            status=ToolCallStatus.PENDING_APPROVAL,
        )
        approval = await agent_env["approvals"].create(
            session_id=session.id,
            tool_call_id=tc.id,
            tool_name=tc.tool_name,
            arguments_hash=compute_arguments_hash(tc.arguments),
        )

        resp = agent_client.post(
            f"/v1/workspaces/{w.id}/agents/{session.id}/approvals/{approval.id}/grant"
        )
        assert resp.status_code == 200

        # Tool call MUST NOT have been executed or populated with output by the API
        persisted_tc = await agent_env["tool_calls"].get(tc.id)
        assert persisted_tc.output is None
        assert persisted_tc.status in (
            ToolCallStatus.APPROVED,
            ToolCallStatus.PENDING_APPROVAL,
        )

        # Instead, durable AGENT_RESUME job was enqueued for the worker
        assert any(
            j.job_type == "agent_resume" and j.session_id == session.id
            for j in agent_env["job_queue"].enqueued
        )
