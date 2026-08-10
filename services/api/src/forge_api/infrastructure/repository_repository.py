"""SQLAlchemy adapter for the RepositoryRepository protocol."""
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from forge_api.domain.indexing import IndexStatus
from forge_api.domain.repository import (
    CloneStatus,
    RepositoryRecord,
    RepositoryVisibility,
    SyncStatus,
)
from forge_api.infrastructure.database.models import RepositoryModel

_SENTINEL = object()


def _to_record(model: RepositoryModel) -> RepositoryRecord:
    return RepositoryRecord(
        id=model.id,
        workspace_id=model.workspace_id,
        name=model.name,
        owner=model.owner,
        provider=model.provider,
        remote_url=model.remote_url,
        local_path=model.local_path,
        default_branch=model.default_branch,
        current_branch=model.current_branch,
        clone_status=CloneStatus(model.clone_status),
        sync_status=SyncStatus(model.sync_status),
        visibility=RepositoryVisibility(model.visibility),
        description=model.description,
        size_bytes=model.size_bytes,
        last_commit_hash=model.last_commit_hash,
        last_synced_at=model.last_synced_at,
        created_at=model.created_at,
        updated_at=model.updated_at,
        archived_at=model.archived_at,
        deleted_at=model.deleted_at,
        index_status=IndexStatus(model.index_status),
        indexed_at=model.indexed_at,
        file_count=model.file_count,
        symbol_count=model.symbol_count,
    )


class SqlRepositoryRepository:
    """Concrete SQLAlchemy implementation of ``RepositoryRepository``."""

    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def get(self, repository_id: UUID) -> RepositoryRecord | None:
        model = await self._db.get(RepositoryModel, repository_id)
        if not model or model.deleted_at:
            return None
        return _to_record(model)

    async def get_by_workspace(
        self,
        workspace_id: UUID,
        *,
        include_archived: bool = False,
        include_deleted: bool = False,
    ) -> list[RepositoryRecord]:
        stmt = select(RepositoryModel).where(
            RepositoryModel.workspace_id == workspace_id,
        )
        if not include_deleted:
            stmt = stmt.where(RepositoryModel.deleted_at.is_(None))
        if not include_archived:
            stmt = stmt.where(RepositoryModel.archived_at.is_(None))
        stmt = stmt.order_by(RepositoryModel.created_at.desc())
        rows = (await self._db.scalars(stmt)).all()
        return [_to_record(r) for r in rows]

    async def create(
        self,
        *,
        workspace_id: UUID,
        name: str,
        owner: str,
        provider: str,
        remote_url: str | None = None,
        local_path: str | None = None,
        default_branch: str | None = None,
        clone_status: str = "pending",
        sync_status: str = "idle",
        visibility: str = "private",
        description: str | None = None,
    ) -> RepositoryRecord:
        model = RepositoryModel(
            workspace_id=workspace_id,
            name=name,
            owner=owner,
            provider=provider,
            remote_url=remote_url,
            local_path=local_path,
            default_branch=default_branch,
            clone_status=clone_status,
            sync_status=sync_status,
            visibility=visibility,
            description=description,
        )
        self._db.add(model)
        await self._db.flush()
        return _to_record(model)

    async def update(
        self,
        repository_id: UUID,
        *,
        name: str | None = None,
        description: str | None = _SENTINEL,
        default_branch: str | None = _SENTINEL,
        current_branch: str | None = _SENTINEL,
        clone_status: str | None = None,
        sync_status: str | None = None,
        visibility: str | None = None,
        local_path: str | None = _SENTINEL,
        size_bytes: int | None = _SENTINEL,
        last_commit_hash: str | None = _SENTINEL,
        last_synced_at: datetime | None = _SENTINEL,
        index_status: str | None = None,
        indexed_at: datetime | None = _SENTINEL,
        file_count: int | None = _SENTINEL,
        symbol_count: int | None = _SENTINEL,
    ) -> RepositoryRecord | None:
        model = await self._db.get(RepositoryModel, repository_id)
        if not model or model.deleted_at:
            return None
        if name is not None:
            model.name = name
        if description is not _SENTINEL:
            model.description = description
        if default_branch is not _SENTINEL:
            model.default_branch = default_branch
        if current_branch is not _SENTINEL:
            model.current_branch = current_branch
        if clone_status is not None:
            model.clone_status = clone_status
        if sync_status is not None:
            model.sync_status = sync_status
        if visibility is not None:
            model.visibility = visibility
        if local_path is not _SENTINEL:
            model.local_path = local_path
        if size_bytes is not _SENTINEL:
            model.size_bytes = size_bytes
        if last_commit_hash is not _SENTINEL:
            model.last_commit_hash = last_commit_hash
        if last_synced_at is not _SENTINEL:
            model.last_synced_at = last_synced_at
        if index_status is not None:
            model.index_status = index_status
        if indexed_at is not _SENTINEL:
            model.indexed_at = indexed_at
        if file_count is not _SENTINEL:
            model.file_count = file_count
        if symbol_count is not _SENTINEL:
            model.symbol_count = symbol_count
        model.updated_at = datetime.now(UTC)
        await self._db.flush()
        return _to_record(model)

    async def soft_delete(self, repository_id: UUID) -> bool:
        model = await self._db.get(RepositoryModel, repository_id)
        if not model or model.deleted_at:
            return False
        model.deleted_at = datetime.now(UTC)
        model.updated_at = datetime.now(UTC)
        await self._db.flush()
        return True

    async def archive(self, repository_id: UUID) -> bool:
        model = await self._db.get(RepositoryModel, repository_id)
        if not model or model.deleted_at or model.archived_at:
            return False
        model.archived_at = datetime.now(UTC)
        model.updated_at = datetime.now(UTC)
        await self._db.flush()
        return True

    async def restore(self, repository_id: UUID) -> RepositoryRecord | None:
        model = await self._db.get(RepositoryModel, repository_id)
        if not model:
            return None
        model.archived_at = None
        model.deleted_at = None
        model.updated_at = datetime.now(UTC)
        await self._db.flush()
        return _to_record(model)
