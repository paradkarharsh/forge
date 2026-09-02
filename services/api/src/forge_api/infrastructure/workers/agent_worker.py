"""Background worker runtime and Redis coordination for agent sessions.

Integrates:
- Durable PostgreSQL job claiming (FOR UPDATE SKIP LOCKED)
- Dual job types: AGENT_EXECUTE and AGENT_RESUME
- Redis distributed session locks (forge:agent:lock:{session_id}) with auto-renewal
- Redis cancellation detection (forge:agent:cancel:{session_id})
- Redis Pub/Sub wake-up (forge:queue:agent_notify) with durable polling fallback
"""
import asyncio
import logging
from collections.abc import Callable
from typing import Any
from uuid import UUID, uuid4

from forge_api.application.agent.orchestrator import AgentOrchestrator
from forge_api.domain.repositories import AgentJobQueue, AgentJobRecord
from forge_api.domain.repository import SyncJobType

logger = logging.getLogger(__name__)

AGENT_NOTIFY_CHANNEL = "forge:queue:agent_notify"
LOCK_PREFIX = "forge:agent:lock:"
CANCEL_PREFIX = "forge:agent:cancel:"
DEFAULT_LOCK_TTL = 60

# Lua script: atomically check ownership and extend expiration
_RENEW_SCRIPT = """
if redis.call('get', KEYS[1]) == ARGV[1] then
    return redis.call('expire', KEYS[1], ARGV[2])
else
    return 0
end
"""

# Lua script: atomically check ownership and delete key
_RELEASE_SCRIPT = """
if redis.call('get', KEYS[1]) == ARGV[1] then
    return redis.call('del', KEYS[1])
else
    return 0
end
"""


class RedisAgentCoordinator:
    """Redis-backed coordination for session locking, cancellation, and wake-up."""

    def __init__(self, redis: Any, worker_id: str | None = None) -> None:
        self._redis = redis
        self._worker_id = worker_id or str(uuid4())

    @property
    def worker_id(self) -> str:
        return self._worker_id

    async def acquire_lock(self, session_id: UUID, ttl_seconds: int = DEFAULT_LOCK_TTL) -> bool:
        """Acquire distributed session lock with NX and TTL."""
        key = f"{LOCK_PREFIX}{session_id}"
        try:
            res = await self._redis.set(key, self._worker_id, nx=True, ex=ttl_seconds)
            return bool(res)
        except Exception as exc:
            logger.warning("Failed to acquire Redis lock for session %s: %s", session_id, exc)
            return False

    async def renew_lock(self, session_id: UUID, ttl_seconds: int = DEFAULT_LOCK_TTL) -> bool:
        """Renew active session lock atomically if currently held by this worker."""
        key = f"{LOCK_PREFIX}{session_id}"
        try:
            if hasattr(self._redis, "eval"):
                res = await self._redis.eval(_RENEW_SCRIPT, 1, key, self._worker_id, ttl_seconds)
                return bool(res)
            # Fallback for simple mocks without eval
            val = await self._redis.get(key)
            val_str = val.decode("utf-8") if isinstance(val, bytes) else str(val) if val else None
            if val_str == self._worker_id:
                await self._redis.expire(key, ttl_seconds)
                return True
            return False
        except Exception as exc:
            logger.warning("Failed to renew Redis lock for session %s: %s", session_id, exc)
            return False

    async def release_lock(self, session_id: UUID) -> bool:
        """Release session lock atomically if held by this worker."""
        key = f"{LOCK_PREFIX}{session_id}"
        try:
            if hasattr(self._redis, "eval"):
                res = await self._redis.eval(_RELEASE_SCRIPT, 1, key, self._worker_id)
                return bool(res)
            # Fallback for simple mocks without eval
            val = await self._redis.get(key)
            val_str = val.decode("utf-8") if isinstance(val, bytes) else str(val) if val else None
            if val_str == self._worker_id:
                await self._redis.delete(key)
                return True
            return False
        except Exception as exc:
            logger.warning("Failed to release Redis lock for session %s: %s", session_id, exc)
            return False


    async def is_cancelled(self, session_id: UUID) -> bool:
        """Check if session cancellation has been signaled in Redis."""
        key = f"{CANCEL_PREFIX}{session_id}"
        try:
            val = await self._redis.get(key)
            return bool(val)
        except Exception:
            return False

    async def signal_cancellation(self, session_id: UUID, ttl_seconds: int = 3600) -> None:
        """Signal cancellation for a session."""
        key = f"{CANCEL_PREFIX}{session_id}"
        try:
            await self._redis.set(key, "1", ex=ttl_seconds)
        except Exception as exc:
            logger.warning("Failed to set cancellation flag in Redis: %s", exc)

    async def notify_new_job(self) -> None:
        """Publish wake-up notification for workers."""
        try:
            await self._redis.publish(AGENT_NOTIFY_CHANNEL, "new_job")
        except Exception as exc:
            logger.debug("Failed to publish agent notify event: %s", exc)


