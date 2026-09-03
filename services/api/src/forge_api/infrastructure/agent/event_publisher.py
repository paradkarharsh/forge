import json
import logging
from typing import Any

from forge_api.domain.agent import AgentEvent
from forge_api.domain.tool import redact_secrets

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


EVENT_LOG_PREFIX = "forge:agent:event_log:"
EVENT_CHANNEL_PREFIX = "forge:agent:events:"
MAX_REPLAY_EVENTS = 500
REPLAY_TTL_SECONDS = 3600


def _redact_value(val: Any) -> Any:
    if isinstance(val, str):
        return redact_secrets(val)
    if isinstance(val, dict):
        return {k: _redact_value(v) for k, v in val.items()}
    if isinstance(val, list):
        return [_redact_value(v) for v in val]
    return val


class RedisAgentEventPublisher:
    """Redis-backed publisher pushing to a 1-hour bounded replay list and live Pub/Sub channel."""

    def __init__(
        self,
        redis: Any,
        *,
        max_replay_events: int = MAX_REPLAY_EVENTS,
        replay_ttl_seconds: int = REPLAY_TTL_SECONDS,
    ) -> None:
        self._redis = redis
        self._max_replay_events = max_replay_events
        self._replay_ttl_seconds = replay_ttl_seconds

    async def publish(self, event: AgentEvent) -> None:
        try:
            safe_payload = _redact_value(event.payload)
            data = {
                "id": str(event.id),
                "session_id": str(event.session_id),
                "event_type": event.event_type.value,
                "timestamp": event.timestamp.isoformat(),
                "payload": safe_payload,
            }
            serialized = json.dumps(data)

            replay_key = f"{EVENT_LOG_PREFIX}{event.session_id}"
            await self._redis.rpush(replay_key, serialized)
            await self._redis.ltrim(replay_key, -self._max_replay_events, -1)
            await self._redis.expire(replay_key, self._replay_ttl_seconds)

            channel = f"{EVENT_CHANNEL_PREFIX}{event.session_id}"
            await self._redis.publish(channel, serialized)
        except Exception as exc:
            logger.warning("Failed to publish agent event to Redis: %s", exc)

