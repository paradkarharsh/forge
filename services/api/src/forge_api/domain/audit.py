"""Audit event domain model.

Audit events carry the full context needed for a security forensics trail:
who, through which session, from where, with which user agent, why, and an
arbitrary structured payload.
"""
from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum
from typing import Any
from uuid import UUID


class AuditEventType(StrEnum):
    LOGIN = "auth.login"
    REGISTER = "auth.register"
    LOGOUT = "auth.logout"
    LOGOUT_ALL = "auth.logout_all"
    REFRESH_ROTATED = "auth.refresh_rotated"
    REFRESH_REUSE_DETECTED = "auth.refresh_reuse_detected"
    SESSION_REVOKED = "auth.session_revoked"
    SESSION_EXPIRED = "auth.session_expired"
    SESSION_CLEANED = "auth.session_cleaned"
    OAUTH_AUTHORIZE = "oauth.authorize"
    OAUTH_CALLBACK = "oauth.callback"
    OAUTH_STATE_MISMATCH = "oauth.state_mismatch"
    OAUTH_NONCE_MISMATCH = "oauth.nonce_mismatch"
    OAUTH_PROFILE_INVALID = "oauth.profile_invalid"
    WORKSPACE_CREATED = "workspace.created"
    WORKSPACE_RENAMED = "workspace.renamed"
    WORKSPACE_DELETED = "workspace.deleted"
    WORKSPACE_UPDATED = "workspace.updated"
    WORKSPACE_MEMBER_ADDED = "workspace.member_added"
    WORKSPACE_MEMBER_REMOVED = "workspace.member_removed"
    WORKSPACE_MEMBER_ROLE_CHANGED = "workspace.member_role_changed"
    REPOSITORY_CREATED = "repository.created"
    REPOSITORY_IMPORTED = "repository.imported"
    REPOSITORY_CLONED = "repository.cloned"
    REPOSITORY_UPDATED = "repository.updated"
    REPOSITORY_ARCHIVED = "repository.archived"
    REPOSITORY_RESTORED = "repository.restored"
    REPOSITORY_DELETED = "repository.deleted"
    REPOSITORY_INDEXED = "repository.indexed"
    REPOSITORY_REINDEXED = "repository.reindexed"
    MEMORY_CREATED = "memory.created"
    MEMORY_UPDATED = "memory.updated"
    MEMORY_DELETED = "memory.deleted"
    MEMORY_ARCHIVED = "memory.archived"
    MEMORY_STALE_MARKED = "memory.stale_marked"
    MEMORY_SEARCHED = "memory.searched"
    CONTEXT_ASSEMBLED = "context.assembled"
    CONVERSATION_CREATED = "conversation.created"
    CONVERSATION_DELETED = "conversation.deleted"
    LLM_COMPLETION = "llm.completion"
    LLM_STREAM_START = "llm.stream_start"
    LLM_STREAM_COMPLETE = "llm.stream_complete"
    LLM_STREAM_ERROR = "llm.stream_error"
    LLM_ERROR = "llm.error"
    LLM_CANCELLED = "llm.cancelled"


@dataclass(frozen=True, slots=True)
class AuditEvent:
    """A single audit record before persistence."""

    event: AuditEventType
    user_id: UUID | None = None
    session_id: UUID | None = None
    ip_address: str | None = None
    user_agent: str | None = None
    reason: str | None = None
    payload: Mapping[str, Any] | None = None
