"""
Albert OS — Event Bus tests
Spek: 41_TESTING_AND_QUALITY_BIBLE.md
"""
import asyncio
import pytest
from core.events import (
    emit, on, off, get_history, clear_listeners,
    MEMORY_UPDATED, USER_REQUEST_RECEIVED, SECURITY_ALERT,
    _build_envelope,
)


# ── Event envelope ────────────────────────────────────────────────────────────
class TestEventEnvelope:
    def test_envelope_fields(self):
        env = _build_envelope("TestEvent", {"x": 1}, source="test", correlation_id="abc")
        assert env["type"] == "TestEvent"
        assert env["payload"] == {"x": 1}
        assert env["source"] == "test"
        assert env["correlationId"] == "abc"
        assert "eventId" in env
        assert "timestamp" in env

    def test_envelope_unique_ids(self):
        a = _build_envelope("E", {})
        b = _build_envelope("E", {})
        assert a["eventId"] != b["eventId"]


# ── Async emit ────────────────────────────────────────────────────────────────
class TestAsyncEmit:
    def test_emit_records_history(self):
        before = len(get_history(1000))
        asyncio.run(emit(MEMORY_UPDATED, {"key": "test"}, source="TestSuite"))
        after = len(get_history(1000))
        assert after == before + 1

    def test_history_contains_event(self):
        asyncio.run(emit("TestMarker_XYZ", {"val": 42}, source="TestSuite"))
        history = get_history(100)
        types = [e["type"] for e in history]
        assert "TestMarker_XYZ" in types

    def test_async_handler_called(self):
        received = []

        async def handler(data):
            received.append(data)

        async def run():
            on("AsyncTestEvent", handler)
            await emit("AsyncTestEvent", {"msg": "hello"}, source="test")
            off("AsyncTestEvent", handler)

        asyncio.run(run())
        assert len(received) == 1
        assert received[0]["msg"] == "hello"

    def test_off_removes_handler(self):
        received = []

        async def h(data):
            received.append(data)

        async def run():
            on("OffTestEvent", h)
            off("OffTestEvent", h)
            await emit("OffTestEvent", {}, source="test")

        asyncio.run(run())
        assert len(received) == 0


# ── Constants ─────────────────────────────────────────────────────────────────
class TestConstants:
    def test_constants_are_strings(self):
        assert isinstance(MEMORY_UPDATED, str)
        assert isinstance(USER_REQUEST_RECEIVED, str)
        assert isinstance(SECURITY_ALERT, str)

    def test_constant_values(self):
        assert MEMORY_UPDATED == "MemoryUpdated"
        assert SECURITY_ALERT == "SecurityAlert"
