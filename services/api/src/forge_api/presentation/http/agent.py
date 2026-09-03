"""Agent endpoints under /workspaces/{workspace_id}/agents.

Provides:
- Agent session CRUD, execution, cancellation
- Step and tool call introspection
- Human approval grant/deny lifecycle
- Real-time Server-Sent Events (SSE) streaming with bounded replay and live handoff
"""

import asyncio
import json
import logging
from collections.abc import AsyncGenerator
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from forge_api.application.agent.agent_service import AgentService
from forge_api.domain.agent import (
    AgentLimits,
    AgentSessionRecord,
    AgentStatus,
    AgentStepRecord,
    AgentToolCallRecord,
    is_terminal_agent_status,
)
from forge_api.domain.approval import AgentApprovalRecord
from forge_api.domain.security import AccessClaims
from forge_api.domain.tool import redact_secrets
from forge_api.infrastructure.agent.event_publisher import (
    EVENT_CHANNEL_PREFIX,
    EVENT_LOG_PREFIX,
)
from forge_api.presentation.http.contracts import ok
from forge_api.presentation.http.dependencies import (
    get_agent_service,
    get_cache_client_optional,
    validated_claims,
)

logger = logging.getLogger(__name__)

agent_router = APIRouter(tags=["agents"])


# ─── Request Models ───────────────────────────────────────────────────


class CreateAgentSessionRequest(BaseModel):
    objective: str = Field(..., min_length=1, max_length=10000)
    repository_id: UUID | None = None
    conversation_id: UUID | None = None
    model: str | None = Field(default=None, max_length=128)
    limits: dict[str, Any] | None = None
    metadata: dict[str, Any] | None = None


class GrantApprovalRequest(BaseModel):
    reason: str | None = Field(default=None, max_length=2000)


class DenyApprovalRequest(BaseModel):
    reason: str | None = Field(default=None, max_length=2000)


# ─── View Helpers ─────────────────────────────────────────────────────


def _session_view(session: AgentSessionRecord) -> dict[str, Any]:
    return {
        "id": str(session.id),
        "workspace_id": str(session.workspace_id),
        "user_id": str(session.user_id),
        "objective": session.objective,
        "status": session.status.value,
        "repository_id": str(session.repository_id) if session.repository_id else None,
        "conversation_id": str(session.conversation_id) if session.conversation_id else None,
        "model": session.model,
        "limits": {
            "max_wall_time_seconds": session.limits.max_wall_time_seconds,
            "max_llm_calls": session.limits.max_llm_calls,
            "max_tool_calls": session.limits.max_tool_calls,
            "max_output_bytes": session.limits.max_output_bytes,
            "max_observation_bytes": session.limits.max_observation_bytes,
        },
        "metrics": {
            "total_llm_calls": session.metrics.total_llm_calls,
            "total_llm_retries": getattr(session.metrics, "total_llm_retries", 0),
            "total_tool_calls": session.metrics.total_tool_calls,
            "total_input_tokens": session.metrics.total_input_tokens,
            "total_output_tokens": session.metrics.total_output_tokens,
            "wall_time_seconds": session.metrics.wall_time_seconds,
            "estimated_cost_usd": session.metrics.estimated_cost_usd,
        },
        "usage_summary": {
            "total_llm_calls": session.metrics.total_llm_calls,
            "total_llm_retries": getattr(session.metrics, "total_llm_retries", 0),
            "total_tool_calls": session.metrics.total_tool_calls,
            "total_input_tokens": session.metrics.total_input_tokens,
            "total_output_tokens": session.metrics.total_output_tokens,
            "wall_time_seconds": session.metrics.wall_time_seconds,
            "estimated_cost_usd": session.metrics.estimated_cost_usd,
        },
        "failure_reason": session.metadata.get("failure_reason") if session.metadata else None,
        "current_step": session.current_step,
        "metadata": session.metadata,
        "created_at": session.created_at.isoformat(),
        "started_at": session.started_at.isoformat() if session.started_at else None,
        "completed_at": session.completed_at.isoformat() if session.completed_at else None,
        "cancelled_at": session.cancelled_at.isoformat() if session.cancelled_at else None,
        "last_heartbeat_at": session.last_heartbeat_at.isoformat()
        if session.last_heartbeat_at
        else None,
    }


