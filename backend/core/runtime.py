"""
Albert OS — Runtime Kernel
Spek: 36_RUNTIME_AND_EVENT_SYSTEM_BIBLE.md

Koordineerib moodulite käivitust, seisundit ja taustatöötajaid.
Sisaldab äriloogikat MITTE — ainult infrastruktuuri.

Olekumasin:
  Stopped → Initializing → Running → Paused → Recovering → Stopping → Stopped

Startup sequence:
  Config → DB → Plugins → Providers → JarvisDirector → Ready
"""
import asyncio
import logging
import time
from enum import Enum
from typing import Callable, Awaitable

from core.events import (
    emit, emit_sync,
    APP_STARTED, APP_STOPPING,
    MODULE_FAILED, MODULE_RECOVERED,
    WORKER_STARTED, WORKER_STOPPED,
    PROVIDER_FAILED,
)

log = logging.getLogger("albert.runtime")


# ── Olekumasin ────────────────────────────────────────────────────────────────
class RuntimeState(str, Enum):
    STOPPED      = "stopped"
    INITIALIZING = "initializing"
    RUNNING      = "running"
    PAUSED       = "paused"
    RECOVERING   = "recovering"
    STOPPING     = "stopping"


# ── Service Registry (DI container) ──────────────────────────────────────────
class ServiceRegistry:
    """Lihtne sünkroonne DI register — teenused registreeritakse ainult korra."""
    _services: dict = {}

    def register(self, name: str, instance) -> None:
        if name in self._services:
            log.warning("Service '%s' already registered — skipping duplicate", name)
            return
        self._services[name] = instance
        log.debug("Service registered: %s", name)

    def get(self, name: str):
        svc = self._services.get(name)
        if svc is None:
            raise KeyError(f"Service '{name}' not registered. Available: {list(self._services)}")
        return svc

    def list(self) -> list[str]:
        return list(self._services)

    def has(self, name: str) -> bool:
        return name in self._services


_registry = ServiceRegistry()


def register_service(name: str, instance) -> None:
    _registry.register(name, instance)

def get_service(name: str):
    return _registry.get(name)

def service_registry() -> ServiceRegistry:
    return _registry


# ── Background Workers ────────────────────────────────────────────────────────
class Worker:
    """Taustatöötaja — käivitab korduva async ülesande intervalliga."""
    def __init__(self, name: str, coro_fn: Callable[[], Awaitable[None]], interval_s: float):
        self.name       = name
        self.coro_fn    = coro_fn
        self.interval_s = interval_s
        self._task: asyncio.Task | None = None
        self._running = False

    async def _loop(self):
        emit_sync(WORKER_STARTED, {"worker": self.name}, source="Runtime")
        log.info("Worker started: %s (interval=%ss)", self.name, self.interval_s)
        while self._running:
            try:
                await self.coro_fn()
            except Exception as e:
                log.warning("Worker '%s' error: %s", self.name, e)
                emit_sync(MODULE_FAILED, {"module": self.name, "error": str(e)}, source="Runtime")
            await asyncio.sleep(self.interval_s)
        emit_sync(WORKER_STOPPED, {"worker": self.name}, source="Runtime")

    def start(self):
        self._running = True
        self._task = asyncio.create_task(self._loop())

    async def stop(self):
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass


# ── Sisseehitatud taustatöötajad ──────────────────────────────────────────────
async def _cache_cleanup_worker():
    """Puhastab response_composer vahemälu aegunud kirjetest."""
    from core.response_composer import cache_clear
    cache_clear()
    log.debug("Cache cleanup done")


async def _memory_index_worker():
    """Indekseerib kõrge tähtsusega mälestused perioodiliselt."""
    try:
        from memory.memory import search_memory_index
        entries = search_memory_index("", min_importance=0.8)
        log.debug("Memory index worker: %d high-importance entries", len(entries))
    except Exception as e:
        log.debug("Memory index worker skipped: %s", e)


async def _provider_health_worker():
    """Kontrollib providerite tervist ja laseb ProviderFailed sündmuse."""
    from core.monitor import get_provider_health
    health = get_provider_health()
    for provider, data in health.items():
        if isinstance(data, dict) and data.get("errors", 0) > 5:
            emit_sync(PROVIDER_FAILED, {"provider": provider, "errors": data["errors"]},
                      source="Runtime")


