"""PostgreSQL-backed agent job queue using SQLAlchemy and AgentSessionModel."""
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from forge_api.domain.agent import AgentStatus
from forge_api.domain.repositories import AgentJobRecord
from forge_api.domain.repository import SyncJobType
from forge_api.infrastructure.database.models import AgentSessionModel


def _dict_to_job(data: dict[str, Any]) -> AgentJobRecord:
    created_at = (
        datetime.fromisoformat(data["created_at"])
        if isinstance(data.get("created_at"), str)
        else data.get("created_at") or datetime.now(UTC)
    )
    started_at = (
        datetime.fromisoformat(data["started_at"])
        if isinstance(data.get("started_at"), str)
        else data.get("started_at")
    )
    completed_at = (
        datetime.fromisoformat(data["completed_at"])
        if isinstance(data.get("completed_at"), str)
        else data.get("completed_at")
    )
    sid = UUID(data["session_id"]) if isinstance(data["session_id"], str) else data["session_id"]
    return AgentJobRecord(
        id=UUID(data["id"]) if isinstance(data["id"], str) else data["id"],
        session_id=sid,
        job_type=data.get("job_type", SyncJobType.AGENT_EXECUTE.value),
        status=data.get("status", "pending"),
        created_at=created_at,
        started_at=started_at,
        completed_at=completed_at,
        error_message=data.get("error_message"),
        metadata=data.get("metadata") or {},
    )



class SqlAgentJobQueue:
    """PostgreSQL-backed implementation of AgentJobQueue.

    Persists background agent jobs durably in agent_sessions using FOR UPDATE SKIP LOCKED
    for transaction-safe, multi-worker concurrency.
    """

    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def enqueue(
        self,
        session_id: UUID,
        job_type: str,
        *,
        metadata: dict[str, Any] | None = None,
    ) -> AgentJobRecord:
        model = await self._db.get(AgentSessionModel, session_id)
        if not model:
            raise ValueError(f"Agent session {session_id} not found.")

        now = datetime.now(UTC)
        job_data = {
            "id": str(session_id),
            "session_id": str(session_id),
            "job_type": job_type,
            "status": "pending",
            "created_at": now.isoformat(),
            "started_at": None,
            "completed_at": None,
            "error_message": None,
            "metadata": metadata or {},
        }
        current_meta = dict(model.metadata_ or {})
        current_meta["_job"] = job_data
        model.metadata_ = current_meta
        await self._db.flush()
        return _dict_to_job(job_data)

    async def claim_next(
        self, job_types: list[str] | None = None
    ) -> AgentJobRecord | None:
        allowed_types = set(
            job_types
            or [SyncJobType.AGENT_EXECUTE.value, SyncJobType.AGENT_RESUME.value]
        )

        # Select candidate sessions FOR UPDATE SKIP LOCKED
        stmt = (
            select(AgentSessionModel)
            .where(
                AgentSessionModel.deleted_at.is_(None),
                AgentSessionModel.status.in_([
                    AgentStatus.CREATED.value,
                    AgentStatus.WAITING_FOR_APPROVAL.value,
                    AgentStatus.RUNNING.value,
                ]),
            )
            .order_by(AgentSessionModel.created_at.asc())
            .with_for_update(skip_locked=True)
        )
        candidates = (await self._db.scalars(stmt)).all()

        for model in candidates:
            meta = dict(model.metadata_ or {})
            job_data = meta.get("_job")

            # Case 1: Session has an explicitly enqueued job in metadata
            if job_data and job_data.get("status") == "pending":
                if job_data.get("job_type") in allowed_types:
                    job_data["status"] = "claimed"
                    meta["_job"] = job_data
                    model.metadata_ = meta
                    await self._db.flush()
                    return _dict_to_job(job_data)

            # Case 2: Session is in CREATED status and has not yet run
            elif (
                model.status == AgentStatus.CREATED.value
                and SyncJobType.AGENT_EXECUTE.value in allowed_types
                and (
                    not job_data
                    or job_data.get("status") not in ("claimed", "running", "completed")
                )
            ):
                job_data = {
                    "id": str(model.id),

                    "session_id": str(model.id),
                    "job_type": SyncJobType.AGENT_EXECUTE.value,
                    "status": "claimed",
                    "created_at": model.created_at.isoformat(),
                    "started_at": None,
                    "completed_at": None,
                    "error_message": None,
                    "metadata": {},
                }
                meta["_job"] = job_data
                model.metadata_ = meta
                await self._db.flush()
                return _dict_to_job(job_data)

        return None

    async def start(self, job_id: UUID) -> AgentJobRecord | None:
        model = await self._db.get(AgentSessionModel, job_id)
        if not model:
            return None

        meta = dict(model.metadata_ or {})
        job_data = meta.get("_job")
        if not job_data:
            return None

        now = datetime.now(UTC)
        job_data["status"] = "running"
        job_data["started_at"] = now.isoformat()
        meta["_job"] = job_data
        model.metadata_ = meta
        await self._db.flush()
        return _dict_to_job(job_data)

    async def complete(self, job_id: UUID) -> AgentJobRecord | None:
        model = await self._db.get(AgentSessionModel, job_id)
        if not model:
            return None

        meta = dict(model.metadata_ or {})
        job_data = meta.get("_job")
        if not job_data:
            return None

        now = datetime.now(UTC)
        job_data["status"] = "completed"
        job_data["completed_at"] = now.isoformat()
        meta["_job"] = job_data
        model.metadata_ = meta
        await self._db.flush()
        return _dict_to_job(job_data)

    async def fail(
        self, job_id: UUID, *, error_message: str | None = None
    ) -> AgentJobRecord | None:
        model = await self._db.get(AgentSessionModel, job_id)
        if not model:
            return None

        meta = dict(model.metadata_ or {})
        job_data = meta.get("_job")
        if not job_data:
            return None

        now = datetime.now(UTC)
        job_data["status"] = "failed"
        job_data["completed_at"] = now.isoformat()
        job_data["error_message"] = error_message
        meta["_job"] = job_data
        model.metadata_ = meta
        await self._db.flush()
        return _dict_to_job(job_data)
