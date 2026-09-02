import asyncio
from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest

from forge_api.domain.repositories import AgentJobRecord
from forge_api.domain.repository import SyncJobType
from forge_api.infrastructure.workers.agent_worker import (
    AGENT_NOTIFY_CHANNEL,
    AgentWorker,
    RedisAgentCoordinator,
)


class InMemoryAgentJobQueue:
    def __init__(self) -> None:
        self._jobs: dict[UUID, AgentJobRecord] = {}

    async def enqueue(
        self, session_id: UUID, job_type: str, *, metadata: dict | None = None
    ) -> AgentJobRecord:
        record = AgentJobRecord(
            id=uuid4(),
            session_id=session_id,
            job_type=job_type,
            status="pending",
            created_at=datetime.now(UTC),
            metadata=metadata or {},
        )
        self._jobs[record.id] = record
        return record

    async def claim_next(self, job_types: list[str] | None = None) -> AgentJobRecord | None:
        # FIFO claim of oldest pending job matching type
        for job in sorted(self._jobs.values(), key=lambda j: j.created_at):
            if job.status == "pending":
                if job_types is None or job.job_type in job_types:
                    # Update status to claimed
                    claimed = AgentJobRecord(
                        id=job.id,
                        session_id=job.session_id,
                        job_type=job.job_type,
                        status="claimed",
                        created_at=job.created_at,
                        metadata=job.metadata,
                    )
                    self._jobs[job.id] = claimed
                    return claimed
        return None

    async def start(self, job_id: UUID) -> AgentJobRecord | None:
        job = self._jobs.get(job_id)
        if not job:
            return None
        started = AgentJobRecord(
            id=job.id,
            session_id=job.session_id,
            job_type=job.job_type,
            status="running",
            created_at=job.created_at,
            started_at=datetime.now(UTC),
            metadata=job.metadata,
        )
        self._jobs[job_id] = started
        return started

    async def complete(self, job_id: UUID) -> AgentJobRecord | None:
        job = self._jobs.get(job_id)
        if not job:
            return None
        completed = AgentJobRecord(
            id=job.id,
            session_id=job.session_id,
            job_type=job.job_type,
            status="completed",
            created_at=job.created_at,
            started_at=job.started_at,
            completed_at=datetime.now(UTC),
            metadata=job.metadata,
        )
        self._jobs[job_id] = completed
        return completed

    async def fail(
        self, job_id: UUID, *, error_message: str | None = None
    ) -> AgentJobRecord | None:

        job = self._jobs.get(job_id)
        if not job:
            return None
        failed = AgentJobRecord(
            id=job.id,
            session_id=job.session_id,
            job_type=job.job_type,
            status="failed",
            created_at=job.created_at,
            started_at=job.started_at,
            completed_at=datetime.now(UTC),
            error_message=error_message,
            metadata=job.metadata,
        )
        self._jobs[job_id] = failed
        return failed


class MockRedis:
    def __init__(self) -> None:
        self.data: dict[str, str] = {}
        self.published: list[tuple[str, str]] = []

    async def get(self, key: str):
        return self.data.get(key)

    async def set(self, key: str, value: str, nx: bool = False, ex: int | None = None):
        if nx and key in self.data:
            return False
        self.data[key] = value
        return True

    async def delete(self, key: str):
        return self.data.pop(key, None) is not None

    async def expire(self, key: str, ttl: int):
        return key in self.data

    async def publish(self, channel: str, message: str):
        self.published.append((channel, message))
        return 1


class MockOrchestrator:
    def __init__(self) -> None:
        self.executed_sessions: list[UUID] = []
        self.resumed_sessions: list[UUID] = []

    async def run_session(self, session_id: UUID):
        self.executed_sessions.append(session_id)

    async def resume_session(self, session_id: UUID):
        self.resumed_sessions.append(session_id)