def _step_view(step: AgentStepRecord) -> dict[str, Any]:
    return {
        "id": str(step.id),
        "session_id": str(step.session_id),
        "sequence": step.sequence,
        "objective": step.objective,
        "status": step.status.value,
        "created_at": step.created_at.isoformat(),
        "started_at": step.started_at.isoformat() if step.started_at else None,
        "completed_at": step.completed_at.isoformat() if step.completed_at else None,
        "metadata": step.metadata,
    }


def _tool_call_view(tc: AgentToolCallRecord) -> dict[str, Any]:
    return {
        "id": str(tc.id),
        "session_id": str(tc.session_id),
        "step_id": str(tc.step_id) if tc.step_id else None,
        "tool_name": tc.tool_name,
        "arguments": tc.arguments,
        "risk_level": tc.risk_level.value,
        "status": tc.status.value,
        "approval_id": str(tc.approval_id) if tc.approval_id else None,
        "output": tc.output,
        "error_message": tc.error_message,
        "duration_ms": tc.duration_ms,
        "created_at": tc.created_at.isoformat(),
        "started_at": tc.started_at.isoformat() if tc.started_at else None,
        "completed_at": tc.completed_at.isoformat() if tc.completed_at else None,
        "metadata": tc.metadata,
    }


def _approval_view(approval: AgentApprovalRecord) -> dict[str, Any]:
    return {
        "id": str(approval.id),
        "session_id": str(approval.session_id),
        "tool_call_id": str(approval.tool_call_id),
        "tool_name": approval.tool_name,
        "arguments_hash": approval.arguments_hash,
        "status": approval.status.value,
        "requested_by": str(approval.requested_by) if approval.requested_by else None,
        "decided_by": str(approval.decided_by) if approval.decided_by else None,
        "reason": approval.reason,
        "requested_at": approval.requested_at.isoformat(),
        "decided_at": approval.decided_at.isoformat() if approval.decided_at else None,
        "expires_at": approval.expires_at.isoformat() if approval.expires_at else None,
        "metadata": approval.metadata,
    }


# ─── Endpoints ────────────────────────────────────────────────────────


@agent_router.post("/workspaces/{workspace_id}/agents")
async def create_agent_session(
    workspace_id: UUID,
    payload: CreateAgentSessionRequest,
    claims: AccessClaims = Depends(validated_claims),
    service: AgentService = Depends(get_agent_service),
) -> Any:
    limits = AgentLimits(**payload.limits) if payload.limits else None
    session = await service.create_session(
        workspace_id=workspace_id,
        user_id=claims.user_id,
        objective=payload.objective,
        repository_id=payload.repository_id,
        conversation_id=payload.conversation_id,
        model=payload.model,
        limits=limits,
        metadata=payload.metadata,
    )
    return ok(data=_session_view(session))


@agent_router.get("/workspaces/{workspace_id}/agents")
async def list_agent_sessions(
    workspace_id: UUID,
    repository_id: UUID | None = None,
    status: str | None = None,
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    claims: AccessClaims = Depends(validated_claims),
    service: AgentService = Depends(get_agent_service),
) -> Any:
    status_enum = AgentStatus(status) if status else None
    sessions, total = await service.list_sessions(
        workspace_id=workspace_id,
        user_id=claims.user_id,
        repository_id=repository_id,
        status=status_enum,
        limit=limit,
        offset=offset,
    )
    return ok(
        data=[_session_view(s) for s in sessions],
        meta={"total": total, "limit": limit, "offset": offset},
    )


@agent_router.get("/workspaces/{workspace_id}/agents/{agent_id}")
async def get_agent_session(
    workspace_id: UUID,
    agent_id: UUID,
    claims: AccessClaims = Depends(validated_claims),
    service: AgentService = Depends(get_agent_service),
) -> Any:
    session = await service.get_session(
        workspace_id=workspace_id,
        session_id=agent_id,
        user_id=claims.user_id,
    )
    return ok(data=_session_view(session))


