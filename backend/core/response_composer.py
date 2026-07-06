"""
Albert OS — Response Composer
Spek: 27_AI_CORE_BIBLE.md

Vastutab:
  - Mitme mudeli vastuste ühendamine
  - Duplikaatide eemaldamine
  - Konflikti tuvastamine ja lahendamine
  - Tähtsa info säilitamine
  - Vahemälu (TTL-põhine, mälusisene)
"""
import hashlib
import re
import time
from difflib import SequenceMatcher

# ── Robotic filler removal ────────────────────────────────────────────────────
_FILLER_PATTERNS = [
    # Trailing address words (various positions)
    r',?\s*сэр\.?$', r',?\s*sir\.?$', r',?\s*härra\.?$',
    r',?\s*сэр\b', r',?\s*sir\b', r',?\s*härra\b',
    # Opening filler
    r'^(Конечно|Разумеется|Of course|Certainly|Muidugi|Loomulikult)[!,.]?\s*',
    r'^(Analysis complete[,.]\s*)', r'^(Noted[,.]\s*)',
    r'^(Хорошо|Понял|Understood)[,.]?\s*',
]
_FILLER_RE = [re.compile(p, re.IGNORECASE | re.MULTILINE) for p in _FILLER_PATTERNS]


def clean_response(text: str) -> str:
    """Strip robotic filler phrases and address words from a response."""
    if not text:
        return text
    for pattern in _FILLER_RE:
        text = pattern.sub('', text)
    text = text.strip().strip(',').strip()
    # Restore sentence-ending period if it was stripped with the address word
    if text and text[-1] not in '.!?':
        text += '.'
    return text

# ── Vastuste vahemälu (in-process, ei püsi taaskäivituse üle) ─────────────────
_cache: dict[str, tuple[str, float]] = {}  # key → (response, expires_at)
_CACHE_TTL = 120  # sekundit (2 minutit)
_CACHE_MAX = 200  # maksimaalne kirjete arv


def _cache_key(prompt: str, intent: str, provider: str) -> str:
    raw = f"{provider}::{intent}::{(prompt or '').strip()[:200]}"
    return hashlib.md5(raw.encode()).hexdigest()


def cache_get(prompt: str, intent: str, provider: str) -> str | None:
    """Tagastab vahemälus oleva vastuse või None."""
    key = _cache_key(prompt, intent, provider)
    entry = _cache.get(key)
    if entry and time.time() < entry[1]:
        return entry[0]
    if entry:
        del _cache[key]  # aegunud
    return None