class TestAgentWorker:
    @pytest.mark.asyncio
    async def test_process_execute_job(self) -> None:
        job_queue = InMemoryAgentJobQueue()
        session_id = uuid4()
        await job_queue.enqueue(session_id, SyncJobType.AGENT_EXECUTE.value)

        orchestrator = MockOrchestrator()
        worker = AgentWorker(
            job_queue=job_queue,
            orchestrator_factory=lambda: orchestrator,
        )

        processed = await worker.process_one()
        assert processed is True
        assert session_id in orchestrator.executed_sessions

        # Verify job completed in queue
        jobs = list(job_queue._jobs.values())
        assert jobs[0].status == "completed"

    @pytest.mark.asyncio
    async def test_process_resume_job(self) -> None:
        job_queue = InMemoryAgentJobQueue()
        session_id = uuid4()
        await job_queue.enqueue(session_id, SyncJobType.AGENT_RESUME.value)

        orchestrator = MockOrchestrator()
        worker = AgentWorker(
            job_queue=job_queue,
            orchestrator_factory=lambda: orchestrator,
        )

        processed = await worker.process_one()
        assert processed is True
        assert session_id in orchestrator.resumed_sessions
        assert (list(job_queue._jobs.values()))[0].status == "completed"

    @pytest.mark.asyncio
    async def test_duplicate_session_prevention_via_lock(self) -> None:
        job_queue = InMemoryAgentJobQueue()
        session_id = uuid4()
        await job_queue.enqueue(session_id, SyncJobType.AGENT_EXECUTE.value)

        redis = MockRedis()
        coordinator1 = RedisAgentCoordinator(redis, worker_id="worker-1")
        coordinator2 = RedisAgentCoordinator(redis, worker_id="worker-2")

        # Worker 1 holds lock on this session
        await coordinator1.acquire_lock(session_id)

        orchestrator = MockOrchestrator()
        worker2 = AgentWorker(
            job_queue=job_queue,
            orchestrator_factory=lambda: orchestrator,
            coordinator=coordinator2,
        )

        # Worker 2 attempts to process the job but lock is held by Worker 1
        processed = await worker2.process_one()
        assert processed is False
        assert session_id not in orchestrator.executed_sessions

    @pytest.mark.asyncio
    async def test_cancellation_signaling_and_detection(self) -> None:
        redis = MockRedis()
        coordinator = RedisAgentCoordinator(redis)
        session_id = uuid4()

        assert await coordinator.is_cancelled(session_id) is False
        await coordinator.signal_cancellation(session_id)
        assert await coordinator.is_cancelled(session_id) is True

    @pytest.mark.asyncio
    async def test_redis_wake_up_notification(self) -> None:
        redis = MockRedis()
        coordinator = RedisAgentCoordinator(redis)
        await coordinator.notify_new_job()

        assert len(redis.published) == 1
        assert redis.published[0] == (AGENT_NOTIFY_CHANNEL, "new_job")

    @pytest.mark.asyncio
    async def test_recovery_when_redis_notification_missed(self) -> None:
        # Enqueue job directly without Redis notification
        job_queue = InMemoryAgentJobQueue()
        session_id = uuid4()
        await job_queue.enqueue(session_id, SyncJobType.AGENT_EXECUTE.value)

        orchestrator = MockOrchestrator()
        worker = AgentWorker(
            job_queue=job_queue,
            orchestrator_factory=lambda: orchestrator,
        )

        # Periodic poll tick discovers and processes the durable PostgreSQL job
        processed = await worker.process_one()
        assert processed is True
        assert session_id in orchestrator.executed_sessions

    @pytest.mark.asyncio
    async def test_worker_aborts_execution_on_lock_loss(self) -> None:
        redis = MockRedis()
        coordinator = RedisAgentCoordinator(redis)
        job_queue = InMemoryAgentJobQueue()
        session_id = uuid4()
        job = await job_queue.enqueue(session_id, SyncJobType.AGENT_EXECUTE.value)

        # Slow orchestrator that runs long enough for heartbeat to fire
        class SlowOrchestrator:
            async def run_session(self, sid: UUID):
                await asyncio.sleep(2.0)

            async def resume_session(self, sid: UUID):
                pass

        worker = AgentWorker(
            job_queue=job_queue,
            orchestrator_factory=lambda: SlowOrchestrator(),
            coordinator=coordinator,
            lock_ttl_seconds=1,  # Short TTL so heartbeat fires rapidly
        )

        task = asyncio.create_task(worker.process_one())
        await asyncio.sleep(0.1)

        # Simulate lock eviction / stolen by another worker
        await redis.delete(f"forge:agent:lock:{session_id}")

        processed = await task
        assert processed is False
        final_job = job_queue._jobs[job.id]
        assert final_job.status == "failed"
        assert "lock lost" in (final_job.error_message or "")

