"""SQLAlchemy adapter for the WorkspaceRepository protocol."""
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from forge_api.domain.auth import WorkspaceRole
from forge_api.domain.workspaces import MembershipRecord, WorkspaceRecord
from forge_api.infrastructure.database.models import MembershipModel, WorkspaceModel

_SENTINEL = object()


def _to_workspace(model: WorkspaceModel) -> WorkspaceRecord:
    return WorkspaceRecord(
        id=model.id,
        name=model.name,
        slug=model.slug,
        created_at=model.created_at,
        deleted_at=model.deleted_at,
        description=model.description,
    )


def _to_membership(model: MembershipModel) -> MembershipRecord:
    return MembershipRecord(
        workspace_id=model.workspace_id,
        user_id=model.user_id,
        role=WorkspaceRole(model.role),
        created_at=model.created_at,
    )


class SqlWorkspaceRepository:
    """Concrete SQLAlchemy implementation of ``WorkspaceRepository``."""

    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def list_for_user(
        self, user_id: UUID
    ) -> list[tuple[WorkspaceRecord, WorkspaceRole]]:
        rows = await self._db.execute(
            select(WorkspaceModel, MembershipModel.role)
            .join(MembershipModel)
            .where(
                MembershipModel.user_id == user_id,
                WorkspaceModel.deleted_at.is_(None),
            )
        )
        return [
            (_to_workspace(workspace), WorkspaceRole(role))
            for workspace, role in rows
        ]

    async def get(self, workspace_id: UUID) -> WorkspaceRecord | None:
        model = await self._db.get(WorkspaceModel, workspace_id)
        if not model or model.deleted_at:
            return None
        return _to_workspace(model)

    async def get_by_slug(self, slug: str) -> WorkspaceRecord | None:
        model = await self._db.scalar(
            select(WorkspaceModel).where(
                WorkspaceModel.slug == slug.lower(),
                WorkspaceModel.deleted_at.is_(None),
            )
        )
        return _to_workspace(model) if model else None

    async def get_membership(
        self, workspace_id: UUID, user_id: UUID
    ) -> MembershipRecord | None:
        model = await self._db.scalar(
            select(MembershipModel).where(
                MembershipModel.workspace_id == workspace_id,
                MembershipModel.user_id == user_id,
            )
        )
        return _to_membership(model) if model else None

    async def list_members(self, workspace_id: UUID) -> list[MembershipRecord]:
        rows = (
            await self._db.scalars(
                select(MembershipModel)
                .where(MembershipModel.workspace_id == workspace_id)
                .order_by(MembershipModel.created_at)
            )
        ).all()
        return [_to_membership(r) for r in rows]

    async def create(
        self, *, name: str, slug: str, description: str | None = None
    ) -> WorkspaceRecord:
        model = WorkspaceModel(name=name, slug=slug.lower(), description=description)
        self._db.add(model)
        await self._db.flush()
        return _to_workspace(model)

    async def add_member(
        self, *, workspace_id: UUID, user_id: UUID, role: WorkspaceRole
    ) -> None:
        self._db.add(
            MembershipModel(
                workspace_id=workspace_id,
                user_id=user_id,
                role=role.value,
            )
        )
        await self._db.flush()

    async def remove_member(self, workspace_id: UUID, user_id: UUID) -> bool:
        model = await self._db.scalar(
            select(MembershipModel).where(
                MembershipModel.workspace_id == workspace_id,
                MembershipModel.user_id == user_id,
            )
        )
        if not model:
            return False
        await self._db.delete(model)
        await self._db.flush()
        return True

    async def update_member_role(
        self, workspace_id: UUID, user_id: UUID, role: WorkspaceRole
    ) -> bool:
        result = await self._db.execute(
            update(MembershipModel)
            .where(
                MembershipModel.workspace_id == workspace_id,
                MembershipModel.user_id == user_id,
            )
            .values(role=role.value)
        )
        return result.rowcount > 0

    async def rename(self, workspace_id: UUID, name: str) -> WorkspaceRecord | None:
        model = await self._db.get(WorkspaceModel, workspace_id)
        if not model or model.deleted_at:
            return None
        model.name = name
        await self._db.flush()
        return _to_workspace(model)

    async def update(
        self,
        workspace_id: UUID,
        *,
        name: str | None = None,
        slug: str | None = None,
        description: str | None = _SENTINEL,
    ) -> WorkspaceRecord | None:
        model = await self._db.get(WorkspaceModel, workspace_id)
        if not model or model.deleted_at:
            return None
        if name is not None:
            model.name = name
        if slug is not None:
            model.slug = slug.lower()
        if description is not _SENTINEL:
            model.description = description
        await self._db.flush()
        return _to_workspace(model)

    async def soft_delete(self, workspace_id: UUID) -> bool:
        model = await self._db.get(WorkspaceModel, workspace_id)
        if not model or model.deleted_at:
            return False
        model.deleted_at = datetime.now(UTC)
        await self._db.flush()
        return True
