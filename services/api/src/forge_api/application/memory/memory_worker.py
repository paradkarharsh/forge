"""Background memory maintenance worker.

Runs the periodic memory housekeeping loop (expiry, embedding backfill,
hard-delete) on a poll interval.  Follows the same shape as the FP5
``IndexWorker``: its own session per iteration, per-iteration error
isolation, and a ``create_services`` hook so the app builds the service
graph once.  Unlike ``IndexWorker`` it does not claim jobs from the sync
job queue — maintenance is workspace-global and time-based rather than
per-repository.
"""
import asyncio
import logging

from forge_api.application.memory.maintenance_service import (
    MemoryMaintenanceService,
)

logger = logging.getLogger(__name__)


class MemoryMaintenanceWorker:
    """Runs memory maintenance on a poll interval."""

    def __init__(
        self,
        *,
        session_factory,
        create_services,
        poll_seconds: int = 3600,
    ) -> None:
        self._session_factory = session_factory
        self._create_services = create_services  # callable(session) -> MemoryMaintenanceService
        self._poll_seconds = poll_seconds

    async def run(self) -> None:
        """Poll loop; never raises (failures are logged per iteration)."""
        while True:
            await asyncio.sleep(self._poll_seconds)
            try:
                await self._run_once()
            except Exception:
                logger.exception("Memory maintenance iteration failed")

    async def _run_once(self) -> None:
        async with self._session_factory() as db:
            service: MemoryMaintenanceService = self._create_services(db)
            results = await service.run()
            await db.commit()
            if any(results.values()):
                logger.info("Memory maintenance results: %s", results)
