"""
Albert OS — Plugin SDK
Spek: 10_PLUGIN_SDK.md

Lifecycle: install → validate → register → initialize → ready → suspend → update → remove
Events: onStartup, onShutdown, onVoiceCommand, onImageCaptured, onMemoryUpdated,
        onWorkspaceChanged, onDeviceConnected, onToolInvoked
"""
import asyncio
import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Callable, Any

log = logging.getLogger("plugin_sdk")

# ── Enums ─────────────────────────────────────────────────────────────────────
class PluginState(str, Enum):
    INSTALLED    = "installed"
    VALIDATED    = "validated"
    REGISTERED   = "registered"
    INITIALIZING = "initializing"
    READY        = "ready"
    SUSPENDED    = "suspended"
    ERROR        = "error"
    REMOVED      = "removed"

class Permission(str, Enum):
    CAMERA       = "camera"
    MICROPHONE   = "microphone"
    FILES        = "files"
    CALENDAR     = "calendar"
    EMAIL        = "email"
    INTERNET     = "internet"
    NOTIFICATIONS= "notifications"
    MEMORY       = "memory"
    VEHICLE_DATA = "vehicle_data"

SENSITIVE_PERMISSIONS = {Permission.CAMERA, Permission.MICROPHONE, Permission.EMAIL,
                         Permission.VEHICLE_DATA, Permission.MEMORY}

# ── Plugin base class ─────────────────────────────────────────────────────────
class AlbertPlugin:
    plugin_id:   str = "unnamed"
    name:        str = "Unnamed Plugin"
    version:     str = "1.0.0"
    author:      str = "Unknown"
    description: str = ""
    permissions: list[Permission] = []
    commands:    list[str]        = []

    def __init__(self):
        self.state = PluginState.INSTALLED
        self._registry: "PluginRegistry | None" = None

    # ── Lifecycle hooks (override in subclass) ────────────────────────────────
    async def on_startup(self):              pass
    async def on_shutdown(self):            pass
    async def on_voice_command(self, text: str, lang: str) -> str | None: return None
    async def on_image_captured(self, image_b64: str, prompt: str) -> str | None: return None
    async def on_memory_updated(self, key: str, value: Any): pass
    async def on_workspace_changed(self, workspace_id: str): pass
    async def on_device_connected(self, device_id: str): pass
    async def on_tool_invoked(self, tool_name: str, args: dict) -> Any: return None

    # ── Helper: send notification ─────────────────────────────────────────────
    def notify(self, msg: str, level: str = "info"):
        if self._registry:
            self._registry.broadcast_event("notification", {"plugin": self.plugin_id, "msg": msg, "level": level})

    # ── Helper: run command ───────────────────────────────────────────────────
    async def run_command(self, cmd: str, args: dict = None) -> str:
        return f"[{self.plugin_id}] Command '{cmd}' not implemented"


