"""Approval domain model and canonical hashing for the FP8 Agentic Development Engine.

Guarantees cryptographic binding between human approvals and exact tool arguments.
"""
import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from typing import Any
from uuid import UUID


class ApprovalStatus(StrEnum):
    """Lifecycle states for a human approval request."""

    PENDING = "pending"
    GRANTED = "granted"
    DENIED = "denied"
    EXPIRED = "expired"
    CANCELLED = "cancelled"


def compute_arguments_hash(args: Any) -> str:
    """Compute deterministic SHA-256 hash of tool arguments.

    Uses canonical JSON formatting:
    - Sorted keys at all dictionary levels
    - Consistent compact separators (',', ':')
    - UTF-8 encoding preserving unicode characters without escape sequences
    """
    canonical_json = json.dumps(
        args,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )
    return hashlib.sha256(canonical_json.encode("utf-8")).hexdigest()


@dataclass(frozen=True, slots=True)
class AgentApprovalRecord:
    """Durable record of a tool approval request and its decision."""

    id: UUID
    session_id: UUID
    tool_call_id: UUID
    tool_name: str
    arguments_hash: str
    status: ApprovalStatus
    requested_at: datetime
    requested_by: UUID | None = None
    decided_by: UUID | None = None
    reason: str | None = None
    decided_at: datetime | None = None
    expires_at: datetime | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
