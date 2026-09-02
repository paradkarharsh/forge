"""LLM and conversation routes.

Exposes model listing, completion, streaming, conversation CRUD, message
history, and usage tracking under `/v1/llm` and `/v1/workspaces/{workspace_id}`.
"""
import asyncio
import logging
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from forge_api.application.llm import ConversationService
from forge_api.application.llm.usage_tracker import UsageTracker
from forge_api.domain.errors import ValidationError
from forge_api.domain.security import AccessClaims
from forge_api.infrastructure.llm.model_registry import ModelRegistry
from forge_api.presentation.http.contracts import ok
from forge_api.presentation.http.dependencies import (
    get_conversation_service,
    get_llm_gateway,
    get_model_registry,
    get_usage_tracker,
    validated_claims,
)

logger = logging.getLogger(__name__)

llm_router = APIRouter(prefix="/llm", tags=["llm"])
conversation_router = APIRouter(prefix="/workspaces", tags=["conversations"])
usage_router = APIRouter(prefix="/workspaces", tags=["usage"])


# ─── Request bodies ────────────────────────────────────────────────

class CompleteLLMInput(BaseModel):
    model: str = Field(min_length=1, max_length=128)
    messages: list[dict[str, str]] = Field(min_length=1, max_length=100)
    temperature: float | None = Field(default=None, ge=0.0, le=2.0)
    max_tokens: int | None = Field(default=None, gt=0, le=128_000)


class CreateConversationInput(BaseModel):
    title: str | None = Field(default=None, max_length=500)
    repository_id: UUID | None = None


class CompleteConversationInput(BaseModel):
    message: str = Field(min_length=1, max_length=32_768)
    context_repository_id: UUID | None = None
    model: str | None = Field(default=None, max_length=128)
    temperature: float | None = Field(default=None, ge=0.0, le=2.0)
    max_tokens: int | None = Field(default=None, gt=0, le=128_000)


class StreamConversationInput(BaseModel):
    message: str = Field(min_length=1, max_length=32_768)
    context_repository_id: UUID | None = None
    model: str | None = Field(default=None, max_length=128)
    temperature: float | None = Field(default=None, ge=0.0, le=2.0)
    max_tokens: int | None = Field(default=None, gt=0, le=128_000)


# ─── View helpers ──────────────────────────────────────────────────

def _conversation_view(c: Any) -> dict:
    return {
        "id": str(c.id),
        "workspace_id": str(c.workspace_id),
        "user_id": str(c.user_id),
        "title": c.title,
        "repository_id": str(c.repository_id) if c.repository_id else None,
        "status": c.status.value,
        "message_count": c.message_count,
        "created_at": c.created_at.isoformat(),
        "updated_at": c.updated_at.isoformat(),
    }


def _message_view(m: Any) -> dict:
    return {
        "id": str(m.id),
        "conversation_id": str(m.conversation_id),
        "role": m.role,
        "content": m.content,
        "provider": m.provider,
        "model": m.model,
        "prompt_version": m.prompt_version,
        "input_tokens": m.input_tokens,
        "output_tokens": m.output_tokens,
        "total_tokens": m.total_tokens,
        "duration_ms": m.duration_ms,
        "finish_reason": m.finish_reason,
        "status": m.status.value,
        "metadata": m.metadata,
        "created_at": m.created_at.isoformat(),
    }


# ─── LLM routes ────────────────────────────────────────────────────

@llm_router.get("/models")
async def list_models(
    registry: ModelRegistry = Depends(get_model_registry),
):
    """List available LLM models with capabilities and cost metadata."""
    models = registry.list_models(enabled_only=True)
    return ok([registry.model_view(m) for m in models])


