"""
Albert OS — Public SDK
Spek: 47_ALBERT_OS_SDK_BIBLE.md

Avalik SDK Albert OS laiendamiseks:
  - Plugin SDK    → core.plugin_sdk
  - Provider SDK  → core.adapters
  - Memory SDK    → memory.repositories
  - Tool SDK      → core.tools (kui olemas)
  - Event SDK     → core.events
  - Security SDK  → core.security (RoleManager, SecretManager)

SDK Version follows Albert OS versioning.
"""
from core.version import VERSION as SDK_VERSION

# ── Plugin SDK (spec 38, 47) ──────────────────────────────────────────────────
from core.plugin_sdk import (
    AlbertPlugin,
    PluginManifest,
    PluginState,
    Permission,
    SUBSCRIBABLE_EVENTS,
    SDK_VERSION as PLUGIN_SDK_VERSION,
)

# ── Provider SDK (spec 33, 47) ────────────────────────────────────────────────
from core.adapters import (
    BaseAdapter,
    ProviderMeta,
)

# ── Event SDK (spec 36, 47) ───────────────────────────────────────────────────
from core.events import (
    emit,
    emit_sync,
    on,
    off,
    get_history,
)

# ── Security SDK (spec 40, 47) ────────────────────────────────────────────────
from core.security import (
    SecretManager,
    RoleManager,
    Role,
    PromptInjectionDetector,
)

# ── Task SDK (spec 44, 47) ────────────────────────────────────────────────────
from core.task_engine import (
    TaskEngine,
    ScheduledTask,
    TaskType,
    TaskStatus,
    TaskPriority,
)

# ── Memory SDK (spec 35, 47) ──────────────────────────────────────────────────
from memory.repositories import (
    memories,
    projects,
    conversations,
)


def sdk_info() -> dict:
    """Albert OS SDK versioon ja saadaolevad moodulid."""
    return {
        "sdk_version":        SDK_VERSION,
        "plugin_sdk_version": PLUGIN_SDK_VERSION,
        "modules": [
            "plugin",   # AlbertPlugin, PluginManifest, Permission
            "provider", # BaseAdapter, ProviderMeta
            "events",   # emit, on, off, get_history
            "security", # SecretManager, RoleManager, Role
            "tasks",    # TaskEngine, ScheduledTask
            "memory",   # memories, projects, conversations repositories
        ],
    }


__all__ = [
    "SDK_VERSION",
    "AlbertPlugin", "PluginManifest", "PluginState", "Permission",
    "SUBSCRIBABLE_EVENTS", "PLUGIN_SDK_VERSION",
    "BaseAdapter", "ProviderMeta",
    "emit", "emit_sync", "on", "off", "get_history",
    "SecretManager", "RoleManager", "Role", "PromptInjectionDetector",
    "TaskEngine", "ScheduledTask", "TaskType", "TaskStatus", "TaskPriority",
    "memories", "projects", "conversations",
    "sdk_info",
]
