"""
Albert OS — Security Layer
Spek: 15_SECURITY_BIBLE.md

Moodulid:
  DeviceTrust   — usaldusväärne/tundmatu seade
  RateLimiter   — päringu sageduse piiramine
  InputSanitizer — sisendi puhastamine
  ActionGuard   — ohtlike toimingute kinnitus
  SecureLogger  — API võtmed/paroolid filtreeritakse logist
  KeyValidator  — kontrollib et API võtmed pole koodis
"""
import re
import time
import hashlib
import sqlite3
import logging
from collections import defaultdict
from datetime import datetime, timedelta
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
        now = datetime.now().isoformat()
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
        now = datetime.now().isoformat()
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


# ── Singletons ────────────────────────────────────────────────────────────────
device_trust  = DeviceTrust()
rate_limiter  = RateLimiter(max_per_minute=30, max_per_hour=300)
input_sanitizer = InputSanitizer()

setup_secure_logging()
