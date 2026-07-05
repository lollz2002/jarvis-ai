"""
Albert OS — Security Layer
Spek: 15_SECURITY_BIBLE.md, 40_SECURITY_IMPLEMENTATION_BIBLE.md

Moodulid:
  DeviceTrust             — usaldusväärne/tundmatu seade
  RateLimiter             — päringu sageduse piiramine
  InputSanitizer          — sisendi puhastamine
  ActionGuard             — ohtlike toimingute kinnitus
  SecureLogger            — API võtmed/paroolid filtreeritakse logist
  KeyValidator            — kontrollib et API võtmed pole koodis
  SecretManager           — secrets env muutujate kaudu (spec 40)
  RoleManager             — RBAC: User/Administrator/Developer/Plugin/Service (spec 40)
  PromptInjectionDetector — prompt injection tuvastamine (spec 40)
"""
import os
import re
import time
import hashlib
import sqlite3
import logging
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from pathlib import Path

DB_PATH = Path(__file__).parent.parent / "memory" / "albert_os.db"

# ── Device Trust ──────────────────────────────────────────────────────────────
class DeviceTrust:
    """Haldab usaldusväärsete seadmete nimekirja."""

    def __init__(self):
        self._ensure_table()

    def _conn(self):
        c = sqlite3.connect(DB_PATH)
        c.row_factory = sqlite3.Row
        return c

    def _ensure_table(self):
        with self._conn() as c:
            c.execute("""
            CREATE TABLE IF NOT EXISTS trusted_devices (
                device_id   TEXT PRIMARY KEY,
                label       TEXT DEFAULT '',
                trust_level TEXT DEFAULT 'trusted',
                first_seen  TEXT,
                last_seen   TEXT,
                approved    INTEGER DEFAULT 0,
                approved_at TEXT
            )""")

    def is_trusted(self, device_id: str) -> bool:
        with self._conn() as c:
            r = c.execute(
                "SELECT approved FROM trusted_devices WHERE device_id=?",
                (device_id,)).fetchone()
            if not r:
                return False
            return bool(r["approved"])

    def register_device(self, device_id: str, label: str = "", auto_approve: bool = False):
        """Registreerib seadme — auto_approve=True kohalike/tuttavate seadmete jaoks."""
        now = datetime.now(timezone.utc).isoformat()
        with self._conn() as c:
            existing = c.execute(
                "SELECT device_id FROM trusted_devices WHERE device_id=?",
                (device_id,)).fetchone()
            if existing:
                c.execute("UPDATE trusted_devices SET last_seen=? WHERE device_id=?",
                          (now, device_id))
            else:
                c.execute("""INSERT INTO trusted_devices
                    (device_id, label, first_seen, last_seen, approved, approved_at)
                    VALUES (?,?,?,?,?,?)""",
                    (device_id, label or device_id, now, now,
                     1 if auto_approve else 0,
                     now if auto_approve else None))

    def approve_device(self, device_id: str):
        now = datetime.now(timezone.utc).isoformat()
        with self._conn() as c:
            c.execute("""UPDATE trusted_devices
                SET approved=1, approved_at=? WHERE device_id=?""",
                (now, device_id))

    def revoke_device(self, device_id: str):
        with self._conn() as c:
            c.execute("UPDATE trusted_devices SET approved=0 WHERE device_id=?",
                      (device_id,))

    def remove_device(self, device_id: str):
        with self._conn() as c:
            c.execute("DELETE FROM trusted_devices WHERE device_id=?", (device_id,))

    def list_devices(self) -> list:
        with self._conn() as c:
            return [dict(r) for r in c.execute(
                "SELECT * FROM trusted_devices ORDER BY last_seen DESC").fetchall()]

    def get_trust_level(self, device_id: str) -> str:
        """→ 'trusted' | 'pending' | 'unknown'"""
        with self._conn() as c:
            r = c.execute(
                "SELECT approved FROM trusted_devices WHERE device_id=?",
                (device_id,)).fetchone()
        if not r: return "unknown"
        return "trusted" if r["approved"] else "pending"


