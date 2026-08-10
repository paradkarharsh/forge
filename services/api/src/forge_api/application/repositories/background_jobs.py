"""Background job service for repository operations.

Provides infrastructure for clone, sync, and index queue jobs.
The indexing queue is created but does NOT yet perform indexing.
"""
import logging
from uuid import UUID

from forge_api.domain.errors import NotFoundError
from forge_api.domain.repositories import (
    RepositoryRepository,
    RepositorySyncJobRepository,
)
from forge_api.domain.repository import SyncJobRecord, SyncJobStatus, SyncJobType

logger = logging.getLogger(__name__)


class BackgroundJobService:
    """Manages background jobs for repository operations."""

    def __init__(
        self,
        *,
        repositories: RepositoryRepository,
        sync_jobs: RepositorySyncJobRepository,
    ) -> None:
        self._repos = repositories
        self._sync_jobs = sync_jobs

    async def enqueue_clone(self, repository_id: UUID) -> SyncJobRecord:
        """Create a clone job for a repository."""
        repo = await self._repos.get(repository_id)
        if not repo:
            raise NotFoundError("Repository not found")

        job = await self._sync_jobs.create(
            repository_id=repository_id,
            job_type=SyncJobType.CLONE,
            status=SyncJobStatus.PENDING,
        )
        logger.info("Enqueued clone job %s for repository %s", job.id, repository_id)
        return job

    async def enqueue_sync(self, repository_id: UUID) -> SyncJobRecord:
        """Create a sync job for a repository."""
        repo = await self._repos.get(repository_id)
        if not repo:
            raise NotFoundError("Repository not found")

        job = await self._sync_jobs.create(
            repository_id=repository_id,
            job_type=SyncJobType.SYNC,
            status=SyncJobStatus.PENDING,
        )
        logger.info("Enqueued sync job %s for repository %s", job.id, repository_id)
        return job

    async def enqueue_index(self, repository_id: UUID) -> SyncJobRecord:
        """Create an index job for a repository.

        NOTE: The indexing queue is created but does NOT perform indexing yet.
        This prepares the infrastructure for future indexing features.
        """
        repo = await self._repos.get(repository_id)
        if not repo:
            raise NotFoundError("Repository not found")

        job = await self._sync_jobs.create(
            repository_id=repository_id,
            job_type=SyncJobType.INDEX,
            status=SyncJobStatus.PENDING,
        )
        logger.info("Enqueued index job %s for repository %s", job.id, repository_id)
        return job

    async def get_job(self, job_id: UUID) -> SyncJobRecord:
        """Retrieve a specific job by ID."""
        job = await self._sync_jobs.get(job_id)
        if not job:
            raise NotFoundError("Job not found")
        return job

    async def list_jobs(
        self, repository_id: UUID, *, job_type: str | None = None
    ) -> list[SyncJobRecord]:
        """List jobs for a repository, optionally filtered by type."""
        return await self._sync_jobs.list_by_repository(
            repository_id, job_type=job_type
        )

    async def start_job(self, job_id: UUID) -> SyncJobRecord:
        """Mark a job as running."""
        job = await self._sync_jobs.update_status(
            job_id, status=SyncJobStatus.RUNNING
        )
        if not job:
            raise NotFoundError("Job not found")
        return job

    async def complete_job(self, job_id: UUID) -> SyncJobRecord:
        """Mark a job as completed."""
        job = await self._sync_jobs.update_status(
            job_id, status=SyncJobStatus.COMPLETED
        )
        if not job:
            raise NotFoundError("Job not found")
        return job

    async def fail_job(
        self, job_id: UUID, *, error_message: str | None = None
    ) -> SyncJobRecord:
        """Mark a job as failed."""
        job = await self._sync_jobs.update_status(
            job_id,
            status=SyncJobStatus.FAILED,
            error_message=error_message,
        )
        if not job:
            raise NotFoundError("Job not found")
        return job