@agent_router.post("/workspaces/{workspace_id}/agents/{agent_id}/run")
async def run_agent_session(
    workspace_id: UUID,
    agent_id: UUID,
    claims: AccessClaims = Depends(validated_claims),
    service: AgentService = Depends(get_agent_service),
) -> Any:
    session = await service.run_session(
        workspace_id=workspace_id,
        session_id=agent_id,
        user_id=claims.user_id,
    )
    return ok(data=_session_view(session))


@agent_router.post("/workspaces/{workspace_id}/agents/{agent_id}/cancel")
async def cancel_agent_session(
    workspace_id: UUID,
    agent_id: UUID,
    claims: AccessClaims = Depends(validated_claims),
    service: AgentService = Depends(get_agent_service),
) -> Any:
    session = await service.cancel_session(
        workspace_id=workspace_id,
        session_id=agent_id,
        user_id=claims.user_id,
    )
    return ok(data=_session_view(session))


@agent_router.get("/workspaces/{workspace_id}/agents/{agent_id}/steps")
async def get_agent_steps(
    workspace_id: UUID,
    agent_id: UUID,
    claims: AccessClaims = Depends(validated_claims),
    service: AgentService = Depends(get_agent_service),
) -> Any:
    steps = await service.get_steps(
        workspace_id=workspace_id,
        session_id=agent_id,
        user_id=claims.user_id,
    )
    return ok(data=[_step_view(s) for s in steps])