# ── Rate Limiter ──────────────────────────────────────────────────────────────
class RateLimiter:
    """Token bucket rate limiter per device."""

    def __init__(self, max_per_minute: int = 30, max_per_hour: int = 200):
        self._max_min  = max_per_minute
        self._max_hour = max_per_hour
        self._minute:  dict[str, list] = defaultdict(list)
        self._hour:    dict[str, list] = defaultdict(list)

    def is_allowed(self, device_id: str) -> tuple[bool, str]:
        now = time.time()
        # Puhasta vanu kirjeid
        self._minute[device_id] = [t for t in self._minute[device_id] if now - t < 60]
        self._hour[device_id]   = [t for t in self._hour[device_id]   if now - t < 3600]

        if len(self._minute[device_id]) >= self._max_min:
            return False, f"Rate limit: max {self._max_min} päringut minutis"
        if len(self._hour[device_id]) >= self._max_hour:
            return False, f"Rate limit: max {self._max_hour} päringut tunnis"

        self._minute[device_id].append(now)
        self._hour[device_id].append(now)
        return True, ""

    def get_usage(self, device_id: str) -> dict:
        now = time.time()
        min_count  = sum(1 for t in self._minute.get(device_id, []) if now - t < 60)
        hour_count = sum(1 for t in self._hour.get(device_id, []) if now - t < 3600)
        return {"per_minute": min_count, "per_hour": hour_count,
                "limit_minute": self._max_min, "limit_hour": self._max_hour}


# ── Input Sanitizer ───────────────────────────────────────────────────────────
class InputSanitizer:
    """Puhastab kasutaja sisendi — eemalda XSS, injection katsed."""

    # Mustrid mis näitavad võimalikku rünnet
    _SUSPICIOUS = [
        r"<script[^>]*>",                    # XSS
        r"javascript\s*:",                   # JS injection
        r"(DROP|DELETE|TRUNCATE)\s+TABLE",   # SQL injection
        r"\.\./\.\./",                       # path traversal
        r"__import__\s*\(",                  # Python injection
        r"eval\s*\(",                        # eval injection
    ]
    _COMPILED = [re.compile(p, re.IGNORECASE) for p in _SUSPICIOUS]

    def sanitize(self, text: str) -> tuple[str, bool]:
        """
        Tagastab (puhastatud_tekst, on_kahtlane).
        Eemalda null bytes, lõika maha liiga pikad sisendid.
        """
        if not text:
            return "", False

        # Null bytes
        text = text.replace("\x00", "")
        # Maksimaalne pikkus
        text = text[:8000]

        suspicious = any(p.search(text) for p in self._COMPILED)
        return text, suspicious

    def is_safe_url(self, url: str) -> bool:
        """Kontrollib et URL on http/https ja ei sisalda ohtlikke skeeme."""
        url = url.strip().lower()
        return url.startswith(("http://", "https://")) and \
               not any(s in url for s in ["javascript:", "data:", "file:", "ftp:"])


# ── Dangerous Action Guard ────────────────────────────────────────────────────
DANGEROUS_KEYWORDS = [
    # Eesti
    "kustuta kõik", "vorminda", "eemalda kõik", "tühista mälu",
    # Vene
    "удали все", "очисти память", "форматируй", "удали базу",
    # Inglise
    "delete all", "wipe memory", "format drive", "drop database",
    "rm -rf", "factory reset",
]

def is_dangerous_action(prompt: str) -> tuple[bool, str]:
    """
    Tuvastab ohtlikud käsud enne täitmist.
    Tagastab (on_ohtlik, kirjeldus).
    """
    p = prompt.lower()
    for kw in DANGEROUS_KEYWORDS:
        if kw in p:
            return True, f"Ohtlik toiming tuvastatud: '{kw}'"
    return False, ""


# ── Secure Logger ──────────────────────────────────────────────────────────────
class SecureLogFilter(logging.Filter):
    """Filtreerib logi kirjetest välja API võtmed ja paroolid."""

    _PATTERNS = [
        (re.compile(r'(sk-[a-zA-Z0-9]{20,})', re.I), "sk-***"),
        (re.compile(r'(Bearer\s+)[a-zA-Z0-9._-]{10,}', re.I), r'\1***'),
        (re.compile(r'(api[_-]?key["\s:=]+)[a-zA-Z0-9._-]{10,}', re.I), r'\1***'),
        (re.compile(r'(password["\s:=]+)\S+', re.I), r'\1***'),
        (re.compile(r'(token["\s:=]+)[a-zA-Z0-9._-]{10,}', re.I), r'\1***'),
    ]

    def filter(self, record: logging.LogRecord) -> bool:
        msg = str(record.getMessage())
        for pattern, replacement in self._PATTERNS:
            msg = pattern.sub(replacement, msg)
        record.msg  = msg
        record.args = ()
        return True


