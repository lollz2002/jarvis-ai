"""
Albert OS — Sync Engine
Spek: 39_NETWORKING_AND_CLOUD_BIBLE.md

Sync Flow:
  Client → LocalDB (instant) → UI update
  SyncEngine → Cloud upload → ACK → mark synchronized

Conflict resolution: ConflictResolution (networking.py)
Offline: sync jätkub automaatselt taasühendamisel
"""
import asyncio
import logging
import os
import time
from datetime import datetime

from core.networking import networking, NetworkState
from core.events import emit_sync, MEMORY_UPDATED
from core.monitor import audit

log = logging.getLogger("albert.sync")

# Pilve endpoint — Railway base URL (võtab env muutujast)
_CLOUD_BASE = os.getenv("CLOUD_SYNC_URL", "")

# ── Muutused mis ootavad sünkroniseerimist ────────────────────────────────────
_pending: list[dict] = []   # {table, record_id, operation, data, ts}
_MAX_PENDING = 500


def mark_dirty(table: str, record_id: int | str, operation: str = "upsert",
               data: dict = None) -> None:
    """
    Märgi kirje sünkroniseerimiseks ootavaks.
    Kutsutakse iga lokaalsest muutuse järel.
    operation: 'upsert' | 'delete'
    """
    if len(_pending) >= _MAX_PENDING:
        _pending.pop(0)
    _pending.append({
        "table":      table,
        "record_id":  record_id,
        "operation":  operation,
        "data":       data or {},
        "ts":         datetime.utcnow().isoformat(),
        "synced":     False,
    })


def pending_count() -> int:
    return sum(1 for p in _pending if not p["synced"])


# ── Sync Engine ───────────────────────────────────────────────────────────────
class SyncEngine:
    """
    Üleslaadib lokaalsed muudatused pilve asünkroonselt.
    Lokaalne DB on alati UI jaoks allikas — sünkroon toimub taustal.
    """

    def __init__(self):
        self._running    = False
        self._sync_task: asyncio.Task | None = None
        self._last_sync  = 0.0

    async def start(self, interval_s: float = 120) -> None:
        """Käivita taustal sünkroniseerimise tsükkel."""
        self._running = True
        self._sync_task = asyncio.create_task(self._loop(interval_s))
        log.info("SyncEngine started (interval=%ss)", interval_s)

    async def stop(self) -> None:
        self._running = False
        if self._sync_task:
            self._sync_task.cancel()

    async def _loop(self, interval_s: float) -> None:
        while self._running:
            await asyncio.sleep(interval_s)
            await self.sync_now()

    async def sync_now(self) -> dict:
        """Sünkroniseeri kõik ootavad muudatused kohe."""
        if not _CLOUD_BASE:
            return {"skipped": True, "reason": "CLOUD_SYNC_URL not configured"}

        pending = [p for p in _pending if not p["synced"]]
        if not pending:
            return {"synced": 0}

        # Kontrolli ühendust
        state = await networking.check_connectivity()
        if state != NetworkState.ONLINE:
            log.debug("Sync skipped — offline. Pending: %d", len(pending))
            return {"skipped": True, "reason": "offline", "pending": len(pending)}

        t0 = time.monotonic()
        synced = 0
        failed = 0

        for item in pending:
            result = await networking.request(
                "POST",
                f"{_CLOUD_BASE}/api/v1/sync",
                payload=item,
                headers={"X-Albert-Device": os.getenv("DEVICE_ID", "server")},
            )
            if result is not None:
                item["synced"] = True
                synced += 1
            else:
                failed += 1

        ms = int((time.monotonic() - t0) * 1000)
        audit("sync_complete", {"synced": synced, "failed": failed, "ms": ms})
        log.info("Sync: %d synced, %d failed (%dms)", synced, failed, ms)

        if synced:
            emit_sync(MEMORY_UPDATED, {"type": "sync", "count": synced}, source="SyncEngine")

        return {"synced": synced, "failed": failed, "ms": ms}

    def status(self) -> dict:
        return {
            "running":       self._running,
            "pending_count": pending_count(),
            "cloud_url":     _CLOUD_BASE or "(not configured)",
            "last_sync":     self._last_sync,
        }

    # ── Pull: laadi muudatused pilvest ────────────────────────────────────────
    async def pull(self, since_ts: str = "") -> list[dict]:
        """
        Laadi muudatused pilvest alla.
        Tagastab muudatuste nimekirja konflikti lahendamiseks.
        """
        if not _CLOUD_BASE:
            return []
        url = f"{_CLOUD_BASE}/api/v1/sync/pull"
        if since_ts:
            url += f"?since={since_ts}"
        result = await networking.request("GET", url)
        return result.get("changes", []) if result else []

    # ── WebSocket sündmuste saatmine (spec 39) ────────────────────────────────
    # Sündmused mis WS kaudu klientidele saadetakse:
    WS_EVENTS = {
        "workspaceUpdated", "memoryUpdated", "taskChanged",
        "providerStatus", "pluginInstalled", "notification",
    }

    @staticmethod
    def is_valid_ws_event(event_type: str) -> bool:
        return event_type in SyncEngine.WS_EVENTS


# ── Global singleton ──────────────────────────────────────────────────────────
sync_engine = SyncEngine()
