"""
Albert OS — Routing Configuration
Mudeli marsruutimine intent'i järgi. Muuda siit, mitte director.py-st.
Uue provideri lisamiseks: lisa PROVIDERS-sse + ROUTING-sse. Rohkem muutusi ei ole vaja.
"""

# ── Intent klassifikaator — märksõnad ────────────────────────────────────────
INTENT_PATTERNS = {
    "coding": [
        "код", "code", "программ", "debug", "ошибка в", "функц", "скрипт",
        "python", "javascript", "sql", "json", "api", "class", "error",
        "kood", "viga", "funktsioon", "skript"
    ],
    "vision": [],  # tuvastab has_image lipuga
    "research": [
        # Russian
        "найди", "поищи", "погода", "курс", "новости", "цена", "сейчас",
        "сегодня", "актуальн", "кто такой", "что такое", "когда был", "кто выиграл",
        "последн", "текущ", "в этом году", "в 2024", "в 2025",
        # English
        "find", "search", "weather", "news", "price", "who is", "what is", "when was",
        "latest", "current", "today", "recently", "right now",
        # Estonian — factual / real-time / current info
        "otsi", "uudised", "ilm", "hind", "praegu", "täna", "hetkel", "hiljuti",
        "viimati", "kes on", "mis on", "millal", "kus on", "kui palju maksab",
        "bitcoin", "krüpto", "aktsia", "valuuta", "euro", "dollar",
        "temperatuur", "prognoos", "ilmaprognoos",
        "võitis", "kaotas", "tulemus", "skoor",
        "2024", "2025", "sel aastal", "sel nädalal",
    ],
    "bmw_diagnostics": [
        "bmw", "бмв", "двигател", "мотор", "ошибка bmw", "неисправн", "obd", "dtc",
        "dme", "dsc", "egs", "fault code", "диагностик", "mootor", "rike",
        "вибрац", "стук", "шум", "течь", "утечка", "масло", "тормоз",
        "bmw rike", "bmw viga", "bmw mootor"
    ],
    "boat_diagnostics": [
        "лодк", "boat", "яхт", "катер", "морск", "двигател лодк",
        "paat", "jaht", "meri", "mootorpaat", "purjekas",
        "якор", "курс", "скорость лодк", "gps", "navtex", "colreg",
        "anchorage", "течь лодк", "bilge", "ruder",
        "volvo penta", "volvo", "penta", "laevamootor", "paadimootor",
        "mootoripaat", "mootori", "diagnostics", "diagonoosi",
    ],
    "construction": [
        "строительств", "ремонт", "бетон", "фундамент", "стен", "крыш",
        "ehitus", "remont", "betoon", "vundament", "sein", "katus",
        "elektr", "santehник", "труб", "construction", "build", "plumbing"
    ],
    "diagnostics": [
        "engine", "fault", "ошибка", "неисправн", "диагностик", "mootor", "rike",
        "вибрац", "стук", "шум", "течь", "утечка"
    ],
    "translation": [
        "переведи", "перевод", "translate", "tõlgi", "tõlkige", "tõlge"
    ],
    "planning": [
        "план", "расписани", "напомни", "запланируй", "schedule", "планир",
        "plaan", "meeldetulet", "ajasta", "deadline", "срок"
    ],
    "business": [
        "бизнес", "клиент", "счёт", "договор", "продаж", "выручк",
        "äri", "klient", "arve", "leping", "müük", "business", "invoice", "contract"
    ],
    "calendar": [
        "календар", "встреч", "собрани", "событи", "завтра", "послезавтра",
        "kalender", "kohtumine", "meeting", "calendar", "event", "tomorrow"
    ],
    "device_control": [
        "открой", "закрой", "запусти", "останови", "включи", "выключи",
        "ava", "sulge", "käivita", "lülita", "open", "close", "start", "stop",
        "экран", "компьютер", "телефон", "прилл"
    ],
    "general": []  # vaikimisi
}

# ── Provider kataloog — lisa uus provider siia ───────────────────────────────
PROVIDERS = {
    "openai": {
        "models": {"fast": "gpt-4o-mini", "smart": "gpt-4o"},
        "strengths": ["general", "vision", "planning", "calendar"],
        "supports_vision": True,
        "supports_tools": True,
        "env_key": "OPENAI_API_KEY",
    },
    "claude": {
        "models": {"fast": "claude-haiku-4-5-20251001", "smart": "claude-sonnet-4-6"},
        "strengths": ["coding", "diagnostics", "business", "translation", "long_document"],
        "supports_vision": True,
        "supports_tools": False,
        "env_key": "ANTHROPIC_API_KEY",
    },
    "gemini": {
        "models": {"fast": "gemini-2.0-flash", "smart": "gemini-2.5-flash"},
        "strengths": ["vision", "translation", "general"],
        "supports_vision": True,
        "supports_tools": False,
        "env_key": "GEMINI_API_KEY",
    },
    "perplexity": {
        "models": {"fast": "llama-3.1-sonar-small-128k-online", "smart": "llama-3.1-sonar-large-128k-online"},
        "strengths": ["research"],
        "supports_vision": False,
        "supports_tools": False,
        "env_key": "PERPLEXITY_API_KEY",
    },
    # Tulevikus: "grok", "llama", "deepseek", "local_ollama"
}

# ── Marsruutimise tabel intent → provider ────────────────────────────────────
ROUTING = {
    "general":        {"primary": "openai",      "verify_with": None,        "parallel": False},
    "coding":         {"primary": "claude",       "verify_with": None,        "parallel": False},
    "vision":         {"primary": "openai",       "verify_with": "gemini",    "parallel": True},
    "research":       {"primary": "perplexity",   "verify_with": None,        "parallel": False},
    "bmw_diagnostics":  {"primary": "claude",       "verify_with": "openai",    "parallel": True},
    "boat_diagnostics": {"primary": "claude",       "verify_with": "openai",    "parallel": True},
    "construction":     {"primary": "claude",       "verify_with": None,        "parallel": False},
    "diagnostics":      {"primary": "claude",       "verify_with": "openai",    "parallel": True},
    "translation":    {"primary": "gemini",       "verify_with": None,        "parallel": False},
    "planning":       {"primary": "openai",       "verify_with": None,        "parallel": False},
    "business":       {"primary": "claude",       "verify_with": None,        "parallel": False},
    "calendar":       {"primary": "openai",       "verify_with": None,        "parallel": False},
    "device_control": {"primary": "openai",       "verify_with": None,        "parallel": False},
}

# ── Fallback järjestus kui primary kukub ─────────────────────────────────────
FALLBACK_CHAIN = ["openai", "claude", "gemini"]
