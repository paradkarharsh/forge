"""Unit tests for the repository background job service."""
from __future__ import annotations

from uuid import uuid4

import pytest

from forge_api.application.repositories.background_jobs import BackgroundJobService
from forge_api.domain.errors import NotFoundError


@pytest.fixture
def jobs_svc(fake_repositories, fake_sync_jobs):
    return BackgroundJobService(
        repositories=fake_repositories,
        sync_jobs=fake_sync_jobs,
    )


async def _setup_repo(fake_repositories):
    repo = await fake_repositories.create(
        workspace_id=uuid4(),
        name="widget",
        owner="alice",
        provider="github",
    )
    return repo


class TestEnqueue:
    @pytest.mark.asyncio
    async def test_enqueue_clone(self, jobs_svc, fake_repositories):
        repo = await _setup_repo(fake_repositories)
        job = await jobs_svc.enqueue_clone(repo.id)
        assert job.job_type == "clone"
        assert job.status.value == "pending"

    @pytest.mark.asyncio
    async def test_enqueue_sync(self, jobs_svc, fake_repositories):
        repo = await _setup_repo(fake_repositories)
        job = await jobs_svc.enqueue_sync(repo.id)
        assert job.job_type == "sync"

    @pytest.mark.asyncio
    async def test_enqueue_index(self, jobs_svc, fake_repositories):
        """The index queue exists but does not perform indexing."""
        repo = await _setup_repo(fake_repositories)
        job = await jobs_svc.enqueue_index(repo.id)
        assert job.job_type == "index"
        assert job.status.value == "pending"

    @pytest.mark.asyncio
    async def test_enqueue_missing_repo(self, jobs_svc):
        with pytest.raises(NotFoundError):
            await jobs_svc.enqueue_clone(uuid4())


class TestJobLifecycle:
    @pytest.mark.asyncio
    async def test_start_complete_job(self, jobs_svc, fake_repositories):
        repo = await _setup_repo(fake_repositories)
        job = await jobs_svc.enqueue_clone(repo.id)
        running = await jobs_svc.start_job(job.id)
        assert running.status.value == "running"
        completed = await jobs_svc.complete_job(job.id)
        assert completed.status.value == "completed"
        assert completed.completed_at is not None

    @pytest.mark.asyncio
    async def test_fail_job(self, jobs_svc, fake_repositories):
        repo = await _setup_repo(fake_repositories)
        job = await jobs_svc.enqueue_clone(repo.id)
        failed = await jobs_svc.fail_job(job.id, error_message="boom")
        assert failed.status.value == "failed"
        assert failed.error_message == "boom"

    @pytest.mark.asyncio
    async def test_get_missing_job(self, jobs_svc):
        with pytest.raises(NotFoundError):
            await jobs_svc.get_job(uuid4())

    @pytest.mark.asyncio
    async def test_list_jobs_filtered(self, jobs_svc, fake_repositories):
        repo = await _setup_repo(fake_repositories)
        await jobs_svc.enqueue_clone(repo.id)
        await jobs_svc.enqueue_sync(repo.id)
        await jobs_svc.enqueue_index(repo.id)
        clones = await jobs_svc.list_jobs(repo.id, job_type="clone")
        assert len(clones) == 1
        all_jobs = await jobs_svc.list_jobs(repo.id)
        assert len(all_jobs) == 3
