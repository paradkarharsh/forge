"""Memory and context routes.

Memory CRUD / search under ``/workspaces/{workspace_id}/memories``, context
assembly under ``/context/assemble``, and ephemeral conversation context
under ``/context/conversation``.  All endpoints use ``validated_claims``,
the global response envelope, centralized exception handling, and DI; the
presentation layer contains no SQLAlchemy logic.
"""
from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from forge_api.application.memory.context_assembly_service import (
    ContextAssemblyService,
)
from forge_api.application.memory.memory_service import MemoryService
from forge_api.domain.memory import (
    ConversationContextEntry,
    MemoryRecord,
)
from forge_api.domain.security import AccessClaims
from forge_api.infrastructure.conversation_context import (
    RedisConversationContextStore,
)
from forge_api.presentation.http.contracts import ok
from forge_api.presentation.http.dependencies import (
    get_context_assembly_service,
    get_conversation_context_store,
    get_memory_service,
    validated_claims,
)

memory_router = APIRouter(prefix="/workspaces", tags=["memories"])
context_router = APIRouter(prefix="/context", tags=["context"])


# ─── Request bodies ────────────────────────────────────────────────


class CreateMemoryInput(BaseModel):
    memory_type: str = Field(min_length=1, max_length=32)
    scope: str = Field(min_length=1, max_length=16)
    content: str = Field(min_length=1)
    summary: str | None = Field(default=None, max_length=1024)
    repository_id: UUID | None = None
    source_file_path: str | None = Field(default=None, max_length=2048)
    source_symbol_name: str | None = Field(default=None, max_length=512)
    source_commit_hash: str | None = Field(default=None, max_length=64)
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    tags: list[str] = Field(default_factory=list, max_length=20)
    expires_at: datetime | None = None


class UpdateMemoryInput(BaseModel):
    content: str | None = Field(default=None, min_length=1)
    summary: str | None = Field(default=None, max_length=1024)
    confidence: float | None = Field(default=None, ge=0.0, le=1.0)
    tags: list[str] | None = Field(default=None, max_length=20)
    expires_at: datetime | None = None


class SearchMemoriesInput(BaseModel):
    query: str | None = Field(default=None, max_length=512)
    tags: list[str] | None = Field(default=None, max_length=20)
    repository_id: UUID | None = None
    limit: int = Field(default=20, ge=1, le=100)


class AssembleContextInput(BaseModel):
    workspace_id: UUID
    query: str = Field(min_length=1, max_length=512)
    repository_id: UUID | None = None
    conversation_id: UUID | None = None
    max_tokens: int | None = Field(default=None, ge=256, le=65536)
    scope_filter: list[str] | None = None
    type_filter: list[str] | None = None


class ConversationAppendInput(BaseModel):
    role: str = Field(default="context", max_length=32)
    content: str = Field(min_length=1)
    source_ids: list[str] = Field(default_factory=list)


# ─── View helpers ──────────────────────────────────────────────────


def _memory_view(m: MemoryRecord) -> dict:
    return {
        "id": str(m.id),
        "workspace_id": str(m.workspace_id),
        "repository_id": str(m.repository_id) if m.repository_id else None,
        "memory_type": m.memory_type,
        "scope": m.scope,
        "status": m.status.value,
        "content": m.content,
        "summary": m.summary,
        "source_file_path": m.source_file_path,
        "source_symbol_name": m.source_symbol_name,
        "source_commit_hash": m.source_commit_hash,
        "confidence": m.confidence,
        "tags": list(m.tags),
        "has_embedding": m.embedding is not None,
        "created_at": m.created_at.isoformat(),
        "updated_at": m.updated_at.isoformat(),
        "accessed_at": m.accessed_at.isoformat() if m.accessed_at else None,
        "expires_at": m.expires_at.isoformat() if m.expires_at else None,
    }


def _memory_summary_view(m: MemoryRecord) -> dict:
    return {
        "id": str(m.id),
        "memory_type": m.memory_type,
        "scope": m.scope,
        "status": m.status.value,
        "content": m.content,
        "confidence": m.confidence,
        "tags": list(m.tags),
    }


def _conversation_entry_view(e: ConversationContextEntry) -> dict:
    return {
        "role": e.role,
        "content": e.content,
        "timestamp": e.timestamp.isoformat(),
        "source_ids": list(e.source_ids),
    }


# ─── Memory routes ─────────────────────────────────────────────────


@memory_router.post("/{workspace_id}/memories", status_code=201)
async def create_memory(
    workspace_id: UUID,
    body: CreateMemoryInput,
    claims: AccessClaims = Depends(validated_claims),
    svc: MemoryService = Depends(get_memory_service),
):
    memory = await svc.create_memory(
        workspace_id=workspace_id,
        user_id=claims.user_id,
        memory_type=body.memory_type,
        scope=body.scope,
        content=body.content,
        summary=body.summary,
        repository_id=body.repository_id,
        source_file_path=body.source_file_path,
        source_symbol_name=body.source_symbol_name,
        source_commit_hash=body.source_commit_hash,
        confidence=body.confidence,
        tags=body.tags,
        expires_at=body.expires_at,
    )
    return ok(_memory_view(memory))