@agent_router.get("/workspaces/{workspace_id}/agents/{agent_id}/tool-calls")
async def get_agent_tool_calls(
    workspace_id: UUID,
    agent_id: UUID,
    limit: int = Query(default=100, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    claims: AccessClaims = Depends(validated_claims),
    service: AgentService = Depends(get_agent_service),
) -> Any:
    tool_calls = await service.get_tool_calls(
        workspace_id=workspace_id,
        session_id=agent_id,
        user_id=claims.user_id,
        limit=limit,
        offset=offset,
    )
    return ok(data=[_tool_call_view(tc) for tc in tool_calls])


@agent_router.get("/workspaces/{workspace_id}/agents/{agent_id}/approvals")
async def get_agent_approvals(
    workspace_id: UUID,
    agent_id: UUID,
    claims: AccessClaims = Depends(validated_claims),
    service: AgentService = Depends(get_agent_service),
) -> Any:
    approvals = await service.get_approvals(
        workspace_id=workspace_id,
        session_id=agent_id,
        user_id=claims.user_id,
    )
    return ok(data=[_approval_view(a) for a in approvals])


@agent_router.post("/workspaces/{workspace_id}/agents/{agent_id}/approvals/{approval_id}/grant")
async def grant_agent_approval(
    workspace_id: UUID,
    agent_id: UUID,
    approval_id: UUID,
    payload: GrantApprovalRequest | None = None,
    claims: AccessClaims = Depends(validated_claims),
    service: AgentService = Depends(get_agent_service),
) -> Any:
    reason = payload.reason if payload else None
    approval = await service.grant_approval(
        workspace_id=workspace_id,
        session_id=agent_id,
        approval_id=approval_id,
        user_id=claims.user_id,
        reason=reason,
    )
    return ok(data=_approval_view(approval))


@agent_router.post("/workspaces/{workspace_id}/agents/{agent_id}/approvals/{approval_id}/deny")
async def deny_agent_approval(
    workspace_id: UUID,
    agent_id: UUID,
    approval_id: UUID,
    payload: DenyApprovalRequest | None = None,
    claims: AccessClaims = Depends(validated_claims),
    service: AgentService = Depends(get_agent_service),
) -> Any:
    reason = payload.reason if payload else None
    approval = await service.deny_approval(
        workspace_id=workspace_id,
        session_id=agent_id,
        approval_id=approval_id,
        user_id=claims.user_id,
        reason=reason,
    )
    return ok(data=_approval_view(approval))


# ─── SSE Streaming Endpoint ───────────────────────────────────────────


@agent_router.get("/workspaces/{workspace_id}/agents/{agent_id}/events")
async def stream_agent_events(
    workspace_id: UUID,
    agent_id: UUID,
    request: Request,
    last_event_id: str | None = Query(default=None),
    claims: AccessClaims = Depends(validated_claims),
    service: AgentService = Depends(get_agent_service),
    redis: Any = Depends(get_cache_client_optional),
) -> StreamingResponse:
    # 1. Authorize session access
    session = await service.get_session(
        workspace_id=workspace_id,
        session_id=agent_id,
        user_id=claims.user_id,
    )

    header_last_id = request.headers.get("last-event-id") or last_event_id

    async def event_generator() -> AsyncGenerator[str, None]:
        seen_ids: set[str] = set()

        # Branch A: Fallback when Redis is unavailable
        if not redis:
            status_payload = json.dumps({"status": session.status.value})
            yield f"id: {agent_id}\nevent: session.status\ndata: {status_payload}\n\n"
            if is_terminal_agent_status(session.status):
                return
            while True:
                if await request.is_disconnected():
                    break
                await asyncio.sleep(15.0)
                yield ": ping\n\n"
            return

        # Branch B: Redis is available
        # Step 1: Replay from Redis event buffer
        try:
            replay_key = f"{EVENT_LOG_PREFIX}{agent_id}"
            raw_events = await redis.lrange(replay_key, 0, -1)
            replaying = header_last_id is None
            for raw in raw_events:
                try:
                    text = raw.decode("utf-8") if isinstance(raw, bytes) else str(raw)
                    data = json.loads(text)
                    evt_id = str(data.get("id"))
                    if not replaying:
                        if evt_id == header_last_id:
                            replaying = True
                        continue
                    seen_ids.add(evt_id)
                    safe_data = redact_secrets(text)
                    evt_type = data.get("event_type")
                    yield f"id: {evt_id}\nevent: {evt_type}\ndata: {safe_data}\n\n"
                except Exception:
                    continue
        except Exception as exc:
            logger.warning("Failed to replay agent events from Redis: %s", exc)

        # If the session has already reached terminal status, replay is the full history
        if is_terminal_agent_status(session.status):
            return

        # Step 2: Live Pub/Sub subscription
        channel = f"{EVENT_CHANNEL_PREFIX}{agent_id}"
        pubsub = redis.pubsub()
        await pubsub.subscribe(channel)
        try:
            while True:
                if await request.is_disconnected():
                    break
                try:
                    message = await asyncio.wait_for(
                        pubsub.get_message(ignore_subscribe_messages=True),
                        timeout=15.0,
                    )
                except TimeoutError:
                    # Periodic keepalive ping
                    yield ": ping\n\n"
                    continue

                if message and message.get("type") == "message":
                    raw_data = message.get("data")
                    text = (
                        raw_data.decode("utf-8") if isinstance(raw_data, bytes) else str(raw_data)
                    )
                    try:
                        data = json.loads(text)
                        evt_id = str(data.get("id"))
                        if evt_id in seen_ids:
                            continue
                        seen_ids.add(evt_id)
                        safe_data = redact_secrets(text)
                        evt_type = data.get("event_type")
                        yield f"id: {evt_id}\nevent: {evt_type}\ndata: {safe_data}\n\n"
                        if evt_type in (
                            "agent.completed",
                            "agent.failed",
                            "agent.cancelled",
                            "agent.timed_out",
                            "completed",
                            "failed",
                            "cancelled",
                        ):
                            break
                    except Exception:
                        continue
                elif message is None:
                    # Yield heartbeat comment and pause briefly to avoid hot spin
                    yield ": ping\n\n"
                    await asyncio.sleep(1.0)
        finally:
            try:
                await pubsub.unsubscribe(channel)
                await pubsub.aclose()
            except Exception:
                pass

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