@llm_router.post("/complete")
async def complete_llm(
    body: CompleteLLMInput,
    claims: AccessClaims = Depends(validated_claims),
    gateway=Depends(get_llm_gateway),
):
    """Run a non-streaming LLM completion (stateless, no conversation)."""
    from forge_api.domain.llm import ChatMessage, MessageRole

    if len(body.messages) == 0:
        raise ValidationError("messages must not be empty")

    messages = []
    for msg in body.messages:
        role_str = msg.get("role", "user")
        content = msg.get("content", "")
        if role_str == "system":
            role = MessageRole.SYSTEM
        elif role_str == "assistant":
            role = MessageRole.ASSISTANT
        else:
            role = MessageRole.USER
        messages.append(ChatMessage(role=role, content=content))

    response = await gateway.complete(
        messages=messages,
        model=body.model,
        temperature=body.temperature,
        max_tokens=body.max_tokens,
        user_id=claims.user_id,
    )

    return ok({
        "content": response.content,
        "finish_reason": response.finish_reason.value,
        "usage": {
            "input_tokens": response.usage.input_tokens,
            "output_tokens": response.usage.output_tokens,
            "total_tokens": response.usage.total_tokens,
        },
        "model": response.model,
        "provider": response.provider,
        "duration_ms": response.duration_ms,
    })


# ─── Conversation routes ───────────────────────────────────────────

@conversation_router.post("/{workspace_id}/conversations", status_code=201)
async def create_conversation(
    workspace_id: UUID,
    body: CreateConversationInput,
    claims: AccessClaims = Depends(validated_claims),
    svc: ConversationService = Depends(get_conversation_service),
):
    """Create a new conversation."""
    conversation = await svc.create_conversation(
        workspace_id=workspace_id,
        user_id=claims.user_id,
        title=body.title,
        repository_id=body.repository_id,
    )
    return ok(_conversation_view(conversation))


@conversation_router.get("/{workspace_id}/conversations")
async def list_conversations(
    workspace_id: UUID,
    limit: int = 50,
    offset: int = 0,
    claims: AccessClaims = Depends(validated_claims),
    svc: ConversationService = Depends(get_conversation_service),
):
    """List conversations for the authenticated user in a workspace."""
    conversations = await svc.list_conversations(
        workspace_id=workspace_id,
        user_id=claims.user_id,
        limit=limit,
        offset=offset,
    )
    count = await svc.count_conversations(
        workspace_id=workspace_id,
        user_id=claims.user_id,
    )
    return ok(
        [_conversation_view(c) for c in conversations],
        meta={"total": count, "limit": limit, "offset": offset},
    )


@conversation_router.get("/{workspace_id}/conversations/{conversation_id}")
async def get_conversation(
    workspace_id: UUID,
    conversation_id: UUID,
    claims: AccessClaims = Depends(validated_claims),
    svc: ConversationService = Depends(get_conversation_service),
):
    """Get a single conversation."""
    conversation = await svc.get_conversation(
        conversation_id=conversation_id,
        workspace_id=workspace_id,
        user_id=claims.user_id,
    )
    return ok(_conversation_view(conversation))


@conversation_router.delete("/{workspace_id}/conversations/{conversation_id}", status_code=204)
async def delete_conversation(
    workspace_id: UUID,
    conversation_id: UUID,
    claims: AccessClaims = Depends(validated_claims),
    svc: ConversationService = Depends(get_conversation_service),
):
    """Delete a conversation (soft delete)."""
    await svc.delete_conversation(
        conversation_id=conversation_id,
        workspace_id=workspace_id,
        user_id=claims.user_id,
    )


@conversation_router.get("/{workspace_id}/conversations/{conversation_id}/messages")
async def list_messages(
    workspace_id: UUID,
    conversation_id: UUID,
    limit: int = 50,
    offset: int = 0,
    claims: AccessClaims = Depends(validated_claims),
    svc: ConversationService = Depends(get_conversation_service),
):
    """List messages in a conversation."""
    messages = await svc.list_messages(
        conversation_id=conversation_id,
        workspace_id=workspace_id,
        user_id=claims.user_id,
        limit=limit,
        offset=offset,
    )
    count = await svc.count_messages(
        conversation_id=conversation_id,
        workspace_id=workspace_id,
        user_id=claims.user_id,
    )
    return ok(
        [_message_view(m) for m in messages],
        meta={"total": count, "limit": limit, "offset": offset},
    )


