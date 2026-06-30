import json
import os
from datetime import datetime

MEMORY_FILE = os.path.join(os.path.dirname(__file__), "jarvis_memory.json")

def _load():
    if not os.path.exists(MEMORY_FILE):
        return {"interactions": [], "user_prefs": {}, "learned_skills": [], "stats": {"total": 0}}
    with open(MEMORY_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def _save(data):
    with open(MEMORY_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def save_interaction(device_id: str, prompt: str, responses: list):
    data = _load()
    data["interactions"].append({
        "ts": datetime.now().isoformat(),
        "device": device_id,
        "prompt": prompt[:500],
        "agents": [r["id"] for r in responses if r.get("response")],
    })
    data["stats"]["total"] += 1
    # hoia vaid viimased 500 interaktsiooni
    data["interactions"] = data["interactions"][-500:]
    _save(data)

def get_stats():
    data = _load()
    return data["stats"]

def get_recent(n=10):
    data = _load()
    return data["interactions"][-n:]

def save_pref(key: str, value):
    data = _load()
    data["user_prefs"][key] = value
    _save(data)

def get_prefs():
    return _load().get("user_prefs", {})
