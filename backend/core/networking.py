"""
Albert OS — Networking Layer
Spek: 39_NETWORKING_AND_CLOUD_BIBLE.md

Offline-first: kõik päringud lähevad läbi selle kihi.
UI ei kutsu kunagi cloud API-t otse.

Kohustuslikud reeglid:
  - Lokaalne DB on alati UI allikas
  - Cloud sync toimub asünkroonselt
  - Töö jätkub võrguühenduseta
  - Sync jätkub automaatselt taasühendamisel
"""
import asyncio
import logging
import time
from collections import deque
from dataclasses import dataclass, field
from enum import Enum
from typing import Awaitable, Callable

import httpx

from core.events import emit_sync, MEMORY_UPDATED, WORKSPACE_CHANGED

log = logging.getLogger("albert.networking")

# ── Ühenduse olek ─────────────────────────────────────────────────────────────
class NetworkState(str, Enum):
    ONLINE   = "online"
    OFFLINE  = "offline"
    DEGRADED = "degraded"   # aeglane / ebastabiilne


# ── Järjekorras ootav päring ───────────────────────────────────────────────────
@dataclass
class QueuedRequest:
    method:   str
    url:      str
    payload:  dict = field(default_factory=dict)
    headers:  dict = field(default_factory=dict)
    retries:  int  = 0
    queued_at: float = field(default_factory=time.time)
    max_retries: int = 3

    def expired(self) -> bool:
        return self.retries >= self.max_retries


# ── Networking Layer ──────────────────────────────────────────────────────────
class NetworkingLayer:
    """
    Kõik välimised HTTP päringud lähevad läbi selle kihi.
    Offline-first: päringud järjekorda kui võrk puudub.
    """

    def __init__(self):
        self.state          = NetworkState.ONLINE
        self._queue: deque[QueuedRequest] = deque(maxlen=200)
        self._retry_task: asyncio.Task | None = None
        self._check_url     = "https://api.anthropic.com"   # lightweight connectivity probe
        self._last_check    = 0.0
        self._check_interval = 30   # sekundit

    # ── Connectivity check ────────────────────────────────────────────────────
    async def check_connectivity(self) -> NetworkState:
        now = time.monotonic()
        if now - self._last_check < self._check_interval:
            return self.state
        self._last_check = now
        try:
            async with httpx.AsyncClient(timeout=5) as c:
                r = await c.head(self._check_url)
                if r.status_code < 500:
                    prev = self.state
                    self.state = NetworkState.ONLINE
                    if prev == NetworkState.OFFLINE:
                        log.info("Network reconnected — flushing queue (%d items)", len(self._queue))
                        asyncio.create_task(self._flush_queue())
                    return NetworkState.ONLINE
        except Exception:
            pass
        self.state = NetworkState.OFFLINE
        return NetworkState.OFFLINE

    # ── Main request method ───────────────────────────────────────────────────
    async def request(self, method: str, url: str, payload: dict = None,
                      headers: dict = None, timeout: float = 30) -> dict | None:
        """
        Saada HTTP päring.
        Offline: lisa järjekorda ja tagasta None.
        Error: logi, ära plahvata.
        """
        if self.state == NetworkState.OFFLINE:
            self._enqueue(method, url, payload or {}, headers or {})
            return None

        try:
            async with httpx.AsyncClient(timeout=timeout) as c:
                resp = await c.request(
                    method, url,
                    json=payload,
                    headers={"Content-Type": "application/json", **(headers or {})},
                )
                if resp.status_code == 200:
                    return resp.json() if resp.content else {}
                log.warning("HTTP %s %s → %d", method, url, resp.status_code)
                return None
        except httpx.TimeoutException:
            log.warning("Timeout: %s %s", method, url)
            self._enqueue(method, url, payload or {}, headers or {})
            return None
        except httpx.NetworkError:
            log.warning("Network error: %s %s — queuing", method, url)
            self.state = NetworkState.OFFLINE
            self._enqueue(method, url, payload or {}, headers or {})
            return None
        except Exception as e:
            log.error("Request error %s %s: %s", method, url, e)
            return None

    # ── Queue management ──────────────────────────────────────────────────────
    def _enqueue(self, method: str, url: str, payload: dict, headers: dict) -> None:
        req = QueuedRequest(method=method, url=url, payload=payload, headers=headers)
        self._queue.append(req)
        log.debug("Queued request: %s %s (queue size: %d)", method, url, len(self._queue))

    async def _flush_queue(self) -> int:
        """Proovi järjekorras olevad päringud uuesti saata."""
        sent = 0
        failed = deque()
        while self._queue:
            req = self._queue.popleft()
            if req.expired():
                log.warning("Dropping expired request: %s %s", req.method, req.url)
                continue
            result = await self.request(req.method, req.url, req.payload, req.headers)
            if result is not None:
                sent += 1
            else:
                req.retries += 1
                if not req.expired():
                    failed.append(req)
        self._queue.extend(failed)
        log.info("Queue flush: sent=%d, remaining=%d", sent, len(self._queue))
        return sent

    def queue_size(self) -> int:
        return len(self._queue)

    def status(self) -> dict:
        return {
            "state":      self.state,
            "queue_size": len(self._queue),
        }

    # ── Background retry loop ─────────────────────────────────────────────────
    async def start_retry_loop(self, interval_s: float = 60) -> None:
        async def _loop():
            while True:
                await asyncio.sleep(interval_s)
                if self._queue:
                    await self.check_connectivity()
                    if self.state == NetworkState.ONLINE:
                        await self._flush_queue()
        self._retry_task = asyncio.create_task(_loop())
        log.info("Networking retry loop started (interval=%ss)", interval_s)


# ── Conflict Resolution (spec 39) ─────────────────────────────────────────────
class ConflictResolution:
    """
    Konfliktide lahendamine prioriteedi järgi:
      1. Kasutaja selged muudatused
      2. Viimane kinnitatud versioon
      3. Ühendamine kui võimalik
      4. Küsi kasutajalt kui konflikt jääb
    """

    @staticmethod
    def resolve(local: dict, remote: dict, user_edit: bool = False) -> tuple[dict, str]:
        """
        Tagastab (lahendus, strateegia).
        strateegia: 'user_wins' | 'remote_wins' | 'merged' | 'conflict'
        """
        if user_edit:
            return local, "user_wins"

        local_ts  = local.get("updated_at",  "")
        remote_ts = remote.get("updated_at", "")

        if local_ts > remote_ts:
            return local, "local_wins"
        if remote_ts > local_ts:
            return remote, "remote_wins"

        # Samaaegne muutus — proovi ühendada (lisavad väljad, ei kirjuta üle)
        merged = {**remote, **{k: v for k, v in local.items() if k not in remote}}
        if merged != local and merged != remote:
            return merged, "merged"

        return remote, "conflict"   # kasutaja otsus nõutav


# ── Global singleton ──────────────────────────────────────────────────────────
networking = NetworkingLayer()
conflict   = ConflictResolution()