@conversation_router.post("/{workspace_id}/conversations/{conversation_id}/complete")
async def complete_conversation(
    workspace_id: UUID,
    conversation_id: UUID,
    body: CompleteConversationInput,
    claims: AccessClaims = Depends(validated_claims),
    svc: ConversationService = Depends(get_conversation_service),
):
    """Run a non-streaming completion within a conversation."""
    from forge_api.presentation.http.dependencies import get_context_assembly_service

    # Assemble context if repository specified
    context_window = None
    if body.context_repository_id is not None:
        context_svc = get_context_assembly_service()
        context_window = await context_svc.assemble(
            workspace_id=workspace_id,
            user_id=claims.user_id,
            query=body.message,
            repository_id=body.context_repository_id,
            session_id=claims.session_id,
            conversation_id=conversation_id,
        )

    user_msg, assistant_msg = await svc.complete(
        conversation_id=conversation_id,
        workspace_id=workspace_id,
        user_id=claims.user_id,
        user_message=body.message,
        context_window=context_window,
        model=body.model,
        temperature=body.temperature,
        max_tokens=body.max_tokens,
    )

    return ok({
        "user_message": _message_view(user_msg),
        "assistant_message": _message_view(assistant_msg),
    })


@conversation_router.post("/{workspace_id}/conversations/{conversation_id}/stream")
async def stream_conversation(
    workspace_id: UUID,
    conversation_id: UUID,
    body: StreamConversationInput,
    request: Request,
    claims: AccessClaims = Depends(validated_claims),
    svc: ConversationService = Depends(get_conversation_service),
):
    """Stream a completion within a conversation (SSE)."""
    from forge_api.presentation.http.dependencies import get_context_assembly_service

    # Assemble context if repository specified
    context_window = None
    if body.context_repository_id is not None:
        context_svc = get_context_assembly_service()
        context_window = await context_svc.assemble(
            workspace_id=workspace_id,
            user_id=claims.user_id,
            query=body.message,
            repository_id=body.context_repository_id,
            session_id=claims.session_id,
            conversation_id=conversation_id,
        )

    stream = await svc.stream(
        conversation_id=conversation_id,
        workspace_id=workspace_id,
        user_id=claims.user_id,
        user_message=body.message,
        context_window=context_window,
        model=body.model,
        temperature=body.temperature,
        max_tokens=body.max_tokens,
    )

    async def event_generator():
        """SSE event generator."""
        import json

        # Start event
        start_payload = {
            "conversation_id": str(stream.conversation_id),
            "message_id": str(stream.message_id),
            "model": stream.model,
        }
        yield "event: start\n"
        yield f"data: {json.dumps(start_payload)}\n\n"

        try:
            async for event_data in stream:
                event_type = event_data.get("event", "delta")
                data = event_data.get("data", {})
                yield f"event: {event_type}\n"
                yield f"data: {json.dumps(data)}\n\n"
        except asyncio.CancelledError:
            # Client disconnected
            await stream.cancel()
            yield "event: error\n"
            yield f'data: {json.dumps({"code": "cancelled", "message": "Stream cancelled"})}\n\n'
        except Exception as exc:
            logger.exception("Stream error")
            yield "event: error\n"
            yield f'data: {json.dumps({"code": "stream_error", "message": str(exc)[:200]})}\n\n'

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


# ─── Usage routes ──────────────────────────────────────────────────

@usage_router.get("/{workspace_id}/usage")
async def get_workspace_usage(
    workspace_id: UUID,
    user_id: UUID | None = None,
    limit: int = 100,
    offset: int = 0,
    claims: AccessClaims = Depends(validated_claims),
    tracker: UsageTracker = Depends(get_usage_tracker),
):
    """Get usage events for a workspace."""
    events = await tracker.get_workspace_usage(
        workspace_id=workspace_id,
        user_id=user_id,
        limit=limit,
        offset=offset,
    )
    aggregate = await tracker.get_workspace_aggregate(
        workspace_id=workspace_id,
        user_id=user_id,
    )
    return ok(
        {
            "events": [
                {
                    "id": str(e.id),
                    "workspace_id": str(e.workspace_id),
                    "user_id": str(e.user_id),
                    "conversation_id": str(e.conversation_id) if e.conversation_id else None,
                    "message_id": str(e.message_id) if e.message_id else None,
                    "provider": e.provider,
                    "model": e.model,
                    "input_tokens": e.input_tokens,
                    "output_tokens": e.output_tokens,
                    "total_tokens": e.total_tokens,
                    "duration_ms": e.duration_ms,
                    "estimated_cost": e.estimated_cost,
                    "created_at": e.created_at.isoformat(),
                }
                for e in events
            ],
            "aggregate": aggregate,
        },
        meta={"limit": limit, "offset": offset},
    )
