"""Tests for SQLAlchemy persistence adapters for FP8 Agent entities."""
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from forge_api.domain.agent import (
    AgentSessionRecord,
    AgentStatus,
    AgentStepRecord,
    AgentToolCallRecord,
    StepStatus,
    ToolCallStatus,
)
from forge_api.domain.approval import (
    AgentApprovalRecord,
    ApprovalStatus,
)
from forge_api.domain.errors import DomainError
from forge_api.domain.repository import SyncJobType
from forge_api.domain.tool import RiskLevel
from forge_api.infrastructure.agent_approval_repository import (
    SqlAgentApprovalRepository,
)
from forge_api.infrastructure.agent_approval_repository import (
    _to_record as approval_to_record,
)
from forge_api.infrastructure.agent_job_queue import SqlAgentJobQueue
from forge_api.infrastructure.agent_session_repository import (
    _to_record as session_to_record,
)
from forge_api.infrastructure.agent_step_repository import (
    _to_record as step_to_record,
)
from forge_api.infrastructure.agent_tool_call_repository import (
    _to_record as tool_call_to_record,
)
from forge_api.infrastructure.database.models import (
    AgentApprovalModel,
    AgentSessionModel,
    AgentStepModel,
    AgentToolCallModel,
)


class TestModelRecordMappings:
    def test_session_model_to_record_mapping(self):
        sid = uuid4()
        wid = uuid4()
        uid = uuid4()
        now = datetime.now(UTC)
        model = AgentSessionModel(
            id=sid,
            workspace_id=wid,
            user_id=uid,
            objective="Test objective",
            status="running",
            model="gpt-4",
            limits={"max_llm_calls": 25, "max_wall_time_seconds": 600},
            metrics={"total_llm_calls": 5, "wall_time_seconds": 120.5},
            current_step=2,
            metadata_={"key": "val"},
            created_at=now,
            started_at=now,
        )
        rec = session_to_record(model)
        assert isinstance(rec, AgentSessionRecord)
        assert rec.id == sid
        assert rec.workspace_id == wid
        assert rec.status == AgentStatus.RUNNING
        assert rec.limits.max_llm_calls == 25
        assert rec.metrics.total_llm_calls == 5
        assert rec.current_step == 2
        assert rec.metadata == {"key": "val"}

    def test_step_model_to_record_mapping(self):
        step_id = uuid4()
        session_id = uuid4()
        now = datetime.now(UTC)
        model = AgentStepModel(
            id=step_id,
            session_id=session_id,
            sequence=1,
            objective="Step 1",
            status="running",
            metadata_={"tag": "init"},
            created_at=now,
        )
        rec = step_to_record(model)
        assert isinstance(rec, AgentStepRecord)
        assert rec.id == step_id
        assert rec.sequence == 1
        assert rec.status == StepStatus.RUNNING
        assert rec.metadata == {"tag": "init"}

    def test_tool_call_model_to_record_mapping(self):
        tc_id = uuid4()
        session_id = uuid4()
        now = datetime.now(UTC)
        model = AgentToolCallModel(
            id=tc_id,
            session_id=session_id,
            tool_name="file.create",
            arguments={"path": "a.txt"},
            risk_level="high",
            status="completed",
            output="file created",
            duration_ms=45.2,
            metadata_={"env": "test"},
            created_at=now,
        )
        rec = tool_call_to_record(model)
        assert isinstance(rec, AgentToolCallRecord)
        assert rec.tool_name == "file.create"
        assert rec.risk_level == RiskLevel.HIGH
        assert rec.status == ToolCallStatus.COMPLETED
        assert rec.duration_ms == 45.2

    def test_approval_model_to_record_mapping(self):
        app_id = uuid4()
        session_id = uuid4()
        tc_id = uuid4()
        now = datetime.now(UTC)
        model = AgentApprovalModel(
            id=app_id,
            session_id=session_id,
            tool_call_id=tc_id,
            tool_name="terminal.execute",
            arguments_hash="abc123hash",
            status="pending",
            reason=None,
            requested_at=now,
            metadata_={},
        )
        rec = approval_to_record(model)
        assert isinstance(rec, AgentApprovalRecord)
        assert rec.status == ApprovalStatus.PENDING
        assert rec.arguments_hash == "abc123hash"


