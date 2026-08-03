from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from forge_api.infrastructure.database.models import AuditEventModel

class AuditLogger:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
    def record(self, event: str, user_id: UUID | None = None) -> None:
        self._session.add(AuditEventModel(event=event, user_id=user_id))