@memory_router.get("/{workspace_id}/memories")
async def list_memories(
    workspace_id: UUID,
    memory_type: str | None = None,
    scope: str | None = None,
    status: str | None = None,
    tags: str | None = None,
    repository_id: UUID | None = None,
    limit: int = 50,
    claims: AccessClaims = Depends(validated_claims),
    svc: MemoryService = Depends(get_memory_service),
):
    tag_list = [t for t in tags.split(",") if t] if tags else None
    memories = await svc.list_memories(
        workspace_id=workspace_id,
        user_id=claims.user_id,
        memory_type=memory_type,
        scope=scope,
        status=status,
        tags=tag_list,
        repository_id=repository_id,
        limit=limit,
    )
    return ok([_memory_view(m) for m in memories])


@memory_router.get("/{workspace_id}/memories/{memory_id}")
async def get_memory(
    workspace_id: UUID,
    memory_id: UUID,
    claims: AccessClaims = Depends(validated_claims),
    svc: MemoryService = Depends(get_memory_service),
):
    memory = await svc.get_memory(workspace_id, memory_id, claims.user_id)
    return ok(_memory_view(memory))


@memory_router.patch("/{workspace_id}/memories/{memory_id}")
async def update_memory(
    workspace_id: UUID,
    memory_id: UUID,
    body: UpdateMemoryInput,
    claims: AccessClaims = Depends(validated_claims),
    svc: MemoryService = Depends(get_memory_service),
):
    memory = await svc.update_memory(
        workspace_id=workspace_id,
        memory_id=memory_id,
        user_id=claims.user_id,
        content=body.content,
        summary=body.summary,
        confidence=body.confidence,
        tags=body.tags,
        expires_at=body.expires_at,
    )
    return ok(_memory_view(memory))


@memory_router.delete("/{workspace_id}/memories/{memory_id}", status_code=204)
async def delete_memory(
    workspace_id: UUID,
    memory_id: UUID,
    claims: AccessClaims = Depends(validated_claims),
    svc: MemoryService = Depends(get_memory_service),
):
    await svc.delete_memory(workspace_id, memory_id, claims.user_id)


@memory_router.post("/{workspace_id}/memories/search")
async def search_memories(
    workspace_id: UUID,
    body: SearchMemoriesInput,
    claims: AccessClaims = Depends(validated_claims),
    svc: MemoryService = Depends(get_memory_service),
):
    result = await svc.search_memories(
        workspace_id=workspace_id,
        user_id=claims.user_id,
        query=body.query,
        tags=body.tags,
        repository_id=body.repository_id,
        limit=body.limit,
    )
    return ok(
        {
            "available": result["available"],
            "results": [_memory_summary_view(m) for m in result["results"]],
        }
    )


# ─── Context assembly route ────────────────────────────────────────


@context_router.post("/assemble")
async def assemble_context(
    body: AssembleContextInput,
    claims: AccessClaims = Depends(validated_claims),
    svc: ContextAssemblyService = Depends(get_context_assembly_service),
):
    window = await svc.assemble(
        workspace_id=body.workspace_id,
        user_id=claims.user_id,
        query=body.query,
        repository_id=body.repository_id,
        session_id=claims.session_id,
        conversation_id=body.conversation_id,
        max_tokens=body.max_tokens,
        scope_filter=body.scope_filter,
        type_filter=body.type_filter,
    )
    return ok(
        {
            "repository_id": str(window.repository_id)
            if window.repository_id
            else None,
            "workspace_id": str(window.workspace_id),
            "total_tokens": window.total_tokens,
            "truncated": window.truncated,
            "assembled_at": window.assembled_at.isoformat(),
            "entries": [
                {
                    "source": e.source.value,
                    "scope": e.scope.value,
                    "content": e.content,
                    "relevance_score": round(e.relevance_score, 4),
                    "source_id": str(e.source_id) if e.source_id else None,
                    "file_path": e.file_path,
                    "metadata": e.metadata,
                }
                for e in window.entries
            ],
        }
    )


# ─── Conversation context routes ───────────────────────────────────


@context_router.get("/conversation/{conversation_id}")
async def get_conversation(
    conversation_id: UUID,
    claims: AccessClaims = Depends(validated_claims),
    store: RedisConversationContextStore = Depends(get_conversation_context_store),
):
    entries = await store.get(claims.session_id, conversation_id)
    return ok([_conversation_entry_view(e) for e in entries])


@context_router.post("/conversation/{conversation_id}", status_code=201)
async def append_conversation(
    conversation_id: UUID,
    body: ConversationAppendInput,
    claims: AccessClaims = Depends(validated_claims),
    store: RedisConversationContextStore = Depends(get_conversation_context_store),
):
    entry = ConversationContextEntry(
        role=body.role,
        content=body.content,
        timestamp=datetime.now(),
        source_ids=body.source_ids,
    )
    await store.append(claims.session_id, conversation_id, entry)
    return ok(_conversation_entry_view(entry))


@context_router.delete("/conversation/{conversation_id}", status_code=204)
async def clear_conversation(
    conversation_id: UUID,
    claims: AccessClaims = Depends(validated_claims),
    store: RedisConversationContextStore = Depends(get_conversation_context_store),
):
    await store.clear(claims.session_id, conversation_id)