class TestSqlAgentApprovalRepositoryDecide:
    @pytest.mark.asyncio
    async def test_decide_pending_to_granted(self):
        app_id = uuid4()
        model = AgentApprovalModel(
            id=app_id,
            session_id=uuid4(),
            tool_call_id=uuid4(),
            tool_name="file.modify",
            arguments_hash="hash",
            status="pending",
            requested_at=datetime.now(UTC),
            metadata_={},
        )

        db = AsyncMock()
        scalars_mock = MagicMock()
        scalars_mock.first.return_value = model
        db.scalars.return_value = scalars_mock

        repo = SqlAgentApprovalRepository(db)
        user_id = uuid4()
        decided = await repo.decide(
            app_id,
            status=ApprovalStatus.GRANTED,
            decided_by=user_id,
            reason="ok",
        )



        assert decided.status == ApprovalStatus.GRANTED
        assert decided.decided_by == user_id
        assert model.status == "granted"
        db.flush.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_decide_already_decided_same_status_is_idempotent(self):
        app_id = uuid4()
        user_id = uuid4()
        model = AgentApprovalModel(
            id=app_id,
            session_id=uuid4(),
            tool_call_id=uuid4(),
            tool_name="file.modify",
            arguments_hash="hash",
            status="granted",
            decided_by=user_id,
            requested_at=datetime.now(UTC),
            metadata_={},
        )

        db = AsyncMock()
        scalars_mock = MagicMock()
        scalars_mock.first.return_value = model
        db.scalars.return_value = scalars_mock

        repo = SqlAgentApprovalRepository(db)
        decided = await repo.decide(app_id, status=ApprovalStatus.GRANTED, decided_by=user_id)
        assert decided.status == ApprovalStatus.GRANTED

    @pytest.mark.asyncio
    async def test_decide_already_decided_different_status_raises_error(self):
        app_id = uuid4()
        model = AgentApprovalModel(
            id=app_id,
            session_id=uuid4(),
            tool_call_id=uuid4(),
            tool_name="file.modify",
            arguments_hash="hash",
            status="granted",
            requested_at=datetime.now(UTC),
            metadata_={},
        )

        db = AsyncMock()
        scalars_mock = MagicMock()
        scalars_mock.first.return_value = model
        db.scalars.return_value = scalars_mock

        repo = SqlAgentApprovalRepository(db)
        with pytest.raises(DomainError) as exc_info:
            await repo.decide(app_id, status=ApprovalStatus.DENIED, decided_by=uuid4())
        assert exc_info.value.code == "approval_already_decided"


class TestSqlAgentJobQueueOperations:
    @pytest.mark.asyncio
    async def test_job_queue_enqueue_and_claim(self):
        session_id = uuid4()
        model = AgentSessionModel(
            id=session_id,
            workspace_id=uuid4(),
            user_id=uuid4(),
            objective="Job queue test",
            status="created",
            limits={},
            metrics={},
            metadata_={},
            created_at=datetime.now(UTC),
        )

        db = AsyncMock()
        db.get.return_value = model
        queue = SqlAgentJobQueue(db)

        # 1. Enqueue job
        job = await queue.enqueue(session_id, SyncJobType.AGENT_EXECUTE.value)
        assert job.session_id == session_id
        assert job.job_type == SyncJobType.AGENT_EXECUTE.value
        assert job.status == "pending"
        assert model.metadata_["_job"]["status"] == "pending"

        # 2. Claim next job
        scalars_mock = MagicMock()
        scalars_mock.all.return_value = [model]
        db.scalars.return_value = scalars_mock

        claimed = await queue.claim_next([SyncJobType.AGENT_EXECUTE.value])
        assert claimed is not None
        assert claimed.session_id == session_id
        assert claimed.status == "claimed"
        assert model.metadata_["_job"]["status"] == "claimed"

        # 3. Start job
        started = await queue.start(session_id)
        assert started.status == "running"

        # 4. Complete job
        completed = await queue.complete(session_id)
        assert completed.status == "completed"
