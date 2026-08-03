"""Persistence-neutral session record."""
from dataclasses import dataclass
from datetime import datetime
from uuid import UUID


@dataclass(frozen=True, slots=True)
class SessionRecord:
    id: UUID
    user_id: UUID
    family_id: UUID
    refresh_hash: str
    created_at: datetime
    expires_at: datetime
    revoked_at: datetime | None
    replaced_at: datetime | None
    last_active_at: datetime
    device_name: str | None
    ip_address: str | None
    user_agent: str | None
