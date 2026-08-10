"""Background index worker.

Polls the pending index-job queue and runs the indexing pipeline for each
claimed job. The worker is deliberately decoupled from the API request
path: it creates its own sessions and service graph per job. Sequential
processing keeps behaviour simple and resource use bounded; the job claim
uses ``FOR UPDATE SKIP LOCKED`` so more workers can be added later without
rework.
"""
import asyncio
import logging

from forge_api.application.indexing.index_service import RepositoryIndexService
from forge_api.application.repositories.background_jobs import BackgroundJobService

logger = logging.getLogger(__name__)


class IndexWorker:
    """Consumes pending index jobs on a poll interval."""

    def __init__(
        self,
        *,
        session_factory,
        create_services,
        poll_seconds: int = 10,
    ) -> None:
        self._session_factory = session_factory
        self._create_services = create_services  # callable(session) -> (index_service, jobs)
        self._poll_seconds = poll_seconds

    async def run(self) -> None:
        """Poll loop; never raises (failures are logged per iteration)."""
        while True:
            await asyncio.sleep(self._poll_seconds)
            try:
                await self._process_one()
            except Exception:
                logger.exception("Index worker iteration failed")

    async def _process_one(self) -> None:
        async with self._session_factory() as db:
            index_service: RepositoryIndexService
            jobs: BackgroundJobService
            index_service, jobs = self._create_services(db)
            job = await jobs.claim_next_index_job()
            if job is None:
                return
            logger.info("Index worker processing job %s (repo %s)", job.id, job.repository_id)
            try:
                await jobs.start_job(job.id)
                stats = await index_service.index_repository(job.repository_id)
                await jobs.complete_job(job.id)
                await db.commit()
                logger.info(
                    "Indexed job %s: %s", job.id, stats
                )
            except Exception as exc:
                logger.exception("Index job %s failed", job.id)
                try:
                    await jobs.fail_job(
                        job.id, error_message=str(exc)[:2000]
                    )
                    await db.commit()
                except Exception:
                    await db.rollback()
                    logger.exception("Failed to record index job failure")