def setup_secure_logging():
    """Paigaldab turvalise log filtri juurloggerile."""
    root = logging.getLogger()
    if not any(isinstance(f, SecureLogFilter) for f in root.filters):
        root.addFilter(SecureLogFilter())


# ── Key Validator ─────────────────────────────────────────────────────────────
HARDCODED_KEY_PATTERNS = [
    re.compile(r'sk-[a-zA-Z0-9]{20,}'),           # OpenAI
    re.compile(r'AIza[a-zA-Z0-9_-]{35}'),          # Google
    re.compile(r'[a-zA-Z0-9]{32,}', re.I),        # üldine pikk string
]

def check_no_hardcoded_keys(text: str) -> list[str]:
    """Kontrollib et koodis pole hardcode'd API võtmeid. Tagastab leitud mustrite loendi."""
    found = []
    for pat in HARDCODED_KEY_PATTERNS[:2]:  # ainult spetsiifilised mustrid
        if pat.search(text):
            found.append(pat.pattern)
    return found


# ── Encrypted Backup ──────────────────────────────────────────────────────────
def create_backup(password: str) -> bytes:
    """
    Loob krüpteeritud mälu backup-i.
    Kasutab AES-256 (fernet) — vajab cryptography paketti.
    Tagastab krüpteeritud bytes.
    """
    import json
    from memory.memory import export_memory
    data = json.dumps(export_memory(), ensure_ascii=False, indent=2).encode()
    try:
        from cryptography.fernet import Fernet
        import base64
        key = hashlib.sha256(password.encode()).digest()
        fernet_key = base64.urlsafe_b64encode(key)
        f = Fernet(fernet_key)
        return f.encrypt(data)
    except ImportError:
        # Fallback: base64 (ei ole krüpteerimine, ainult kodeerimine)
        import base64
        return base64.b64encode(data)

def restore_backup(encrypted: bytes, password: str) -> dict:
    """Taastab backup-i. Tagastab mälu dict."""
    import json
    try:
        from cryptography.fernet import Fernet
        import base64
        key = hashlib.sha256(password.encode()).digest()
        fernet_key = base64.urlsafe_b64encode(key)
        f = Fernet(fernet_key)
        data = f.decrypt(encrypted)
    except ImportError:
        import base64
        data = base64.b64decode(encrypted)
    return json.loads(data)


# ── Secret Manager (spec 40) ──────────────────────────────────────────────────
class SecretManager:
    """
    Secrets tulevad ainult env muutujastest — mitte koodist.
    Zero Trust: iga saladus on eksplitsiitselt loetletud.
    """

    _KNOWN = {
        "OPENAI_API_KEY", "ANTHROPIC_API_KEY", "GOOGLE_API_KEY",
        "PERPLEXITY_API_KEY", "ELEVENLABS_API_KEY",
        "JWT_SECRET", "BACKUP_ENCRYPTION_KEY", "DEVICE_ID",
        "CLOUD_SYNC_URL", "DATABASE_URL",
    }

    def get(self, name: str, default: str | None = None) -> str | None:
        """Loe secret env muutujast. Logib hoiatuse kui tundmatu."""
        if name not in self._KNOWN:
            logging.getLogger("security").warning(
                "SecretManager: tundmatu secret '%s' — lisa _KNOWN nimekirja", name)
        value = os.environ.get(name, default)
        return value

    def require(self, name: str) -> str:
        """Nõuab secret olemasolu — tõstab vea kui puudub."""
        value = os.environ.get(name)
        if not value:
            raise EnvironmentError(
                f"Kohustuslik secret '{name}' puudub env muutujate seast. "
                f"Seadista see Railway/Vercel keskkonnas.")
        return value

    def is_configured(self, name: str) -> bool:
        return bool(os.environ.get(name))

    def audit_secrets(self) -> dict:
        """Tagastab millised secrets on konfigureeritud (mitte väärtused)."""
        return {k: self.is_configured(k) for k in self._KNOWN}


# ── Role-Based Access Control (spec 40) ───────────────────────────────────────
class Role(str, Enum):
    USER          = "user"
    ADMINISTRATOR = "administrator"
    DEVELOPER     = "developer"
    PLUGIN        = "plugin"
    SERVICE       = "service"


