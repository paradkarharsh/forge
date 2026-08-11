"""Memory maintenance service.

Periodic housekeeping for the durable memory store:

1. Expire memories whose ``expires_at`` has passed (ACTIVE -> STALE).
2. Backfill embeddings for memories created while embeddings were disabled.
3. Hard-delete soft-deleted memories older than the grace period.

Stale memories are never auto-deleted: they remain queryable (when
explicitly requested) and can be re-confirmed or restored by users.
"""
import logging
from datetime import UTC, datetime, timedelta
from uuid import UUID

from forge_api.domain.memory import MemoryStatus
from forge_api.domain.repositories import MemoryRepository

logger = logging.getLogger(__name__)

_HARD_DELETE_GRACE_DAYS = 30


class MemoryMaintenanceService:
    """Maintenance operations over the memory store."""

    def __init__(
        self,
        *,
        memories: MemoryRepository,
        embedding,
        backfill_batch_size: int = 100,
        hard_delete_grace_days: int = _HARD_DELETE_GRACE_DAYS,
    ) -> None:
        self._memories = memories
        self._embedding = embedding
        self._backfill_batch_size = backfill_batch_size
        self._hard_delete_grace_days = hard_delete_grace_days

    async def run(self, now: datetime | None = None) -> dict:
        """Run all maintenance steps; never raises. Returns counts."""
        results: dict = {}
        try:
            results["expired"] = await self.expire_memories(now)
        except Exception:
            logger.exception("Memory expiry failed")
            results["expired"] = 0
        try:
            results["backfilled"] = await self.backfill_embeddings()
        except Exception:
            logger.exception("Memory embedding backfill failed")
            results["backfilled"] = 0
        try:
            results["hard_deleted"] = await self.hard_delete()
        except Exception:
            logger.exception("Memory hard-delete failed")
            results["hard_deleted"] = 0
        return results

    async def expire_memories(self, now: datetime | None = None) -> int:
        """Mark ACTIVE memories with a passed ``expires_at`` as STALE."""
        now = now or datetime.now(UTC)
        expired = await self._memories.find_expired(now, limit=self._backfill_batch_size)
        if not expired:
            return 0
        count = await self._memories.bulk_update_status(
            [m.id for m in expired], MemoryStatus.STALE.value
        )
        logger.info("Expired %d memories", count)
        return count

    async def backfill_embeddings(self) -> int:
        """Embed ACTIVE memories missing a vector when embeddings exist."""
        if self._embedding.dimension() is None:
            return 0
        missing = await self._memories.find_missing_embeddings(
            limit=self._backfill_batch_size,
        )
        if not missing:
            return 0
        updates: list[tuple[UUID, list[float]]] = []
        for memory in missing:
            try:
                vectors = await self._embedding.embed([memory.content])
                vector = vectors[0]
            except Exception:
                logger.warning(
                    "Embedding failed for memory %s during backfill", memory.id
                )
                continue
            if vector is not None:
                updates.append((memory.id, vector))
        count = await self._memories.bulk_update_embeddings(updates)
        logger.info("Backfilled embeddings for %d memories", count)
        return count

    async def hard_delete(self, now: datetime | None = None) -> int:
        """Hard-delete soft-deleted memories past the grace period."""
        now = now or datetime.now(UTC)
        cutoff = now - timedelta(days=self._hard_delete_grace_days)
        count = await self._memories.hard_delete_old(cutoff)
        if count:
            logger.info("Hard-deleted %d stale soft-deleted memories", count)
        return count
