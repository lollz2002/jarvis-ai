"""
Albert OS — JarvisDirector v2
Spek: 04_JARVIS_DIRECTOR.md

Pipeline:
  1. Keele tuvastus
  2. Intent klassifitseerimine (10 klassi)
  3. Mälu laadimine
  4. Provider valimine (routing_config.py kaudu)
  5. Paralleelne täitmine kui kasulik
  6. Confidence hinnang
  7. Vastuse valideerimine / teise provideriga kontroll
  8. Lõplik koherentsete vastus
"""
import os
import re
import json
import asyncio
import httpx
from agents.personality import JARVIS_SYSTEM, build_system
from core.monitor import audit
from core.tools import TOOLS, execute_tool, get_cfg
from core.routing_config import INTENT_PATTERNS, PROVIDERS, ROUTING, FALLBACK_CHAIN
from core.planner import is_complex_request, build_plan, format_plan_for_prompt
from core.response_composer import (
    compose_parallel_results, compose,
    cache_get, cache_set,
)
from core.events import emit_sync, USER_REQUEST_RECEIVED, PROVIDER_SELECTED, RESPONSE_COMPOSED
from engines.vision_engine import detect_vision_mode, get_vision_system_prompt, should_save_to_project, preprocess_image

OPENAI_URL = "https://api.openai.com/v1/chat/completions"

# ── 1. Keele tuvastus ─────────────────────────────────────────────────────────
def detect_language(text: str) -> str:
    if not text: return "ru"
    et = sum(1 for w in ["kas", "ma", "ta", "on", "ei", "ja", "see", "mis", "mida", "kuidas", "ava", "sulge", "tee"] if w in text.lower().split())
    en = sum(1 for w in ["the", "is", "are", "what", "how", "can", "open", "close", "find", "show", "make"] if w in text.lower().split())
    ru = sum(1 for ch in text if 'Ѐ' <= ch <= 'ӿ')
    if et >= 2: return "et"
    if en >= 2: return "en"
    if ru >= 3: return "ru"
    return "ru"

# ── 2. Intent klassifitseerimine ──────────────────────────────────────────────
# Prioriteetne järjestus: spetsiifilisemad intentid enne üldisemaid
_INTENT_PRIORITY = [
    "bmw_diagnostics", "boat_diagnostics", "construction",
    "vision", "coding", "research", "translation", "planning",
    "business", "calendar", "device_control", "diagnostics",
]

def classify_intent(prompt: str, has_image: bool) -> str:
    if has_image:
        return "vision"
    p = prompt.lower()
    for intent in _INTENT_PRIORITY:
        patterns = INTENT_PATTERNS.get(intent, [])
        if patterns and any(pat in p for pat in patterns):
            return intent
    return "general"

# ── 3. Aktiivse projekti tuvastus ─────────────────────────────────────────────
_PROJECT_KEYWORDS = {
    "bmw":          ["bmw", "бмв", "bmw rike", "bmw viga", "bmw mootor"],
    "boat":         ["paat", "jaht", "лодк", "яхт", "катер", "boat"],
    "construction": ["ehitus", "remont", "строительств", "ремонт"],
}

def detect_active_project(prompt: str) -> str | None:
    """Tuvastab aktiivse projekti märksõnade järgi. Tagastab projekti nime või None."""
    p = prompt.lower()
    for project, keywords in _PROJECT_KEYWORDS.items():
        if any(kw in p for kw in keywords):
            return project
    return None

# ── 4. Confidence hinnang ─────────────────────────────────────────────────────
_UNCERTAIN_MARKERS = [
    "не уверен", "возможно", "наверное", "might", "perhaps",
    "could be", "võib-olla", "arvatavasti", "не знаю", "unclear",
    "uncertain", "assuming", "i think", "я думаю", "скорее всего",
]

def estimate_confidence(response: str, intent: str) -> str:
    if not response or len(response) < 20:
        return "low"
    if any(m in response.lower() for m in _UNCERTAIN_MARKERS):
        return "medium"
    if intent in ("research", "diagnostics", "bmw_diagnostics", "boat_diagnostics") and len(response) > 100:
        return "high"
    return "high"

def apply_confidence_label(text: str, confidence: str, lang: str) -> str:
    """Medium confidence: lisa eelduse märgend vastuse ette."""
    if confidence != "medium":
        return text
    prefix = {"ru": "Предположительно: ", "et": "Eeldatavasti: ", "en": "Assuming: "}.get(lang, "Assuming: ")
    return prefix + text

