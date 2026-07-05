"""
Albert OS — Sync Engine tests
Spek: 41_TESTING_AND_QUALITY_BIBLE.md, 43_SYNC_ENGINE_BIBLE.md
"""
import pytest
from core.sync import mark_dirty, pending_count, sync_engine, SyncEngine, SyncState


class TestMarkDirty:
    def test_mark_dirty_increases_pending(self):
        before = pending_count()
        mark_dirty("memories", 1, "upsert", {"text": "tere"})
        assert pending_count() == before + 1

    def test_mark_dirty_delete(self):
        before = pending_count()
        mark_dirty("projects", "proj-1", "delete", {})
        assert pending_count() == before + 1


class TestSyncState:
    def test_initial_state_idle(self):
        engine = SyncEngine()
        assert engine.state == SyncState.IDLE

    def test_status_returns_dict(self):
        s = sync_engine.status()
        assert "running" in s
        assert "pending_count" in s
        assert "state" in s

    def test_ws_events_are_set(self):
        assert isinstance(SyncEngine.WS_EVENTS, set)
        assert "memoryUpdated" in SyncEngine.WS_EVENTS

    def test_valid_ws_event(self):
        assert SyncEngine.is_valid_ws_event("memoryUpdated") is True
        assert SyncEngine.is_valid_ws_event("invalidEvent") is False
