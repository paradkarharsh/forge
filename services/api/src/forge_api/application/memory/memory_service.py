"""Memory application service.

Durable memory CRUD, search, lifecycle, authorization, audit, and
embedding-on-write.  Authorization is enforced here in the application
layer:

- create workspace/repository memory: OWNER / ADMIN / MAINTAINER
- create user memory: any workspace member, only for themselves
- read workspace/repository memory: any workspace member
- read user memory: only the owning user
- update/delete: creator OR workspace OWNER/ADMIN

The repository adapter independently enforces workspace isolation and
user ownership, so the HTTP layer is never the only guard.
"""
import logging
from datetime import datetime
from uuid import UUID

from forge_api.domain.audit import AuditEventType
from forge_api.domain.auth import WorkspaceRole
from forge_api.domain.errors import (
    AuthorizationError,
    NotFoundError,
    ValidationError,
)
from forge_api.domain.memory import MemoryRecord, MemoryScope, MemoryStatus
from forge_api.domain.repositories import MemoryRepository, WorkspaceRepository
from forge_api.infrastructure.audit import AuditLogger

logger = logging.getLogger(__name__)

_WRITE_ROLES = frozenset(
    {WorkspaceRole.OWNER, WorkspaceRole.ADMIN, WorkspaceRole.MAINTAINER}
)
_OWNER_ROLES = frozenset({WorkspaceRole.OWNER, WorkspaceRole.ADMIN})

_MAX_CONTENT_LENGTH = 16_384
_MAX_TAGS = 20
_MAX_TAG_LENGTH = 64