def cache_set(prompt: str, intent: str, provider: str, response: str):
    """Salvestab vastuse vahemällu."""
    if not response:
        return
    # Puhasta vanu kandeid kui liiga palju
    if len(_cache) >= _CACHE_MAX:
        now = time.time()
        expired = [k for k, (_, exp) in _cache.items() if now > exp]
        for k in expired:
            del _cache[k]
        # Kui ikka liiga palju, kustuta vanim pool
        if len(_cache) >= _CACHE_MAX:
            keys = list(_cache.keys())
            for k in keys[: _CACHE_MAX // 2]:
                del _cache[k]
    key = _cache_key(prompt, intent, provider)
    _cache[key] = (response, time.time() + _CACHE_TTL)


def cache_clear():
    _cache.clear()


# ── Teksti sarnasuse mõõtmine ─────────────────────────────────────────────────
def _similarity(a: str, b: str) -> float:
    """0.0 – 1.0 vaheline sarnasusaste kahe tekstilõigu vahel."""
    if not a or not b:
        return 0.0
    return SequenceMatcher(None, a[:500], b[:500]).ratio()


# ── Konflikti tuvastamine ─────────────────────────────────────────────────────
_CONFLICT_PAIRS = [
    # (keyword_a, keyword_b) — viitavad vastandlikele väidetele
    ("toimib", "ei toimi"), ("works", "doesn't work"), ("работает", "не работает"),
    ("normaalne", "rike"), ("normal", "fault"), ("нормально", "неисправн"),
    ("jah", "ei"), ("yes", "no"), ("да", "нет"),
    ("safe", "dangerous"), ("ohutu", "ohtlik"), ("безопасно", "опасно"),
]


def detect_conflict(text_a: str, text_b: str) -> bool:
    """Lihtne heuristika — tagastab True kui vastused on vastuolulised."""
    a, b = (text_a or "").lower(), (text_b or "").lower()
    for kw_a, kw_b in _CONFLICT_PAIRS:
        if (kw_a in a and kw_b in b) or (kw_b in a and kw_a in b):
            return True
    return False


# ── Peamine ühendaja ──────────────────────────────────────────────────────────
def compose(primary: str | None, secondary: str | None,
            intent: str = "general", lang: str = "ru") -> str:
    """
    Ühendab kahe mudeli vastused üheks koherentse vastuseks.

    Loogika:
      1. Kui ainult primary — tagasta see.
      2. Kui ainult secondary — tagasta see.
      3. Kui mõlemad sarnased (>0.7) — tagasta primary (lühem/esimene).
      4. Kui vastukäivad — lisa hoiatus + mõlemad lühidalt.
      5. Kui täiendavad — ühenda: primary + secondary unikaalne info.
    """
    primary   = clean_response((primary   or "").strip())
    secondary = clean_response((secondary or "").strip())

    if not primary and not secondary:
        _no_response = {
            "ru": "Kõik süsteemid on kättesaamatud.",
            "et": "Kõik süsteemid on kättesaamatud.",
            "en": "All systems unavailable.",
        }
        return _no_response.get(lang, _no_response["ru"])

    if not secondary:
        return primary
    if not primary:
        return secondary

    sim = _similarity(primary, secondary)

    # Sarnased vastused — primary on piisav
    if sim > 0.72:
        return primary

    # Vastuolulised vastused
    if detect_conflict(primary, secondary):
        _conflict = {
            "ru": "⚠ Модели дают противоречивые ответы:",
            "et": "⚠ Mudelid annavad vastuolulisi vastuseid:",
            "en": "⚠ Models give conflicting answers:",
        }
        label_a = {"ru": "Первичный", "et": "Esmane", "en": "Primary"}.get(lang, "Primary")
        label_b = {"ru": "Вторичный", "et": "Teisene", "en": "Secondary"}.get(lang, "Secondary")
        return (
            f"{_conflict.get(lang, _conflict['en'])}\n"
            f"{label_a}: {primary[:300]}\n"
            f"{label_b}: {secondary[:300]}\n"
        )

    # Täiendavad vastused — ühenda
    # Leia secondary lõigud mis pole primary-s (>30 sõna ja sarnasus <0.5)
    secondary_sentences = [s.strip() for s in secondary.replace("\n", ". ").split(". ") if len(s.split()) > 5]
    unique_parts = [s for s in secondary_sentences
                    if _similarity(s, primary) < 0.5]

    if unique_parts:
        extra = ". ".join(unique_parts[:3])  # kuni 3 unikaalset lauset
        return f"{primary}\n\n{extra}"

    return primary


def compose_parallel_results(results: list[tuple[str | None, list]],
                              intent: str = "general",
                              lang: str = "ru") -> tuple[str, list]:
    """
    Ühendab asyncio.gather tulemuste nimekirja.
    results: [(text, ws_commands), ...]
    Tagastab: (composed_text, merged_ws_commands)
    """
    texts = [r[0] for r in results if r and not isinstance(r, Exception) and r[0]]
    ws_all = []
    for r in results:
        if r and not isinstance(r, Exception):
            ws_all.extend(r[1] or [])

    if not texts:
        return "", ws_all
    if len(texts) == 1:
        return texts[0], ws_all

    # Ühenda esimene ja teine
    composed = compose(texts[0], texts[1], intent=intent, lang=lang)
    # Kolmas+ — ainult kui oluliselt erinev
    for extra in texts[2:]:
        if extra and _similarity(extra, composed) < 0.5:
            composed = compose(composed, extra, intent=intent, lang=lang)

    return composed, ws_all
