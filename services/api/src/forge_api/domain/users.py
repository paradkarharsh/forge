"""Persistence-neutral user and OAuth identity records."""
from dataclasses import dataclass
from datetime import datetime
from uuid import UUID


@dataclass(frozen=True, slots=True)
class UserRecord:
    id: UUID
    email: str
    password_hash: str | None
    created_at: datetime


@dataclass(frozen=True, slots=True)
class OAuthIdentityRecord:
    id: UUID
    user_id: UUID
    provider: str
    subject: str
    created_at: datetime