# ── Plugin Registry ───────────────────────────────────────────────────────────
class PluginRegistry:
    def __init__(self):
        self._plugins: dict[str, AlbertPlugin] = {}
        self._approved_permissions: dict[str, set[Permission]] = {}  # plugin_id → approved
        self._event_listeners: dict[str, list[Callable]] = {}

    # ── Register ──────────────────────────────────────────────────────────────
    def register(self, plugin: AlbertPlugin) -> dict:
        pid = plugin.plugin_id
        if not pid or pid == "unnamed":
            raise ValueError("plugin_id on kohustuslik")
        if pid in self._plugins and self._plugins[pid].state == PluginState.READY:
            raise ValueError(f"Plugin '{pid}' on juba registreeritud")

        # Validate
        if not self._validate(plugin):
            plugin.state = PluginState.ERROR
            return {"ok": False, "error": "Valideerimine ebaõnnestus"}

        plugin.state = PluginState.VALIDATED
        plugin._registry = self

        # Sensitive permissions — märgi auto-approvituks mitte-tundlikud
        approved = set()
        for perm in plugin.permissions:
            if perm not in SENSITIVE_PERMISSIONS:
                approved.add(perm)
        self._approved_permissions[pid] = approved

        self._plugins[pid] = plugin
        plugin.state = PluginState.REGISTERED
        log.info(f"Plugin registreeritud: {pid} v{plugin.version}")
        return {"ok": True, "plugin_id": pid,
                "needs_approval": [p.value for p in plugin.permissions if p in SENSITIVE_PERMISSIONS]}

    def _validate(self, plugin: AlbertPlugin) -> bool:
        if not plugin.plugin_id or not plugin.name or not plugin.version:
            return False
        if not isinstance(plugin.permissions, list):
            return False
        return True

    # ── Approve permissions ───────────────────────────────────────────────────
    def approve_permissions(self, plugin_id: str, permissions: list[str]) -> dict:
        if plugin_id not in self._plugins:
            return {"ok": False, "error": "Plugin ei leitud"}
        approved = self._approved_permissions.setdefault(plugin_id, set())
        for p in permissions:
            try: approved.add(Permission(p))
            except ValueError: pass
        return {"ok": True, "approved": [p.value for p in approved]}

    def has_permission(self, plugin_id: str, perm: Permission) -> bool:
        return perm in self._approved_permissions.get(plugin_id, set())

    # ── Initialize & Start ────────────────────────────────────────────────────
    async def initialize(self, plugin_id: str) -> dict:
        plugin = self._plugins.get(plugin_id)
        if not plugin:
            return {"ok": False, "error": "Plugin ei leitud"}
        plugin.state = PluginState.INITIALIZING
        try:
            await plugin.on_startup()
            plugin.state = PluginState.READY
            log.info(f"Plugin ready: {plugin_id}")
            return {"ok": True, "state": plugin.state}
        except Exception as e:
            plugin.state = PluginState.ERROR
            log.error(f"Plugin init viga {plugin_id}: {e}")
            return {"ok": False, "error": str(e)}

    async def initialize_all(self):
        for pid in list(self._plugins):
            if self._plugins[pid].state == PluginState.REGISTERED:
                await self.initialize(pid)

    # ── Suspend / Remove ──────────────────────────────────────────────────────
    async def suspend(self, plugin_id: str):
        p = self._plugins.get(plugin_id)
        if p and p.state == PluginState.READY:
            await p.on_shutdown()
            p.state = PluginState.SUSPENDED

    async def remove(self, plugin_id: str):
        await self.suspend(plugin_id)
        self._plugins.pop(plugin_id, None)
        self._approved_permissions.pop(plugin_id, None)

    # ── Event dispatch ────────────────────────────────────────────────────────
    async def dispatch(self, event: str, **kwargs) -> list[Any]:
        results = []
        for plugin in self._plugins.values():
            if plugin.state != PluginState.READY:
                continue
            try:
                handler = getattr(plugin, f"on_{event}", None)
                if handler:
                    result = await handler(**kwargs)
                    if result is not None:
                        results.append({"plugin": plugin.plugin_id, "result": result})
            except Exception as e:
                log.warning(f"Plugin {plugin.plugin_id} event {event} viga: {e}")
        return results

    def broadcast_event(self, event: str, data: dict):
        for cb in self._event_listeners.get(event, []):
            try: cb(data)
            except Exception: pass

    def on_event(self, event: str, cb: Callable):
        self._event_listeners.setdefault(event, []).append(cb)

    # ── Info ──────────────────────────────────────────────────────────────────
    def list_plugins(self) -> list[dict]:
        return [{
            "plugin_id":   p.plugin_id,
            "name":        p.name,
            "version":     p.version,
            "author":      p.author,
            "description": p.description,
            "state":       p.state.value,
            "permissions": [x.value for x in p.permissions],
            "commands":    p.commands,
        } for p in self._plugins.values()]

    def get_plugin(self, plugin_id: str) -> AlbertPlugin | None:
        return self._plugins.get(plugin_id)


# ── Global registry (singleton) ───────────────────────────────────────────────
registry = PluginRegistry()


def get_registry() -> PluginRegistry:
    return registry
