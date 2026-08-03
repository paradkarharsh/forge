from dataclasses import dataclass
from datetime import datetime
from uuid import UUID


@dataclass(frozen=True, slots=True)
class SessionView:
    id: UUID
    device_name: str | None
    ip_address: str | None
    user_agent: str | None
    last_active_at: datetime
    expires_at: datetime