# ── Provideri API kutsed ──────────────────────────────────────────────────────
async def _call_openai(prompt, image_b64, system, key, model="gpt-4o", use_tools=True) -> tuple[str | None, list]:
    content = []
    if image_b64:
        content.append({"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{image_b64}"}})
    content.append({"type": "text", "text": prompt or "Анализируй изображение."})
    messages = [
        {"role": "system", "content": system},
        {"role": "user", "content": content if image_b64 else prompt}
    ]
    ws_commands = []
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            body = {"model": model, "max_tokens": get_cfg("max_tokens", 300), "messages": messages}
            if use_tools: body.update({"tools": TOOLS, "tool_choice": "auto"})
            resp = await client.post(OPENAI_URL,
                headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"}, json=body)
            if resp.status_code != 200: return None, []
            msg = resp.json()["choices"][0]["message"]
            if use_tools and msg.get("tool_calls"):
                messages.append(msg)
                for tc in msg["tool_calls"]:
                    fn_name = tc["function"]["name"]
                    fn_args = json.loads(tc["function"]["arguments"])
                    result_text, ws_cmd = execute_tool(fn_name, fn_args)
                    if ws_cmd: ws_commands.append(ws_cmd)
                    messages.append({"role": "tool", "tool_call_id": tc["id"], "content": result_text})
                resp2 = await client.post(OPENAI_URL,
                    headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
                    json={"model": "gpt-4o-mini", "max_tokens": get_cfg("max_tokens", 300), "messages": messages})
                if resp2.status_code == 200:
                    return resp2.json()["choices"][0]["message"]["content"], ws_commands
            return msg.get("content"), ws_commands
    except Exception:
        return None, []

async def _call_claude(prompt, image_b64, system, key, model="claude-sonnet-4-6") -> str | None:
    content = []
    if image_b64:
        content.append({"type": "image", "source": {"type": "base64", "media_type": "image/jpeg", "data": image_b64}})
    content.append({"type": "text", "text": prompt or "Анализируй изображение."})
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post("https://api.anthropic.com/v1/messages",
                headers={"x-api-key": key, "anthropic-version": "2023-06-01", "content-type": "application/json"},
                json={"model": model, "max_tokens": get_cfg("max_tokens", 300),
                      "system": system, "messages": [{"role": "user", "content": content}]})
            if resp.status_code == 200: return resp.json()["content"][0]["text"]
    except Exception: pass
    return None

async def _call_gemini(prompt, image_b64, key, model="gemini-2.5-flash") -> str | None:
    try:
        from google import genai
        from google.genai import types
        client = genai.Client(api_key=key)
        parts = []
        if image_b64:
            import base64
            parts.append(types.Part.from_bytes(data=base64.b64decode(image_b64), mime_type="image/jpeg"))
        parts.append(types.Part.from_text(text=prompt or "Анализируй изображение."))
        resp = await asyncio.to_thread(
            client.models.generate_content,
            model=model,
            contents=types.Content(parts=parts, role="user"),
            config=types.GenerateContentConfig(
                system_instruction=JARVIS_SYSTEM,
                max_output_tokens=get_cfg("max_tokens", 300)
            )
        )
        return resp.text
    except Exception:
        return None

async def _call_perplexity(prompt, system, key, model="llama-3.1-sonar-large-128k-online") -> str | None:
    try:
        async with httpx.AsyncClient(timeout=20) as client:
            resp = await client.post(
                "https://api.perplexity.ai/chat/completions",
                headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
                json={"model": model,
                      "messages": [{"role": "system", "content": system}, {"role": "user", "content": prompt}],
                      "max_tokens": 400, "temperature": 0.2, "return_citations": True})
            if resp.status_code == 200:
                data = resp.json()
                text = data["choices"][0]["message"]["content"]
                citations = data.get("citations", [])
                if citations: text += f"\n[{', '.join(citations[:2])}]"
                return text
    except Exception: pass
    return None

async def _call_provider(provider: str, prompt: str, image_b64: str, system: str) -> tuple[str | None, list]:
    """Kutsub õige provideri API-t."""
    cfg = PROVIDERS.get(provider, {})
    key = os.getenv(cfg.get("env_key", ""), "")
    if not key: return None, []
    model = cfg["models"]["smart"]
    ws = []
    if provider == "openai":
        text, ws = await _call_openai(prompt, image_b64, system, key, model)
    elif provider == "claude":
        text = await _call_claude(prompt, image_b64, system, key, model)
    elif provider == "gemini":
        text = await _call_gemini(prompt, image_b64, key, model)
    elif provider == "perplexity":
        text = await _call_perplexity(prompt, system, key, model)
    else:
        text = None
    return text, ws

# ── Peamine Director ───────────────────────────────────────────────────────────
async def run_with_tools(prompt: str, image_b64: str = None, memory_ctx: str = "") -> tuple[str, list]:
    lang   = detect_language(prompt or "")
    intent = classify_intent(prompt or "", bool(image_b64))
    active_project = detect_active_project(prompt or "")
    routing = ROUTING.get(intent, ROUTING["general"])

    emit_sync(USER_REQUEST_RECEIVED, {
        "intent": intent, "lang": lang,
        "has_image": bool(image_b64), "active_project": active_project,
        "prompt_len": len(prompt or ""),
    })

    # ── Vahemälu kontroll (tekstipäringud, mitte pildid) ──────────────────────
    if not image_b64:
        primary_provider = routing["primary"]
        cached = cache_get(prompt or "", intent, primary_provider)
        if cached:
            return cached, []

    # ── Pildi eeltöötlus ─────────────────────────────────────────────────────
    if image_b64:
        pre = preprocess_image(image_b64)
        if not pre.get("ok"):
            return f"Pildi töötlemine ebaõnnestus: {pre.get('reason', 'unknown')}", []
        if pre.get("warning") == "very_small_image":
            prompt = (prompt or "") + " [Note: image is very small, quality may be low]"

    # Vision Engine — spetsialiseeritud režiim piltide jaoks
    if intent == "vision":
        vision_mode = detect_vision_mode(prompt or "", memory_ctx)
        base_system = get_vision_system_prompt(vision_mode, JARVIS_SYSTEM)
        system = build_system(mode=None, memory_ctx=memory_ctx, lang=lang, intent=intent)
        system = base_system + "\n\n" + system  # vision prompt ette
    else:
        # Intent → isiksuse moodul kaart
        mode_map = {
            "coding":           "coding",
            "bmw_diagnostics":  "automotive",
            "boat_diagnostics": "marine",
            "construction":     "coding",   # tehniline režiim
            "diagnostics":      "automotive",
            "research":         "research",
            "business":         "business",
        }
        personality_mode = mode_map.get(intent)
        system = build_system(mode=personality_mode, memory_ctx=memory_ctx, lang=lang, intent=intent)

    # ── Planner — keeruliste päringute sammude lisamine prompti ───────────────
    if is_complex_request(prompt or "", intent):
        steps = build_plan(prompt or "", intent)
        system += "\n\n" + format_plan_for_prompt(steps)

    ws_commands = []
    primary = routing["primary"]
    verify_with = routing["verify_with"]
    run_parallel = routing.get("parallel", False) and verify_with

    emit_sync(PROVIDER_SELECTED, {"primary": primary, "verify_with": verify_with, "parallel": run_parallel, "intent": intent})

    # ── Paralleelne täitmine + Response Composer ─────────────────────────────
    if run_parallel and verify_with:
        raw_results = await asyncio.gather(
            _call_provider(primary, prompt, image_b64, system),
            _call_provider(verify_with, prompt, image_b64, system),
            return_exceptions=True
        )
        text, ws = compose_parallel_results(raw_results, intent=intent, lang=lang)
        ws_commands.extend(ws)
    else:
        text, ws = await _call_provider(primary, prompt, image_b64, system)
        ws_commands.extend(ws)

    # ── Fallback kui primary kukus ────────────────────────────────────────────
    if not text:
        for fallback in FALLBACK_CHAIN:
            if fallback == primary: continue
            text, ws = await _call_provider(fallback, prompt, image_b64, system)
            ws_commands.extend(ws)
            if text: break

    # ── Confidence strateegia ─────────────────────────────────────────────────
    if text:
        confidence = estimate_confidence(text, intent)
        if confidence == "low" and verify_with and not run_parallel:
            # Madal kindlus: küsi teiselt providerilt
            verify_text, _ = await _call_provider(verify_with, prompt, image_b64, system)
            if verify_text:
                text = verify_text
                confidence = estimate_confidence(text, intent)
        # Keskmine kindlus: lisa eelduse märgend
        text = apply_confidence_label(text, confidence, lang)
    else:
        confidence = "low"

    # ── Mälu uuendus — salvesta projekti mällu pärast vastust ─────────────────
    if text:
        try:
            from memory.memory import add_project_entry
            if intent == "vision":
                proj, entry_type = should_save_to_project(
                    vision_mode if intent == "vision" else "general", text)
                if proj and entry_type:
                    add_project_entry(proj, entry_type,
                                      f"[Vision] {(prompt or '')[:60]} → {text[:200]}")
            elif active_project and intent in (
                "bmw_diagnostics", "boat_diagnostics", "construction", "diagnostics"
            ):
                # Salvesta diagnostika tulemus aktiivse projekti alla
                add_project_entry(active_project, "diagnosis",
                                  f"[{intent}] {(prompt or '')[:80]} → {text[:300]}")
        except Exception:
            pass

    # Vahemällu salvestamine (ainult kõrge/keskmise kindlusega tekstivastused)
    if text and not image_b64 and confidence in ("high", "medium"):
        cache_set(prompt or "", intent, primary, text)

    audit("director_response", {
        "intent": intent, "provider": primary,
        "has_text": bool(text), "confidence": confidence,
        "active_project": active_project, "lang": lang,
    })
    emit_sync(RESPONSE_COMPOSED, {
        "intent": intent, "provider": primary, "confidence": confidence,
        "response_len": len(text or ""), "lang": lang,
    })
    return text or "Все системы недоступны, сэр.", ws_commands


async def decide_routing(prompt: str, has_image: bool) -> dict:
    intent         = classify_intent(prompt, has_image)
    lang           = detect_language(prompt)
    active_project = detect_active_project(prompt)
    routing        = ROUTING.get(intent, ROUTING["general"])
    return {
        "intent":           intent,
        "language":         lang,
        "active_project":   active_project,
        "primary_provider": routing["primary"],
        "verify_with":      routing["verify_with"],
        "parallel":         routing.get("parallel", False),
    }


async def synthesize(prompt: str, results: list, memory_ctx: str = "") -> str:
    valid = [r for r in results if r.get("response")]
    return valid[0]["response"] if valid else "Системы недоступны, сэр."
