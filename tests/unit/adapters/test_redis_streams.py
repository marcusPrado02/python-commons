"""Unit tests for the Redis Streams adapter (§56)."""
from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest

from mp_commons.adapters.redis.streams import (
    RedisStreamConsumerGroup,
    RedisStreamEntry,
    RedisStreamOutboxDispatcher,
    RedisStreamProducer,
)


# ---------------------------------------------------------------------------
# RedisStreamEntry
# ---------------------------------------------------------------------------


def test_entry_field_str_decodes_bytes():
    entry = RedisStreamEntry(id="1-0", fields={b"key": b"value"})
    assert entry.field_str("key") == "value"


def test_entry_field_str_default():
    entry = RedisStreamEntry(id="1-0", fields={})
    assert entry.field_str("missing", default="x") == "x"


def test_entry_parsed_at_set():
    entry = RedisStreamEntry(id="1-0", fields={})
    assert isinstance(entry.parsed_at, datetime)


# ---------------------------------------------------------------------------
# RedisStreamProducer
# ---------------------------------------------------------------------------


def test_producer_calls_xadd():
    redis = MagicMock()
    redis.xadd = AsyncMock(return_value=b"1700000000000-0")
    producer = RedisStreamProducer(redis)

    result = asyncio.run(producer.publish("my-stream", {"event": "test"}))
    assert result == "1700000000000-0"
    redis.xadd.assert_called_once_with("my-stream", {"event": "test"})


def test_producer_maxlen_passed_to_xadd():
    redis = MagicMock()
    redis.xadd = AsyncMock(return_value=b"1-0")
    producer = RedisStreamProducer(redis)

    asyncio.run(producer.publish("s", {"k": "v"}, maxlen=1000))
    call_kwargs = redis.xadd.call_args[1]
    assert call_kwargs["maxlen"] == 1000
    assert call_kwargs["approximate"] is True


def test_producer_str_entry_id():
    redis = MagicMock()
    redis.xadd = AsyncMock(return_value="1-0")  # already str
    producer = RedisStreamProducer(redis)

    result = asyncio.run(producer.publish("s", {}))
    assert result == "1-0"


# ---------------------------------------------------------------------------
# RedisStreamConsumerGroup — create_group
# ---------------------------------------------------------------------------


def test_consumer_group_create():
    redis = MagicMock()
    redis.xgroup_create = AsyncMock(return_value="OK")
    cg = RedisStreamConsumerGroup(redis)

    asyncio.run(cg.create_group("stream", "grp", start_id="0"))
    redis.xgroup_create.assert_called_once_with("stream", "grp", id="0", mkstream=True)


def test_consumer_group_create_noop_on_busygroup():
    redis = MagicMock()
    redis.xgroup_create = AsyncMock(side_effect=Exception("BUSYGROUP Consumer Group already exists"))
    cg = RedisStreamConsumerGroup(redis)

    asyncio.run(cg.create_group("s", "g"))  # should not raise


# ---------------------------------------------------------------------------
# RedisStreamConsumerGroup — read
# ---------------------------------------------------------------------------


def test_consumer_group_read_returns_entries():
    redis = MagicMock()
    fake_messages = [
        (b"stream", [(b"1-0", {b"event": b"test", b"data": b"hello"})])
    ]
    redis.xreadgroup = AsyncMock(return_value=fake_messages)
    cg = RedisStreamConsumerGroup(redis)

    entries = asyncio.run(cg.read("stream", "grp", "consumer1", count=5))
    assert len(entries) == 1
    assert entries[0].id == "1-0"
    assert entries[0].field_str("event") == "test"


def test_consumer_group_read_empty():
    redis = MagicMock()
    redis.xreadgroup = AsyncMock(return_value=None)
    cg = RedisStreamConsumerGroup(redis)

    entries = asyncio.run(cg.read("stream", "grp", "c", count=10))
    assert entries == []


# ---------------------------------------------------------------------------
# RedisStreamConsumerGroup — ack
# ---------------------------------------------------------------------------


def test_consumer_group_ack():
    redis = MagicMock()
    redis.xack = AsyncMock(return_value=2)
    cg = RedisStreamConsumerGroup(redis)

    result = asyncio.run(cg.ack("stream", "grp", "1-0", "2-0"))
    assert result == 2
    redis.xack.assert_called_once_with("stream", "grp", "1-0", "2-0")


# ---------------------------------------------------------------------------
# RedisStreamOutboxDispatcher
# ---------------------------------------------------------------------------


def _make_record(record_id: str = "r1", topic: str = "events") -> MagicMock:
    from mp_commons.kernel.messaging.outbox import OutboxRecord, OutboxStatus

    return OutboxRecord(
        id=record_id,
        topic=topic,
        event_type="UserCreated",
        aggregate_id="u1",
        aggregate_type="User",
        payload=b'{"id":"u1"}',
        headers={},
        status=OutboxStatus.PENDING,
    )


def test_dispatcher_publishes_and_marks_dispatched():
    redis = MagicMock()
    redis.xadd = AsyncMock(return_value=b"1-0")
    producer = RedisStreamProducer(redis)

    repo = MagicMock()
    repo.get_pending = AsyncMock(return_value=[_make_record()])
    repo.mark_dispatched = AsyncMock()
    repo.mark_failed = AsyncMock()

    dispatcher = RedisStreamOutboxDispatcher(producer, repo)
    count = asyncio.run(dispatcher.dispatch_pending())

    assert count == 1
    repo.mark_dispatched.assert_called_once_with("r1")
    repo.mark_failed.assert_not_called()


def test_dispatcher_marks_failed_on_error():
    redis = MagicMock()
    redis.xadd = AsyncMock(side_effect=Exception("connection error"))
    producer = RedisStreamProducer(redis)

    repo = MagicMock()
    repo.get_pending = AsyncMock(return_value=[_make_record()])
    repo.mark_dispatched = AsyncMock()
    repo.mark_failed = AsyncMock()

    dispatcher = RedisStreamOutboxDispatcher(producer, repo)
    count = asyncio.run(dispatcher.dispatch_pending())

    assert count == 0
    repo.mark_failed.assert_called_once_with("r1", error="dispatch failed")


def test_dispatcher_returns_count():
    redis = MagicMock()
    redis.xadd = AsyncMock(return_value=b"1-0")
    producer = RedisStreamProducer(redis)

    repo = MagicMock()
    repo.get_pending = AsyncMock(return_value=[_make_record("r1"), _make_record("r2")])
    repo.mark_dispatched = AsyncMock()
    repo.mark_failed = AsyncMock()

    dispatcher = RedisStreamOutboxDispatcher(producer, repo)
    count = asyncio.run(dispatcher.dispatch_pending())
    assert count == 2
