"""
Albert OS — Event Bus v2
Spek: 32_CODE_ARCHITECTURE_BIBLE.md, 36_RUNTIME_AND_EVENT_SYSTEM_BIBLE.md

Async sündmuste süsteem struktureeritud Event Contract'iga:
  {eventId, type, timestamp, source, payload, correlationId}

Kasutamine:
  from core.events import emit, on, off

  async def my_handler(data: dict): ...
  on("MemoryUpdated", my_handler)
  await emit("MemoryUpdated", {"key": "foo"}, source="MemoryEngine")
"""
import asyncio
import logging
import uuid
from collections import defaultdict
from datetime import datetime, timezone
from typing import Callable, Awaitable

log = logging.getLogger("albert.events")

# ── Sündmuste nimed ───────────────────────────────────────────────────────────
# Runtime (36_RUNTIME_AND_EVENT_SYSTEM_BIBLE.md)
APP_STARTED               = "AppStarted"
APP_STOPPING              = "AppStopping"
MODULE_FAILED             = "ModuleFailed"
MODULE_RECOVERED          = "ModuleRecovered"
WORKSPACE_LOADED          = "WorkspaceLoaded"
VOICE_RECOGNIZED          = "VoiceRecognized"
PROVIDER_FAILED           = "ProviderFailed"
PLUGIN_INSTALLED          = "PluginInstalled"
WORKER_STARTED            = "WorkerStarted"
WORKER_STOPPED            = "WorkerStopped"
# Core (32_CODE_ARCHITECTURE_BIBLE.md)
USER_REQUEST_RECEIVED     = "UserRequestReceived"
MEMORY_UPDATED            = "MemoryUpdated"
PROVIDER_SELECTED         = "ProviderSelected"
TOOL_EXECUTED             = "ToolExecuted"
VISION_ANALYSIS_COMPLETED = "VisionAnalysisCompleted"
WORKSPACE_CHANGED         = "WorkspaceChanged"
PLUGIN_LOADED             = "PluginLoaded"
SESSION_STARTED           = "SessionStarted"
SESSION_ENDED             = "SessionEnded"
RESPONSE_COMPOSED         = "ResponseComposed"

Handler = Callable[[dict], Awaitable[None]]

_listeners: dict[str, list[Handler]] = defaultdict(list)
_history:   list[dict] = []
_MAX_HISTORY = 500


def _build_envelope(event_type: str, payload: dict,
                    source: str = "", correlation_id: str = "") -> dict:
    """Ehita struktureeritud Event Contract (36_RUNTIME_AND_EVENT_SYSTEM_BIBLE.md)."""
    return {
        "eventId":       str(uuid.uuid4()),
        "type":          event_type,
        "timestamp":     datetime.now(timezone.utc).isoformat(),
        "source":        source or "unknown",
        "payload":       payload,
        "correlationId": correlation_id or "",
    }


def on(event: str, handler: Handler) -> None:
    """Registreeri async kuulaja sündmusele."""
    if handler not in _listeners[event]:
        _listeners[event].append(handler)


def off(event: str, handler: Handler) -> None:
    """Eemalda kuulaja."""
    try:
        _listeners[event].remove(handler)
    except ValueError:
        pass


async def emit(event: str, data: dict | None = None,
               source: str = "", correlation_id: str = "") -> None:
    """Lase sündmus välja struktureeritud Event Contract'iga."""
    envelope = _build_envelope(event, data or {}, source, correlation_id)
    _history.append(envelope)
    if len(_history) > _MAX_HISTORY:
        _history.pop(0)
    handlers = list(_listeners.get(event, []))
    if not handlers:
        return
    results = await asyncio.gather(
        *[h(data or {}) for h in handlers],
        return_exceptions=True,
    )
    for i, r in enumerate(results):
        if isinstance(r, Exception):
            log.warning("Event handler error [%s][%d]: %s", event, i, r)


def emit_sync(event: str, data: dict | None = None,
              source: str = "", correlation_id: str = "") -> None:
    """Mitte-async kontekstist sündmuse saatmine (fire-and-forget)."""
    try:
        loop = asyncio.get_running_loop()
        loop.create_task(emit(event, data, source=source, correlation_id=correlation_id))
    except RuntimeError:
        pass


def get_history(last_n: int = 50) -> list[dict]:
    """Tagastab viimased N sündmust struktureeritud kujul."""
    return _history[-last_n:]


def clear_listeners(event: str | None = None) -> None:
    """Eemalda kõik kuulajad (kasulik testides)."""
    if event:
        _listeners.pop(event, None)
    else:
        _listeners.clear()
