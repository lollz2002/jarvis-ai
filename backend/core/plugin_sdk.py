"""
Albert OS — Plugin SDK v2
Spek: 10_PLUGIN_SDK.md, 38_PLUGIN_SDK_IMPLEMENTATION_BIBLE.md

Lifecycle (38_PLUGIN_SDK_IMPLEMENTATION_BIBLE.md):
  Installed → Loaded → Enabled → Disabled → Enabled → Uninstalled

Interface:
  on_load / on_enable / on_disable / on_unload / on_event

SDK version: 2.0.0 (semantic versioning)
"""
import asyncio
import json
import logging
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Callable, Any

log = logging.getLogger("plugin_sdk")

SDK_VERSION = "2.0.0"

# ── Plugin Lifecycle (spec 38) ────────────────────────────────────────────────
class PluginState(str, Enum):
    INSTALLED   = "installed"
    LOADED      = "loaded"
    ENABLED     = "enabled"
    DISABLED    = "disabled"
    UNINSTALLED = "uninstalled"
    ERROR       = "error"
    # Legacy aliases (backward compat)
    VALIDATED   = "loaded"
    REGISTERED  = "loaded"
    INITIALIZING= "loaded"
    READY       = "enabled"
    SUSPENDED   = "disabled"
    REMOVED     = "uninstalled"

# ── Permissions (spec 38 + legacy) ────────────────────────────────────────────
class Permission(str, Enum):
    CAMERA        = "camera"
    MICROPHONE    = "microphone"
    MEMORY        = "memory"
    INTERNET      = "internet"
    NOTIFICATIONS = "notifications"
    FILES         = "files"
    CALENDAR      = "calendar"
    PLUGINS       = "plugins"   # lisatud spec 38
    DEVICE        = "device"    # lisatud spec 38
    EMAIL         = "email"
    VEHICLE_DATA  = "vehicle_data"

SENSITIVE_PERMISSIONS = {
    Permission.CAMERA, Permission.MICROPHONE, Permission.EMAIL,
    Permission.VEHICLE_DATA, Permission.MEMORY, Permission.DEVICE,
}

# ── Supported event subscriptions (spec 38) ───────────────────────────────────
SUBSCRIBABLE_EVENTS = {
    "AppStarted", "WorkspaceChanged", "VoiceRecognized",
    "VisionCompleted", "MemoryUpdated", "ProviderChanged", "PluginInstalled",
}

# ── Manifest (spec 38 folder structure) ──────────────────────────────────────
@dataclass
class PluginManifest:
    id:          str
    name:        str
    version:     str
    author:      str
    permissions: list[str]
    entry:       str = "plugin.py"
    description: str = ""
    sdk_version: str = SDK_VERSION
    events:      list[str] = field(default_factory=list)

    @classmethod
    def from_dict(cls, d: dict) -> "PluginManifest":
        return cls(
            id=d["id"], name=d["name"], version=d["version"],
            author=d.get("author", "unknown"),
            permissions=d.get("permissions", []),
            entry=d.get("entry", "plugin.py"),
            description=d.get("description", ""),
            sdk_version=d.get("sdk_version", SDK_VERSION),
            events=d.get("events", []),
        )

    def validate(self) -> list[str]:
        """Tagastab vigade nimekirja (tühi = OK)."""
        errors = []
        if not self.id or "." not in self.id:
            errors.append("id peab olema reverse-domain formaadis (nt com.albert.bmw)")
        if not self.name:
            errors.append("name on kohustuslik")
        if not self.version or len(self.version.split(".")) != 3:
            errors.append("version peab olema semver (nt 1.0.0)")
        unknown_perms = [p for p in self.permissions
                         if p not in {x.value for x in Permission}]
        if unknown_perms:
            errors.append(f"Tundmatud load: {unknown_perms}")
        unknown_evts = [e for e in self.events if e not in SUBSCRIBABLE_EVENTS]
        if unknown_evts:
            errors.append(f"Tundmatud sündmused: {unknown_evts}")
        return errors