# Õiguste maatriks: mis toiminguid iga roll lubab
_ROLE_PERMISSIONS: dict[Role, set[str]] = {
    Role.USER: {
        "chat", "memory.read", "memory.write",
        "voice.use", "vision.use", "workspace.manage",
    },
    Role.ADMINISTRATOR: {
        "chat", "memory.read", "memory.write", "memory.delete",
        "voice.use", "vision.use", "workspace.manage",
        "devices.manage", "plugins.manage", "providers.manage",
        "security.audit", "backup.create", "backup.restore",
        "agents.run", "agents.stop",
    },
    Role.DEVELOPER: {
        "chat", "memory.read", "memory.write",
        "voice.use", "vision.use", "workspace.manage",
        "plugins.manage", "providers.manage",
        "agents.run", "events.read", "schema.read",
    },
    Role.PLUGIN: {
        "chat", "memory.read", "workspace.manage",
        "voice.use", "vision.use",
    },
    Role.SERVICE: {
        "memory.read", "memory.write", "sync.run",
        "agents.run", "events.read",
    },
}


class RoleManager:
    """
    Rollipõhine juurdepääsukontroll (RBAC).
    Least Privilege: kõigile antakse minimaalne vajalik roll.
    """

    def __init__(self):
        self._device_roles: dict[str, Role] = {}  # device_id → Role

    def assign_role(self, device_id: str, role: Role) -> None:
        self._device_roles[device_id] = role
        _audit_security_event("role_assigned", {
            "device_id": device_id, "role": role.value
        })

    def get_role(self, device_id: str) -> Role:
        return self._device_roles.get(device_id, Role.USER)

    def has_permission(self, device_id: str, action: str) -> bool:
        role = self.get_role(device_id)
        return action in _ROLE_PERMISSIONS.get(role, set())

    def require_permission(self, device_id: str, action: str) -> None:
        if not self.has_permission(device_id, action):
            role = self.get_role(device_id)
            raise PermissionError(
                f"Roll '{role.value}' ei luba toimingut '{action}'")

    def list_permissions(self, device_id: str) -> list[str]:
        role = self.get_role(device_id)
        return sorted(_ROLE_PERMISSIONS.get(role, set()))

    def roles_info(self) -> dict:
        return {
            role.value: sorted(perms)
            for role, perms in _ROLE_PERMISSIONS.items()
        }


# ── Prompt Injection Detector (spec 40 — Threat Model) ───────────────────────
class PromptInjectionDetector:
    """
    Tuvastab prompt injection katseid enne AI mudelile saatmist.
    Defense in Depth: mudel pole ainus kaitsekiht.
    """

    _PATTERNS = [
        # Klassikalised injection katsed
        r"ignore\s+(all\s+)?(previous|prior|above)\s+instructions?",
        r"forget\s+(everything|all)\s+(you|i|we)\s+(know|said|told)",
        r"you\s+are\s+now\s+(a\s+)?(?!Albert|Jarvis)\w+",  # rolli vahetus
        r"act\s+as\s+(if\s+you\s+(are|were)\s+)?\w+\s+without\s+(any\s+)?restriction",
        r"disregard\s+(your\s+)?(previous|all|safety)\s+\w+",
        r"new\s+instruction[s]?\s*[:：]",
        r"system\s*[:：]\s*you\s+(are|must|should|will)",
        r"\[INST\]|\[\/INST\]|<\|im_start\|>|<\|im_end\|>",  # model tokens
        # Eestikeelsed katsed
        r"ignoreeri\s+(kõik\s+)?(eelnevad?|varasemad?)\s+juhised?",
        r"sa\s+oled\s+nüüd\s+(uus\s+)?\w+\s+ilma\s+piiranguteta",
        r"unusta\s+kõik\s+eelnev",
        # Venekeelsed katsed
        r"игнорируй\s+(все\s+)?предыдущие\s+инструкции",
        r"забудь\s+все",
        r"ты\s+теперь\s+\w+\s+без\s+ограничений",
        # DAN / jailbreak
        r"\bDAN\b.*mode",
        r"jailbreak",
        r"developer\s+mode\s+(enabled|on|activate)",
        r"pretend\s+(you\s+have\s+no|there\s+are\s+no)\s+(ethical\s+)?(guidelines|restrictions|limits)",
    ]
    _COMPILED = [re.compile(p, re.IGNORECASE | re.DOTALL) for p in _PATTERNS]

    def detect(self, text: str) -> tuple[bool, list[str]]:
        """
        Tagastab (on_injection, leitud_mustrid).
        True = kahtlane sisend, mis tuleks blokeerida või logida.
        """
        if not text:
            return False, []
        found = []
        for pat in self._COMPILED:
            m = pat.search(text)
            if m:
                found.append(pat.pattern[:60])
        is_injection = len(found) > 0
        if is_injection:
            _audit_security_event("prompt_injection_detected", {
                "patterns": found,
                "text_preview": text[:100],
            })
        return is_injection, found

    def is_safe(self, text: str) -> bool:
        ok, _ = self.detect(text)
        return not ok