class AgentWorker:
    """Consumes and processes durable AGENT_EXECUTE and AGENT_RESUME jobs."""

    def __init__(
        self,
        *,
        job_queue: AgentJobQueue,
        orchestrator_factory: Callable[[], AgentOrchestrator],
        coordinator: RedisAgentCoordinator | None = None,
        poll_seconds: float = 2.0,
        lock_ttl_seconds: int = DEFAULT_LOCK_TTL,
    ) -> None:
        self._job_queue = job_queue
        self._orchestrator_factory = orchestrator_factory
        self._coordinator = coordinator
        self._poll_seconds = poll_seconds
        self._lock_ttl_seconds = lock_ttl_seconds
        self._running = False

    async def run(self) -> None:
        """Continuous worker execution loop with durable polling and wake-up fallback."""
        self._running = True
        logger.info("AgentWorker started (polling every %ss)", self._poll_seconds)

        while self._running:
            try:
                processed = await self.process_one()
                if not processed:
                    await asyncio.sleep(self._poll_seconds)
            except asyncio.CancelledError:
                logger.info("AgentWorker cancelled")
                break
            except Exception:
                logger.exception("AgentWorker encountered an unexpected error in poll loop")
                await asyncio.sleep(self._poll_seconds)

    def stop(self) -> None:
        """Signal the worker to stop after the current iteration."""
        self._running = False

    async def process_one(self) -> bool:
        """Claim and execute a single job from the queue.

        Returns True if a job was claimed and processed, False if queue is empty.
        """
        # 1. Claim next job using durable FOR UPDATE SKIP LOCKED
        job_types = [SyncJobType.AGENT_EXECUTE.value, SyncJobType.AGENT_RESUME.value]
        job: AgentJobRecord | None = await self._job_queue.claim_next(job_types)
        if not job:
            return False

        session_id = job.session_id
        logger.info(
            "Claimed agent job %s (type: %s, session: %s)",
            job.id,
            job.job_type,
            session_id,
        )


        # 2. Acquire Redis Distributed Session Lock to prevent duplicate concurrent execution
        lock_acquired = False
        heartbeat_task: asyncio.Task | None = None

        if self._coordinator:
            lock_acquired = await self._coordinator.acquire_lock(
                session_id, ttl_seconds=self._lock_ttl_seconds
            )
            if not lock_acquired:
                logger.warning(
                    "Could not acquire lock for session %s (concurrent worker active). Skipping.",
                    session_id,
                )
                # Fail or reset job so it can be picked up later when lock frees
                await self._job_queue.fail(
                    job.id, error_message="Session lock active on another worker."
                )
                return False

        # 3. Execute job through Orchestrator
        exec_task: asyncio.Task | None = None
        try:
            await self._job_queue.start(job.id)
            orchestrator = self._orchestrator_factory()

            if job.job_type == SyncJobType.AGENT_RESUME.value:
                exec_coro = orchestrator.resume_session(session_id)
            else:
                exec_coro = orchestrator.run_session(session_id)

            exec_task = asyncio.create_task(exec_coro)
            if self._coordinator:
                heartbeat_task = asyncio.create_task(
                    self._lock_heartbeat(session_id, exec_task)
                )

            await exec_task

            await self._job_queue.complete(job.id)
            logger.info("Completed agent job %s for session %s", job.id, session_id)
            return True
        except asyncio.CancelledError:
            logger.error(
                "Agent job %s for session %s aborted (lock lost or cancelled).",
                job.id,
                session_id,
            )
            try:
                await self._job_queue.fail(
                    job.id, error_message="Execution aborted: distributed lock lost."
                )
            except Exception:
                pass
            return False
        except Exception as exc:
            logger.exception("Agent job %s execution failed: %s", job.id, exc)
            try:
                await self._job_queue.fail(job.id, error_message=str(exc)[:2000])
            except Exception:
                pass
            return True
        finally:
            # 4. Clean up heartbeat & release lock
            if heartbeat_task:
                heartbeat_task.cancel()
                try:
                    await heartbeat_task
                except asyncio.CancelledError:
                    pass
            if self._coordinator and lock_acquired:
                await self._coordinator.release_lock(session_id)

    async def _lock_heartbeat(
        self, session_id: UUID, target_task: asyncio.Task | None = None
    ) -> None:
        """Renew distributed lock periodically while the job is active."""
        interval = max(1.0, self._lock_ttl_seconds / 2.0)
        while True:
            await asyncio.sleep(interval)
            if self._coordinator:
                renewed = await self._coordinator.renew_lock(
                    session_id, ttl_seconds=self._lock_ttl_seconds
                )
                if not renewed:
                    logger.error(
                        "Failed to renew distributed lock for session %s; "
                        "lock lost! Aborting execution.",
                        session_id,
                    )
                    if target_task and not target_task.done():
                        target_task.cancel()
                    break

