"""
Albert OS — Monitoring & Metrics
Spek: 12_API_AND_INTEGRATION_BIBLE.md

Kogub: provider latentsus, vead, retry-d, tööriistade kasutus, mälu timing.
Ei kogu: isiklikku sisu (ainult metaandmed).
"""
import time
from collections import defaultdict, deque
from datetime import datetime
from threading import Lock

_lock = Lock()

# ── Struktuurid ───────────────────────────────────────────────────────────────
_calls: dict[str, list] = defaultdict(list)     # provider → [{"ms":, "ok":, "intent":, "ts":}]
_errors: deque = deque(maxlen=200)              # viimased vead
_tool_usage: dict[str, int] = defaultdict(int) # tool_name → count
_audit_log: deque = deque(maxlen=500)           # audit sündmused

# ── Kirjutamine ───────────────────────────────────────────────────────────────
def record_call(provider: str, intent: str, ms: int, success: bool, error: str = ""):
    entry = {"provider": provider, "intent": intent, "ms": ms,
             "ok": success, "ts": datetime.now().isoformat()}
    with _lock:
        calls = _calls[provider]
        calls.append(entry)
        if len(calls) > 500:
            _calls[provider] = calls[-500:]
        if not success and error:
            _errors.append({"provider": provider, "error": error[:200],
                           "intent": intent, "ts": entry["ts"]})

def record_tool(tool_name: str):
    with _lock:
        _tool_usage[tool_name] += 1
    audit("tool_invoked", {"tool": tool_name})

def audit(event: str, data: dict = None):
    """Audit log — olulised sündmused (ei sisalda isiklikku sisu)."""
    with _lock:
        _audit_log.append({"event": event, "data": data or {},
                           "ts": datetime.now().isoformat()})

# ── Lugemine ──────────────────────────────────────────────────────────────────
def get_stats() -> dict:
    with _lock:
        stats = {}
        for provider, calls in _calls.items():
            if not calls: continue
            ok_calls  = [c for c in calls if c["ok"]]
            all_ms    = [c["ms"] for c in calls]
            ok_ms     = [c["ms"] for c in ok_calls]
            stats[provider] = {
                "total":        len(calls),
                "success":      len(ok_calls),
                "failures":     len(calls) - len(ok_calls),
                "success_rate": round(len(ok_calls) / len(calls) * 100, 1) if calls else 0,
                "avg_ms":       round(sum(all_ms) / len(all_ms)) if all_ms else 0,
                "p95_ms":       _p95(all_ms),
                "ok_avg_ms":    round(sum(ok_ms) / len(ok_ms)) if ok_ms else 0,
                "last_call":    calls[-1]["ts"],
            }
        return stats

def get_errors(n: int = 20) -> list:
    with _lock:
        return list(_errors)[-n:]

def get_tool_usage() -> dict:
    with _lock:
        return dict(sorted(_tool_usage.items(), key=lambda x: -x[1]))

def get_audit_log(n: int = 50) -> list:
    with _lock:
        return list(_audit_log)[-n:]

def get_provider_health() -> dict:
    """Kiire ülevaade iga provideri tervisest."""
    with _lock:
        health = {}
        for provider, calls in _calls.items():
            if not calls:
                health[provider] = "unknown"
                continue
            recent = calls[-10:]
            ok_rate = sum(1 for c in recent if c["ok"]) / len(recent)
            avg_ms  = sum(c["ms"] for c in recent) / len(recent)
            if ok_rate >= 0.8 and avg_ms < 5000:
                health[provider] = "healthy"
            elif ok_rate >= 0.5:
                health[provider] = "degraded"
            else:
                health[provider] = "down"
        return health

def _p95(values: list) -> int:
    if not values: return 0
    s = sorted(values)
    idx = max(0, int(len(s) * 0.95) - 1)
    return s[idx]

# ── Reset (arendus/test) ──────────────────────────────────────────────────────
def reset():
    with _lock:
        _calls.clear()
        _errors.clear()
        _tool_usage.clear()
