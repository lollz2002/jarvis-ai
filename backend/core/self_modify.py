"""
JARVIS enesemuutmise moodul — JARVIS saab ise oma seadeid muuta.
"""
import os
import re

# Dünaamilised seaded (muutuvad käitusajal)
_runtime_config = {
    "voice_speed": 0.95,
    "voice_stability": 0.75,
    "primary_agent": "gpt4o",
    "language": "ru",
    "voice_id": os.getenv("ELEVENLABS_VOICE_ID", "pNInz6obpgDQGcFmaJgB"),
    "use_openai_tts": True,
    "max_response_length": 500,
    "personality_mode": "jarvis",  # jarvis | friendly | formal | brief
}

def get_config(key: str, default=None):
    return _runtime_config.get(key, os.getenv(key.upper(), default))

def set_config(key: str, value):
    _runtime_config[key] = value
    return f"Parameeter '{key}' muudetud: '{value}'."

def get_all_config() -> dict:
    return dict(_runtime_config)

# Käskluste tuvastamine vestlusest
SELF_MODIFY_PATTERNS = [
    # Hääle kiirus
    (r'говори (быстрее|скорее|faster)', lambda: set_config("voice_speed", 1.2)),
    (r'говори (медленнее|slower)', lambda: set_config("voice_speed", 0.8)),
    (r'нормальная скорость|normal speed', lambda: set_config("voice_speed", 0.95)),
    # Hääle stabiilsus
    (r'более роботизированный|more robotic', lambda: set_config("voice_stability", 0.95)),
    (r'более живой|more natural', lambda: set_config("voice_stability", 0.5)),
    # Primaarne AI
    (r'используй только claude|use only claude', lambda: set_config("primary_agent", "claude")),
    (r'используй только gpt|use only gpt', lambda: set_config("primary_agent", "gpt4o")),
    (r'используй все|use all', lambda: set_config("primary_agent", "all")),
    # Vastuse pikkus
    (r'отвечай короче|be brief|lühemalt', lambda: set_config("max_response_length", 200)),
    (r'отвечай подробнее|more detail|pikemalt', lambda: set_config("max_response_length", 1000)),
    # Isiksus
    (r'будь более формальным|be formal', lambda: set_config("personality_mode", "formal")),
    (r'будь дружелюбнее|be friendly', lambda: set_config("personality_mode", "friendly")),
    (r'режим джарвис|jarvis mode', lambda: set_config("personality_mode", "jarvis")),
]

def detect_and_apply(prompt: str) -> str | None:
    """Tuvastab enesemuutmise käskluse ja rakendab seda. Tagastab muutuse kirjelduse või None."""
    p = prompt.lower()
    for pattern, action in SELF_MODIFY_PATTERNS:
        if re.search(pattern, p, re.IGNORECASE):
            result = action()
            return result

    # Hääle ID muutmine
    m = re.search(r'измени голос на\s+([a-zA-Z0-9]+)', prompt, re.IGNORECASE)
    if m:
        new_voice = m.group(1)
        return set_config("voice_id", new_voice)

    return None
