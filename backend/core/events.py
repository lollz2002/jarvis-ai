"""
Albert OS — Event Bus
Spek: 32_CODE_ARCHITECTURE_BIBLE.md

Lihtne async sündmuste süsteem moodulite vaheliseks suhtluseks.
Moodulid ei tohiks sõltuda teineteise implementatsioonist — kasuta sündmusi.

Kasutamine:
  from core.events import emit, on, off

  # Kuulaja registreerimine
  async def my_handler(data: dict):
      print(data)
  on("MemoryUpdated", my_handler)

  # Sündmuse väljalaskmine
  await emit("MemoryUpdated", {"key": "foo", "value": "bar"})
"""
import asyncio
import logging
from collections import defaultdict
from typing import Callable, Awaitable

log = logging.getLogger("albert.events")

# ── Tuntud sündmuste nimed (32_CODE_ARCHITECTURE_BIBLE.md) ───────────────────
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
_history:   list[dict] = []          # viimased 200 sündmust debugimiseks
_MAX_HISTORY = 200


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


async def emit(event: str, data: dict | None = None) -> None:
    """Lase sündmus välja — kutsub kõiki registreeritud kuulajaid."""
    payload = {"event": event, "data": data or {}}
    _history.append(payload)
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


def emit_sync(event: str, data: dict | None = None) -> None:
    """Mitte-async kontekstist sündmuse saatmine (fire-and-forget)."""
    try:
        loop = asyncio.get_running_loop()
        loop.create_task(emit(event, data))
    except RuntimeError:
        # Ei ole running loop — ignoreeri (nt testi kontekstis)
        pass


def get_history(last_n: int = 50) -> list[dict]:
    """Tagastab viimased N sündmust (debug/monitor endpoint)."""
    return _history[-last_n:]


def clear_listeners(event: str | None = None) -> None:
    """Eemalda kõik kuulajad (kasulik testides)."""
    if event:
        _listeners.pop(event, None)
    else:
        _listeners.clear()
