"""In-memory and null event publishers for agent lifecycle domain events."""
import logging

from forge_api.domain.agent import AgentEvent

logger = logging.getLogger(__name__)


class NullAgentEventPublisher:
    """No-op event publisher discarding events (e.g. for testing or fallback)."""

    async def publish(self, event: AgentEvent) -> None:
        logger.debug("NullAgentEventPublisher discarding event: %s", event.event_type)


class InMemoryAgentEventPublisher:
    """In-memory collector of agent lifecycle events for verification and tests."""

    def __init__(self) -> None:
        self._events: list[AgentEvent] = []

    @property
    def events(self) -> list[AgentEvent]:
        return list(self._events)

    async def publish(self, event: AgentEvent) -> None:
        self._events.append(event)
        logger.debug(
            "InMemoryAgentEventPublisher received: %s (session %s)",
            event.event_type,
            event.session_id,
        )

    def clear(self) -> None:
        self._events.clear()
