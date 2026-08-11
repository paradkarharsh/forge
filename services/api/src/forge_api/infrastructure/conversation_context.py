"""Redis-backed ephemeral conversation context store.

Conversation context is transient turn-by-turn state tied to a session +
conversation pair.  It is never persisted to PostgreSQL and is never
automatically converted into durable memory.  Keys are scoped by
``session_id`` so one session can never read another session's context.
"""
import json
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from redis.asyncio import Redis

from forge_api.domain.memory import ConversationContextEntry

_PREFIX = "forge:ctx"


class RedisConversationContextStore:
    """Concrete Redis implementation of ``ConversationContextStore``."""

    def __init__(
        self,
        cache: Redis,
        *,
        max_entries: int = 100,
        default_ttl_seconds: int = 86_400,
    ) -> None:
        self._cache = cache
        self._max_entries = max_entries
        self._default_ttl_seconds = default_ttl_seconds

    def _key(self, session_id: UUID, conversation_id: UUID) -> str:
        return f"{_PREFIX}:{session_id}:{conversation_id}"

    async def get(
        self, session_id: UUID, conversation_id: UUID,
    ) -> list[ConversationContextEntry]:
        try:
            raw = await self._cache.get(self._key(session_id, conversation_id))
        except Exception:
            return []
        if not raw:
            return []
        try:
            payload = json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            return []
        return [_entry_from_dict(item) for item in payload if isinstance(item, dict)]

    async def append(
        self,
        session_id: UUID,
        conversation_id: UUID,
        entry: ConversationContextEntry,
    ) -> None:
        key = self._key(session_id, conversation_id)
        try:
            raw = await self._cache.get(key)
        except Exception:
            return
        payload = []
        if raw:
            try:
                payload = json.loads(raw)
            except (json.JSONDecodeError, TypeError):
                payload = []
        payload.append(_entry_to_dict(entry))
        # Cap the list length (oldest evicted first).
        if len(payload) > self._max_entries:
            payload = payload[-self._max_entries :]
        try:
            await self._cache.set(
                key, json.dumps(payload), ex=self._default_ttl_seconds
            )
        except Exception:
            return

    async def clear(
        self, session_id: UUID, conversation_id: UUID,
    ) -> None:
        try:
            await self._cache.delete(self._key(session_id, conversation_id))
        except Exception:
            return

    async def set_ttl(
        self, session_id: UUID, conversation_id: UUID, ttl_seconds: int,
    ) -> None:
        try:
            await self._cache.expire(
                self._key(session_id, conversation_id), ttl_seconds
            )
        except Exception:
            return


# ─── Serialization helpers ───────────────────────────────────────────


def _entry_to_dict(entry: ConversationContextEntry) -> dict[str, Any]:
    return {
        "role": entry.role,
        "content": entry.content,
        "timestamp": entry.timestamp.isoformat(),
        "source_ids": list(entry.source_ids),
    }


def _entry_from_dict(item: dict[str, Any]) -> ConversationContextEntry:
    timestamp = None
    raw_ts = item.get("timestamp")
    if raw_ts:
        try:
            timestamp = datetime.fromisoformat(raw_ts)
        except ValueError:
            timestamp = None
    if timestamp is None:
        timestamp = datetime.now(UTC)
    return ConversationContextEntry(
        role=str(item.get("role", "context")),
        content=str(item.get("content", "")),
        timestamp=timestamp,
        source_ids=[str(s) for s in item.get("source_ids", [])],
    )


class NullConversationContextStore:
    """No-op conversation context store.

    Used when Redis is unavailable so context assembly can gracefully omit
    conversation context instead of failing the entire request.
    """

    async def get(
        self, session_id: UUID, conversation_id: UUID,
    ) -> list[ConversationContextEntry]:
        return []

    async def append(
        self,
        session_id: UUID,
        conversation_id: UUID,
        entry: ConversationContextEntry,
    ) -> None:
        return

    async def clear(
        self, session_id: UUID, conversation_id: UUID,
    ) -> None:
        return

    async def set_ttl(
        self, session_id: UUID, conversation_id: UUID, ttl_seconds: int,
    ) -> None:
        return