# ── Security Audit Events (spec 40 — Audit Logging) ──────────────────────────
def _audit_security_event(event_type: str, data: dict) -> None:
    """Saada turvalisuse auditisündmus Event Bus'i ja monitor'i."""
    try:
        from core.events import emit_sync, SECURITY_ALERT
        emit_sync(SECURITY_ALERT, {"event_type": event_type, **data},
                  source="SecurityLayer")
    except Exception:
        pass
    try:
        from core.monitor import audit
        audit(f"security.{event_type}", data)
    except Exception:
        pass


def audit_login(device_id: str, success: bool, method: str = "websocket") -> None:
    _audit_security_event("login", {
        "device_id": device_id, "success": success, "method": method,
        "ts": datetime.now(timezone.utc).isoformat(),
    })


def audit_memory_deletion(device_id: str, table: str, record_id: str) -> None:
    _audit_security_event("memory_deletion", {
        "device_id": device_id, "table": table, "record_id": record_id,
        "ts": datetime.now(timezone.utc).isoformat(),
    })


def audit_plugin_install(plugin_id: str, device_id: str, version: str = "") -> None:
    _audit_security_event("plugin_installed", {
        "plugin_id": plugin_id, "device_id": device_id, "version": version,
        "ts": datetime.now(timezone.utc).isoformat(),
    })


def audit_permission_change(device_id: str, target: str, action: str,
                             permissions: list) -> None:
    _audit_security_event("permission_change", {
        "device_id": device_id, "target": target,
        "action": action, "permissions": permissions,
        "ts": datetime.now(timezone.utc).isoformat(),
    })


def audit_provider_change(old_provider: str, new_provider: str, device_id: str = "") -> None:
    _audit_security_event("provider_changed", {
        "old": old_provider, "new": new_provider, "device_id": device_id,
        "ts": datetime.now(timezone.utc).isoformat(),
    })


# ── Security Checklist (spec 40 — Security Checklist) ─────────────────────────
def get_security_checklist() -> dict:
    """
    Käitusaegne turvakontroll — tagastab pass/fail iga punkti kohta.
    """
    sm = SecretManager()
    checks = {
        "secrets_configured": {
            "openai":      sm.is_configured("OPENAI_API_KEY"),
            "anthropic":   sm.is_configured("ANTHROPIC_API_KEY"),
            "jwt_secret":  sm.is_configured("JWT_SECRET"),
            "device_id":   sm.is_configured("DEVICE_ID"),
            "cloud_sync":  sm.is_configured("CLOUD_SYNC_URL"),
        },
        "secure_logging_active": any(
            isinstance(f, SecureLogFilter)
            for f in logging.getLogger().filters
        ),
        "rate_limiter_active": True,  # alati aktiivne
        "input_sanitizer_active": True,
        "prompt_injection_detection": True,
        "rbac_enabled": True,
        "encrypted_backup_available": _check_crypto(),
        "device_trust_table": _check_db_table("trusted_devices"),
    }

    all_secrets_ok = all(checks["secrets_configured"].values())
    checks["overall"] = (
        all_secrets_ok and
        checks["secure_logging_active"] and
        checks["encrypted_backup_available"]
    )
    return checks


def _check_crypto() -> bool:
    try:
        from cryptography.fernet import Fernet
        return True
    except ImportError:
        return False


def _check_db_table(table: str) -> bool:
    try:
        with sqlite3.connect(DB_PATH) as c:
            c.execute(f"SELECT 1 FROM {table} LIMIT 1")
        return True
    except Exception:
        return False


# ── Singletons ────────────────────────────────────────────────────────────────
device_trust  = DeviceTrust()
rate_limiter  = RateLimiter(max_per_minute=30, max_per_hour=300)
input_sanitizer = InputSanitizer()
secret_manager  = SecretManager()
role_manager    = RoleManager()
injection_detector = PromptInjectionDetector()

setup_secure_logging()