# ── Plugin base class (spec 38 interface) ─────────────────────────────────────
class AlbertPlugin:
    plugin_id:   str = "unnamed"
    name:        str = "Unnamed Plugin"
    version:     str = "1.0.0"
    author:      str = "Unknown"
    description: str = ""
    permissions: list[Permission] = []
    commands:    list[str]        = []
    subscribed_events: list[str]  = []   # sündmused millele plugin subscribib

    def __init__(self):
        self.state = PluginState.INSTALLED
        self._registry: "PluginRegistry | None" = None
        self.manifest: PluginManifest | None = None

    # ── Spec 38 interface (on_load/on_enable/on_disable/on_unload/on_event) ───
    async def on_load(self):   pass   # plugin laaditi mällu
    async def on_enable(self): pass   # plugin aktiveeriti
    async def on_disable(self): pass  # plugin deaktiveeriti (temp)
    async def on_unload(self): pass   # plugin eemaldati täielikult
    async def on_event(self, event_type: str, data: dict): pass  # üldine sündmus

    # ── Legacy lifecycle aliases (backward compat) ────────────────────────────
    async def on_startup(self):  await self.on_enable()
    async def on_shutdown(self): await self.on_disable()

    # ── Domain-specific event hooks ───────────────────────────────────────────
    async def on_voice_command(self, text: str, lang: str) -> str | None: return None
    async def on_image_captured(self, image_b64: str, prompt: str) -> str | None: return None
    async def on_memory_updated(self, key: str, value: Any): pass
    async def on_workspace_changed(self, workspace_id: str): pass
    async def on_device_connected(self, device_id: str): pass
    async def on_tool_invoked(self, tool_name: str, args: dict) -> Any: return None

    # ── SDK helpers ───────────────────────────────────────────────────────────
    def notify(self, msg: str, level: str = "info"):
        if self._registry:
            self._registry.broadcast_event("notification",
                {"plugin": self.plugin_id, "msg": msg, "level": level})

    def has_permission(self, perm: str) -> bool:
        if self._registry:
            try:
                return self._registry.has_permission(self.plugin_id, Permission(perm))
            except ValueError:
                return False
        return False

    async def run_command(self, cmd: str, args: dict = None) -> str:
        return f"[{self.plugin_id}] Command '{cmd}' not implemented"


# ── PluginLoader — manifest.json põhine laadimine ────────────────────────────
class PluginLoader:
    """Laadib pluginaid manifest.json failide põhjal (spec 38 folder structure)."""

    @staticmethod
    def load_manifest(directory: str | Path) -> PluginManifest | None:
        path = Path(directory) / "manifest.json"
        if not path.exists():
            return None
        try:
            d = json.loads(path.read_text(encoding="utf-8"))
            m = PluginManifest.from_dict(d)
            errors = m.validate()
            if errors:
                log.warning("Manifest vead %s: %s", directory, errors)
                return None
            return m
        except Exception as e:
            log.warning("Manifest laadimine ebaõnnestus %s: %s", directory, e)
            return None

    @staticmethod
    def validate_manifest(data: dict) -> list[str]:
        """Kontrollib manifest dict'i — tagastab vigade nimekirja."""
        try:
            m = PluginManifest.from_dict(data)
            return m.validate()
        except KeyError as e:
            return [f"Puuduv väli: {e}"]


