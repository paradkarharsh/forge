"""Infrastructure audit logger.

Converts domain ``AuditEvent`` records into persistence models within the
active unit-of-work (SQLAlchemy session). The caller is responsible for
committing the transaction.
"""
from collections.abc import Mapping
from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from forge_api.domain.audit import AuditEvent, AuditEventType
from forge_api.infrastructure.database.models import AuditEventModel


class AuditLogger:
    """Appends audit events to the current database session."""

    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    def record(self, event: AuditEvent) -> None:
        """Add an audit event to the current unit-of-work."""
        self._db.add(
            AuditEventModel(
                event=event.event,
                user_id=event.user_id,
                session_id=event.session_id,
                ip_address=event.ip_address,
                user_agent=event.user_agent,
                reason=event.reason,
                payload=dict(event.payload) if event.payload else None,
            )
        )

    def log(
        self,
        event: AuditEventType,
        *,
        user_id: UUID | None = None,
        session_id: UUID | None = None,
        ip_address: str | None = None,
        user_agent: str | None = None,
        reason: str | None = None,
        payload: Mapping[str, Any] | None = None,
    ) -> None:
        """Convenience shorthand that builds the domain event inline."""
        self.record(
            AuditEvent(
                event=event,
                user_id=user_id,
                session_id=session_id,
                ip_address=ip_address,
                user_agent=user_agent,
                reason=reason,
                payload=payload,
            )
        )