# ── Runtime Kernel ────────────────────────────────────────────────────────────
class RuntimeKernel:
    """
    Koordineerib Albert OS käivitust, olekut ja taustatöid.
    Äriloogikat EI sisalda — ainult infrastruktuuri.
    """

    def __init__(self):
        self.state   = RuntimeState.STOPPED
        self._workers: list[Worker] = []
        self._started_at: float = 0.0

    # ── Startup sequence (spec 36_RUNTIME_AND_EVENT_SYSTEM_BIBLE.md) ─────────
    async def start(self) -> None:
        if self.state != RuntimeState.STOPPED:
            log.warning("Runtime already in state %s — skipping start", self.state)
            return

        self.state = RuntimeState.INITIALIZING
        t0 = time.monotonic()
        log.info("Albert OS Runtime starting...")

        try:
            await self._step("Config", self._load_config)
            await self._step("Database", self._init_db)
            await self._step("Plugins", self._load_plugins)
            await self._step("Providers", self._register_providers)
            await self._step("JarvisDirector", self._init_director)
            self._start_workers()

            self.state = RuntimeState.RUNNING
            self._started_at = time.monotonic()
            ms = int((time.monotonic() - t0) * 1000)
            log.info("Albert OS Runtime READY in %dms", ms)
            await emit(APP_STARTED, {"startup_ms": ms, "state": self.state}, source="Runtime")

        except Exception as e:
            log.exception("Runtime startup failed: %s", e)
            self.state = RuntimeState.STOPPED
            raise

    async def stop(self) -> None:
        if self.state == RuntimeState.STOPPED:
            return
        self.state = RuntimeState.STOPPING
        await emit(APP_STOPPING, {}, source="Runtime")
        for w in self._workers:
            await w.stop()
        self._workers.clear()
        self.state = RuntimeState.STOPPED
        log.info("Albert OS Runtime stopped.")

    async def pause(self) -> None:
        if self.state == RuntimeState.RUNNING:
            self.state = RuntimeState.PAUSED
            log.info("Runtime paused.")

    async def resume(self) -> None:
        if self.state == RuntimeState.PAUSED:
            self.state = RuntimeState.RUNNING
            log.info("Runtime resumed.")

    # ── Startup helpers ───────────────────────────────────────────────────────
    async def _step(self, name: str, fn: Callable[[], Awaitable[None]]) -> None:
        log.debug("Runtime step: %s", name)
        try:
            await fn()
        except Exception as e:
            log.warning("Runtime step '%s' failed (non-fatal): %s", name, e)

    async def _load_config(self) -> None:
        from core.tools import get_cfg
        cfg = get_cfg("max_tokens", 300)
        register_service("config", {"max_tokens": cfg})

    async def _init_db(self) -> None:
        from memory.memory import _conn
        with _conn() as c:
            ver = c.execute("SELECT MAX(version) as v FROM schema_version").fetchone()
            v = ver["v"] if ver else 0
        register_service("db", {"schema_version": v})
        log.debug("DB connected, schema v%s", v)

    async def _load_plugins(self) -> None:
        from core.plugin_sdk import get_registry
        reg = get_registry()
        register_service("plugins", reg)
        log.debug("Plugins loaded: %d registered", len(reg.get("plugins", [])))

    async def _register_providers(self) -> None:
        from core.adapters import _register_defaults, _adapters
        if not _adapters:
            _register_defaults()
        register_service("providers", list(_adapters.keys()))
        log.debug("Providers: %s", list(_adapters.keys()))

    async def _init_director(self) -> None:
        from memory.memory import init_project_brain
        init_project_brain()
        register_service("director", True)

    def _start_workers(self) -> None:
        workers_cfg = [
            ("cache_cleanup",    _cache_cleanup_worker,    120),   # 2 min
            ("memory_index",     _memory_index_worker,     300),   # 5 min
            ("provider_health",  _provider_health_worker,  180),   # 3 min
        ]
        for name, fn, interval in workers_cfg:
            w = Worker(name, fn, interval)
            w.start()
            self._workers.append(w)
        log.debug("Started %d background workers", len(self._workers))

    # ── Module failure recovery (spec 36_RUNTIME_AND_EVENT_SYSTEM_BIBLE.md) ──
    async def recover_module(self, module_name: str, restart_fn: Callable) -> bool:
        """
        Mooduli taastumine:
        1. Tuvasta viga
        2. Isoleeri moodul
        3. Taaskäivita
        4. Taasta olek
        5. Teavita director'it
        """
        log.warning("Recovering module: %s", module_name)
        prev_state = self.state
        self.state = RuntimeState.RECOVERING
        try:
            await restart_fn()
            self.state = RuntimeState.RUNNING
            emit_sync(MODULE_RECOVERED, {"module": module_name}, source="Runtime")
            log.info("Module '%s' recovered successfully", module_name)
            return True
        except Exception as e:
            self.state = prev_state
            emit_sync(MODULE_FAILED, {"module": module_name, "error": str(e)}, source="Runtime")
            log.error("Module '%s' recovery failed: %s", module_name, e)
            return False

    # ── Diagnostics ───────────────────────────────────────────────────────────
    def status(self) -> dict:
        uptime = int(time.monotonic() - self._started_at) if self._started_at else 0
        return {
            "state":    self.state,
            "uptime_s": uptime,
            "workers":  [w.name for w in self._workers],
            "services": _registry.list(),
        }


# ── Globaalne singleton ───────────────────────────────────────────────────────
kernel = RuntimeKernel()