# ── Plugin Registry ───────────────────────────────────────────────────────────
class PluginRegistry:
    def __init__(self):
        self._plugins: dict[str, AlbertPlugin] = {}
        self._approved_permissions: dict[str, set[Permission]] = {}
        self._event_listeners: dict[str, list[Callable]] = {}

    # ── Register (Installed → Loaded) ─────────────────────────────────────────
    def register(self, plugin: AlbertPlugin) -> dict:
        pid = plugin.plugin_id
        if not pid or pid == "unnamed":
            raise ValueError("plugin_id on kohustuslik")
        if pid in self._plugins and self._plugins[pid].state == PluginState.ENABLED:
            raise ValueError(f"Plugin '{pid}' on juba aktiivne")

        if not self._validate(plugin):
            plugin.state = PluginState.ERROR
            return {"ok": False, "error": "Valideerimine ebaõnnestus"}

        plugin.state = PluginState.LOADED
        plugin._registry = self

        approved = set()
        for perm in plugin.permissions:
            if perm not in SENSITIVE_PERMISSIONS:
                approved.add(perm)
        self._approved_permissions[pid] = approved
        self._plugins[pid] = plugin
        log.info("Plugin laaditud: %s v%s", pid, plugin.version)
        return {
            "ok": True, "plugin_id": pid, "state": "loaded",
            "needs_approval": [p.value for p in plugin.permissions if p in SENSITIVE_PERMISSIONS],
        }

    def _validate(self, plugin: AlbertPlugin) -> bool:
        return bool(plugin.plugin_id and plugin.name and plugin.version and
                    isinstance(plugin.permissions, list))

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

    # ── Enable (Loaded/Disabled → Enabled) ────────────────────────────────────
    async def enable(self, plugin_id: str) -> dict:
        plugin = self._plugins.get(plugin_id)
        if not plugin:
            return {"ok": False, "error": "Plugin ei leitud"}
        if plugin.state == PluginState.ENABLED:
            return {"ok": True, "state": "already_enabled"}
        try:
            if plugin.state == PluginState.LOADED:
                await plugin.on_load()
            await plugin.on_enable()
            plugin.state = PluginState.ENABLED
            self._subscribe_to_events(plugin)
            log.info("Plugin enabled: %s", plugin_id)
            from core.events import emit_sync, PLUGIN_LOADED
            emit_sync(PLUGIN_LOADED, {"plugin_id": plugin_id, "name": plugin.name},
                      source="PluginRegistry")
            return {"ok": True, "state": plugin.state}
        except Exception as e:
            plugin.state = PluginState.ERROR
            log.error("Plugin enable viga %s: %s", plugin_id, e)
            return {"ok": False, "error": str(e)}

    # ── Disable (Enabled → Disabled) ─────────────────────────────────────────
    async def disable(self, plugin_id: str) -> dict:
        plugin = self._plugins.get(plugin_id)
        if not plugin or plugin.state != PluginState.ENABLED:
            return {"ok": False, "error": "Plugin pole aktiivne"}
        try:
            await plugin.on_disable()
            plugin.state = PluginState.DISABLED
            log.info("Plugin disabled: %s", plugin_id)
            return {"ok": True, "state": plugin.state}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    # ── Uninstall (any → Uninstalled) ─────────────────────────────────────────
    async def uninstall(self, plugin_id: str) -> dict:
        plugin = self._plugins.get(plugin_id)
        if not plugin:
            return {"ok": False, "error": "Plugin ei leitud"}
        if plugin.state == PluginState.ENABLED:
            await plugin.on_disable()
        await plugin.on_unload()
        plugin.state = PluginState.UNINSTALLED
        self._plugins.pop(plugin_id, None)
        self._approved_permissions.pop(plugin_id, None)
        log.info("Plugin uninstalled: %s", plugin_id)
        return {"ok": True}

    # ── Legacy compatibility ──────────────────────────────────────────────────
    async def initialize(self, plugin_id: str) -> dict:
        return await self.enable(plugin_id)

    async def initialize_all(self):
        for pid in list(self._plugins):
            if self._plugins[pid].state == PluginState.LOADED:
                await self.enable(pid)

    async def suspend(self, plugin_id: str):
        await self.disable(plugin_id)

    async def remove(self, plugin_id: str):
        await self.uninstall(plugin_id)

    # ── Event Bus integration (spec 38 — subscribe only to required events) ───
    def _subscribe_to_events(self, plugin: AlbertPlugin) -> None:
        from core.events import on as bus_on
        async def _handler(data: dict):
            try:
                await plugin.on_event(data.get("type", ""), data)
            except Exception as e:
                log.warning("Plugin %s event handler viga: %s", plugin.plugin_id, e)
        for event_name in (plugin.subscribed_events or []):
            if event_name in SUBSCRIBABLE_EVENTS:
                bus_on(event_name, _handler)

    # ── Event dispatch (domain events → plugin hooks) ─────────────────────────
    async def dispatch(self, event: str, **kwargs) -> list[Any]:
        results = []
        for plugin in self._plugins.values():
            if plugin.state != PluginState.ENABLED:
                continue
            try:
                handler = getattr(plugin, f"on_{event}", None)
                if handler:
                    result = await handler(**kwargs)
                    if result is not None:
                        results.append({"plugin": plugin.plugin_id, "result": result})
            except Exception as e:
                log.warning("Plugin %s event %s viga: %s", plugin.plugin_id, event, e)
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
            "plugin_id":        p.plugin_id,
            "name":             p.name,
            "version":          p.version,
            "author":           p.author,
            "description":      p.description,
            "state":            p.state.value,
            "permissions":      [x.value for x in p.permissions],
            "commands":         p.commands,
            "subscribed_events": p.subscribed_events,
        } for p in self._plugins.values()]

    def get_plugin(self, plugin_id: str) -> AlbertPlugin | None:
        return self._plugins.get(plugin_id)

    def get(self, key: str, default=None):
        """Legacy: server.py kasutab get_registry().get('plugins', [])"""
        if key == "plugins":
            return self.list_plugins()
        return default


# ── Global registry (singleton) ───────────────────────────────────────────────
registry = PluginRegistry()


def get_registry() -> PluginRegistry:
    return registry