class MemoryService:
    """Manages the durable memory lifecycle within a workspace."""

    def __init__(
        self,
        *,
        memories: MemoryRepository,
        workspaces: WorkspaceRepository,
        embedding,
        audit: AuditLogger,
        max_content_length: int = _MAX_CONTENT_LENGTH,
        max_tags: int = _MAX_TAGS,
    ) -> None:
        self._memories = memories
        self._workspaces = workspaces
        self._embedding = embedding
        self._audit = audit
        self._max_content_length = max_content_length
        self._max_tags = max_tags

    # ─── Authorization helpers ──────────────────────────────────────

    async def _require_member(self, workspace_id: UUID, user_id: UUID):
        member = await self._workspaces.get_membership(workspace_id, user_id)
        if not member:
            raise AuthorizationError("Not a member of this workspace")
        return member

    async def _require_write_role(
        self, workspace_id: UUID, user_id: UUID,
    ):
        member = await self._require_member(workspace_id, user_id)
        if member.role not in _WRITE_ROLES:
            raise AuthorizationError("Insufficient workspace role")

    # ─── Create ─────────────────────────────────────────────────────

    async def create_memory(
        self,
        *,
        workspace_id: UUID,
        user_id: UUID,
        memory_type: str,
        scope: str,
        content: str,
        summary: str | None = None,
        repository_id: UUID | None = None,
        source_file_path: str | None = None,
        source_symbol_name: str | None = None,
        source_commit_hash: str | None = None,
        confidence: float = 1.0,
        tags: list[str] | None = None,
        expires_at: datetime | None = None,
    ) -> MemoryRecord:
        memory_type = memory_type.lower()
        scope = scope.lower()

        if memory_type not in {
            "decision",
            "convention",
            "fact",
            "preference",
            "summary",
            "annotation",
        }:
            raise ValidationError("Invalid memory_type")
        if scope not in {s.value for s in MemoryScope}:
            raise ValidationError("Invalid scope")
        if not content or not content.strip():
            raise ValidationError("content is required")
        if len(content) > self._max_content_length:
            raise ValidationError(
                f"content exceeds maximum length of {self._max_content_length}"
            )
        if not 0.0 <= confidence <= 1.0:
            raise ValidationError("confidence must be between 0.0 and 1.0")
        tags = self._validate_tags(tags)

        if scope == MemoryScope.USER.value:
            # Any member may create their own user memory, but never for
            # another user.
            await self._require_member(workspace_id, user_id)
            owner_user_id = user_id
        else:
            # Workspace and repository memories require a write role.
            await self._require_write_role(workspace_id, user_id)
            owner_user_id = None
            if scope == MemoryScope.REPOSITORY.value and repository_id is None:
                raise ValidationError(
                    "repository_id is required for repository-scoped memories"
                )

        # Embedding-on-write: optional, never blocks creation.
        embedding = None
        try:
            if self._embedding.dimension() is not None:
                vectors = await self._embedding.embed([content])
                embedding = vectors[0]
        except Exception:
            logger.warning(
                "Embedding failed during memory create; storing without vector"
            )

        record = await self._memories.create(
            workspace_id=workspace_id,
            repository_id=repository_id if scope == MemoryScope.REPOSITORY.value else None,
            user_id=owner_user_id,
            memory_type=memory_type,
            scope=scope,
            content=content,
            summary=summary,
            source_file_path=source_file_path,
            source_symbol_name=source_symbol_name,
            source_commit_hash=source_commit_hash,
            confidence=confidence,
            tags=tags,
            embedding=embedding,
            created_by=user_id,
            expires_at=expires_at,
        )
        self._audit.log(
            AuditEventType.MEMORY_CREATED,
            user_id=user_id,
            payload={
                "memory_id": str(record.id),
                "memory_type": record.memory_type,
                "scope": record.scope,
                "repository_id": str(record.repository_id)
                if record.repository_id
                else None,
            },
        )
        return record

    # ─── Read ───────────────────────────────────────────────────────

    async def get_memory(
        self, workspace_id: UUID, memory_id: UUID, user_id: UUID,
    ) -> MemoryRecord:
        await self._require_member(workspace_id, user_id)
        record = await self._memories.get(memory_id)
        if record is None or record.workspace_id != workspace_id:
            raise NotFoundError("Memory not found")
        if record.scope == MemoryScope.USER.value and record.user_id != user_id:
            raise AuthorizationError("Cannot read another user's memory")
        return record

    async def list_memories(
        self,
        *,
        workspace_id: UUID,
        user_id: UUID,
        memory_type: str | None = None,
        scope: str | None = None,
        status: str | None = None,
        tags: list[str] | None = None,
        repository_id: UUID | None = None,
        limit: int = 50,
    ) -> list[MemoryRecord]:
        await self._require_member(workspace_id, user_id)

        if scope == MemoryScope.USER.value:
            # User-scoped read: only the owning user's memories.
            return await self._memories.list_by_user(
                workspace_id,
                user_id,
                memory_type=memory_type,
                status=status,
                tags=tags,
                limit=limit,
            )
        if repository_id is not None:
            return await self._memories.list_by_repository(
                repository_id,
                memory_type=memory_type,
                status=status,
                tags=tags,
                limit=limit,
            )
        if scope == MemoryScope.REPOSITORY.value:
            raise ValidationError(
                "repository_id is required when scope=repository"
            )
        return await self._memories.list_by_workspace(
            workspace_id,
            memory_type=memory_type,
            status=status,
            tags=tags,
            limit=limit,
        )

    # ─── Update / lifecycle ─────────────────────────────────────────

    async def update_memory(
        self,
        *,
        workspace_id: UUID,
        memory_id: UUID,
        user_id: UUID,
        content: str | None = None,
        summary: str | None = None,
        confidence: float | None = None,
        tags: list[str] | None = None,
        expires_at: datetime | None = None,
    ) -> MemoryRecord:
        await self._require_owner_or_admin(workspace_id, memory_id, user_id)
        if content is not None:
            if not content.strip():
                raise ValidationError("content must not be empty")
            if len(content) > self._max_content_length:
                raise ValidationError(
                    f"content exceeds maximum length of {self._max_content_length}"
                )
        if confidence is not None and not 0.0 <= confidence <= 1.0:
            raise ValidationError("confidence must be between 0.0 and 1.0")
        tags = self._validate_tags(tags) if tags is not None else None

        embedding = ...
        if content is not None:
            try:
                if self._embedding.dimension() is not None:
                    vectors = await self._embedding.embed([content])
                    embedding = vectors[0]
                else:
                    embedding = None
            except Exception:
                logger.warning(
                    "Embedding failed during memory update; storing without vector"
                )
                embedding = None

        record = await self._memories.update(
            memory_id,
            content=content,
            summary=summary,
            confidence=confidence,
            tags=tags,
            embedding=embedding,
            expires_at=expires_at,
        )
        if record is None:
            raise NotFoundError("Memory not found")
        self._audit.log(
            AuditEventType.MEMORY_UPDATED,
            user_id=user_id,
            payload={
                "memory_id": str(memory_id),
                "changed_fields": [
                    f
                    for f, v in (
                        ("content", content),
                        ("summary", summary),
                        ("confidence", confidence),
                        ("tags", tags),
                    )
                    if v is not None
                ],
            },
        )
        return record

    async def delete_memory(
        self, workspace_id: UUID, memory_id: UUID, user_id: UUID,
    ) -> None:
        await self._require_owner_or_admin(workspace_id, memory_id, user_id)
        deleted = await self._memories.soft_delete(memory_id)
        if not deleted:
            raise NotFoundError("Memory not found")
        self._audit.log(
            AuditEventType.MEMORY_DELETED,
            user_id=user_id,
            payload={"memory_id": str(memory_id)},
        )

    async def archive_memory(
        self, workspace_id: UUID, memory_id: UUID, user_id: UUID,
    ) -> MemoryRecord:
        await self._require_owner_or_admin(workspace_id, memory_id, user_id)
        record = await self._memories.update(memory_id, status=MemoryStatus.ARCHIVED.value)
        if record is None:
            raise NotFoundError("Memory not found")
        self._audit.log(
            AuditEventType.MEMORY_ARCHIVED,
            user_id=user_id,
            payload={"memory_id": str(memory_id)},
        )
        return record

    async def restore_memory(
        self, workspace_id: UUID, memory_id: UUID, user_id: UUID,
    ) -> MemoryRecord:
        await self._require_owner_or_admin(workspace_id, memory_id, user_id)
        record = await self._memories.update(memory_id, status=MemoryStatus.ACTIVE.value)
        if record is None:
            raise NotFoundError("Memory not found")
        self._audit.log(
            AuditEventType.MEMORY_UPDATED,
            user_id=user_id,
            payload={"memory_id": str(memory_id), "action": "restored"},
        )
        return record

    async def reconfirm_memory(
        self, workspace_id: UUID, memory_id: UUID, user_id: UUID,
    ) -> MemoryRecord:
        """Explicitly re-confirm a stale memory back to ACTIVE."""
        await self._require_owner_or_admin(workspace_id, memory_id, user_id)
        record = await self._memories.update(memory_id, status=MemoryStatus.ACTIVE.value)
        if record is None:
            raise NotFoundError("Memory not found")
        self._audit.log(
            AuditEventType.MEMORY_UPDATED,
            user_id=user_id,
            payload={"memory_id": str(memory_id), "action": "reconfirmed"},
        )
        return record

    # ─── Search ─────────────────────────────────────────────────────

    async def search_memories(
        self,
        *,
        workspace_id: UUID,
        user_id: UUID,
        query: str | None = None,
        tags: list[str] | None = None,
        repository_id: UUID | None = None,
        limit: int = 20,
    ) -> dict:
        """Semantic search when embeddings exist; tag search otherwise.

        Returns ``{"available": bool, "results": [...]}`` so callers can
        degrade gracefully without embeddings.
        """
        await self._require_member(workspace_id, user_id)
        if not query and not tags:
            raise ValidationError("query or tags are required")

        semantic = False
        results: list[MemoryRecord] = []

        # Semantic path (only when embeddings enabled and a query is given).
        if query and self._embedding.dimension() is not None:
            try:
                vectors = await self._embedding.embed([query])
                query_embedding = vectors[0]
                if query_embedding is not None:
                    results = await self._memories.search_semantic(
                        workspace_id,
                        query_embedding,
                        repository_id=repository_id,
                        user_id=None,
                        limit=limit,
                    )
                    semantic = True
            except Exception:
                logger.warning("Semantic memory search failed; falling back")

        if not results and tags:
            results = await self._memories.search_by_tags(
                workspace_id,
                tags,
                repository_id=repository_id,
                limit=limit,
            )

        self._audit.log(
            AuditEventType.MEMORY_SEARCHED,
            user_id=user_id,
            payload={
                "query": (query or "")[:256],
                "tags": tags or [],
                "semantic": semantic,
                "result_count": len(results),
            },
        )
        return {"available": semantic, "results": results}

    # ─── Internal ───────────────────────────────────────────────────

    async def _require_owner_or_admin(
        self, workspace_id: UUID, memory_id: UUID, user_id: UUID,
    ) -> MemoryRecord:
        """Creator OR workspace OWNER/ADMIN may mutate a memory."""
        await self._require_member(workspace_id, user_id)
        member = await self._workspaces.get_membership(workspace_id, user_id)
        record = await self._memories.get(memory_id)
        if record is None or record.workspace_id != workspace_id:
            raise NotFoundError("Memory not found")
        if record.user_id is not None and record.user_id != user_id:
            # A user-scoped memory belongs to someone else: only an
            # OWNER/ADMIN may touch it.
            if not member or member.role not in _OWNER_ROLES:
                raise AuthorizationError(
                    "Cannot modify another user's memory"
                )
        return record

    def _validate_tags(self, tags: list[str] | None) -> list[str]:
        if not tags:
            return []
        if len(tags) > self._max_tags:
            raise ValidationError(f"Too many tags (max {self._max_tags})")
        cleaned: list[str] = []
        for tag in tags:
            tag = tag.strip().lower()
            if not tag:
                continue
            if len(tag) > _MAX_TAG_LENGTH:
                raise ValidationError(f"Tag too long (max {_MAX_TAG_LENGTH})")
            cleaned.append(tag)
        return cleaned
