"""Conversation domain model.

Persistence-neutral records for durable conversation history.  These
complement (and do NOT replace) the ephemeral Redis-backed conversation
context from FP6.

Redis  → ephemeral, session/current-turn freshness, TTL, max 100 entries.
Postgres → durable conversation history, user-visible history, message
           persistence.
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from typing import Any
from uuid import UUID

# ─── Enums ────────────────────────────────────────────────────────────


class ConversationStatus(StrEnum):
    ACTIVE = "active"
    ARCHIVED = "archived"


class MessageStatus(StrEnum):
    COMPLETE = "complete"
    PARTIAL = "partial"
    CANCELLED = "cancelled"
    ERROR = "error"


# ─── Records ──────────────────────────────────────────────────────────


@dataclass(frozen=True, slots=True)
class ConversationRecord:
    """A single conversation."""

    id: UUID
    workspace_id: UUID
    user_id: UUID
    title: str | None
    repository_id: UUID | None
    status: ConversationStatus
    message_count: int
    created_at: datetime
    updated_at: datetime
    deleted_at: datetime | None


@dataclass(frozen=True, slots=True)
class MessageRecord:
    """A single message within a conversation."""

    id: UUID
    conversation_id: UUID
    role: str  # "user" | "assistant" | "system"
    content: str
    provider: str | None
    model: str | None
    prompt_version: str | None
    input_tokens: int | None
    output_tokens: int | None
    total_tokens: int | None
    duration_ms: float | None
    finish_reason: str | None
    status: MessageStatus
    metadata: dict[str, Any]
    created_at: datetime


@dataclass(frozen=True, slots=True)
class UsageEventRecord:
    """A single LLM usage event for cost tracking."""

    id: UUID
    workspace_id: UUID
    user_id: UUID
    conversation_id: UUID | None
    message_id: UUID | None
    provider: str
    model: str
    input_tokens: int
    output_tokens: int
    total_tokens: int
    duration_ms: float
    estimated_cost: float
    created_at: datetime
    agent_session_id: UUID | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
