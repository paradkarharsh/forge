"""Conversation context store tests.

Uses an in-memory fake Redis to exercise the ``RedisConversationContextStore``
serialization, max-entry capping, TTL, and graceful behavior when Redis is
unavailable (null store fallback).
"""

from datetime import UTC, datetime
from uuid import uuid4

import pytest

from forge_api.domain.memory import ConversationContextEntry
from forge_api.infrastructure.conversation_context import (
    NullConversationContextStore,
    RedisConversationContextStore,
)


class _FakeRedis:
    """Minimal in-memory async Redis for testing the store."""

    def __init__(self) -> None:
        self._data: dict[str, str] = {}
        self._ttls: dict[str, int] = {}

    async def get(self, key):
        return self._data.get(key)

    async def set(self, key, value, ex=None):
        self._data[key] = value
        if ex is not None:
            self._ttls[key] = ex

    async def delete(self, key):
        self._data.pop(key, None)
        self._ttls.pop(key, None)

    async def expire(self, key, ttl):
        if key in self._data:
            self._ttls[key] = ttl
        return key in self._data


def _entry(content: str, role: str = "user") -> ConversationContextEntry:
    return ConversationContextEntry(
        role=role,
        content=content,
        timestamp=datetime.now(UTC),
    )


@pytest.mark.asyncio
async def test_append_and_get_round_trip():
    redis = _FakeRedis()
    store = RedisConversationContextStore(redis)
    session_id, conv_id = uuid4(), uuid4()
    await store.append(session_id, conv_id, _entry("hello"))
    entries = await store.get(session_id, conv_id)
    assert len(entries) == 1
    assert entries[0].content == "hello"
    assert entries[0].role == "user"


@pytest.mark.asyncio
async def test_session_isolation():
    redis = _FakeRedis()
    store = RedisConversationContextStore(redis)
    s1, s2, conv = uuid4(), uuid4(), uuid4()
    await store.append(s1, conv, _entry("session-one"))
    await store.append(s2, conv, _entry("session-two"))
    assert [e.content for e in await store.get(s1, conv)] == ["session-one"]
    assert [e.content for e in await store.get(s2, conv)] == ["session-two"]


@pytest.mark.asyncio
async def test_max_entries_caps_newest():
    redis = _FakeRedis()
    store = RedisConversationContextStore(redis, max_entries=3)
    session_id, conv_id = uuid4(), uuid4()
    for i in range(5):
        await store.append(session_id, conv_id, _entry(f"msg-{i}"))
    entries = await store.get(session_id, conv_id)
    assert [e.content for e in entries] == ["msg-2", "msg-3", "msg-4"]


@pytest.mark.asyncio
async def test_clear_removes_entries():
    redis = _FakeRedis()
    store = RedisConversationContextStore(redis)
    session_id, conv_id = uuid4(), uuid4()
    await store.append(session_id, conv_id, _entry("x"))
    await store.clear(session_id, conv_id)
    assert await store.get(session_id, conv_id) == []


@pytest.mark.asyncio
async def test_set_ttl():
    redis = _FakeRedis()
    store = RedisConversationContextStore(redis)
    session_id, conv_id = uuid4(), uuid4()
    await store.append(session_id, conv_id, _entry("x"))
    await store.set_ttl(session_id, conv_id, 3600)
    assert redis._ttls.get(store._key(session_id, conv_id)) == 3600


@pytest.mark.asyncio
async def test_redis_failure_returns_empty():
    class _Down:
        async def get(self, key):
            raise ConnectionError("down")

        async def set(self, *args, **kwargs):
            raise ConnectionError("down")

        async def delete(self, key):
            raise ConnectionError("down")

        async def expire(self, key, ttl):
            raise ConnectionError("down")

    store = RedisConversationContextStore(_Down())
    session_id, conv_id = uuid4(), uuid4()
    assert await store.get(session_id, conv_id) == []
    # append/clear/set_ttl must not raise
    await store.append(session_id, conv_id, _entry("x"))
    await store.clear(session_id, conv_id)
    await store.set_ttl(session_id, conv_id, 60)


@pytest.mark.asyncio
async def test_null_store_is_noop():
    store = NullConversationContextStore()
    session_id, conv_id = uuid4(), uuid4()
    assert await store.get(session_id, conv_id) == []
    await store.append(session_id, conv_id, _entry("x"))
    await store.clear(session_id, conv_id)
    await store.set_ttl(session_id, conv_id, 60)
    assert await store.get(session_id, conv_id) == []
