"""
Albert OS — Vision Engine v2
Spek: 29_VISION_BIBLE.md

Pipeline:
  Camera/Image → Pre-processing → Scene Detection → Object Detection
  → OCR → Context Builder → Memory Retrieval → JarvisDirector
  → AI Provider(s) → Response Composer → AR Overlay (optional)

Standard response format (7 fields):
  1. What I see
  2. Confidence
  3. Why I think this
  4. Possible issues
  5. Recommended next step
  6. Safety notes
  7. Related documentation
"""
import re
import base64

# ── Visioonirežiimi tuvastamine ───────────────────────────────────────────────
VISION_MODE_KEYWORDS = {
    "bmw": ["bmw", "бмв", "двигател", "mootor", "engine", "sensor", "датчик",
            "разъём", "connector", "wiring", "шланг", "hose", "масло", "oil",
            "e46", "e90", "f10", "g30"],
    "boat": ["лодк", "boat", "paat", "marine", "мотор лодк", "outboard",
             "bilge", "electrical marine", "plumbing boat"],
    "construction": ["строительств", "ehitus", "construction", "инструмент",
                     "material", "installation", "concrete", "бетон", "cement"],
    "electronics": ["pcb", "плата", "connector", "разъём", "wiring",
                    "circuit", "схем", "transistor", "capacitor", "резистор"],
    "documents": ["document", "текст", "text", "dokument", "договор", "счёт",
                  "invoice", "letter", "письмо", "page", "страниц"],
}

def detect_vision_mode(prompt: str, memory_ctx: str = "") -> str:
    """Tuvastab visioonirežiimi prompt'i ja mälu konteksti põhjal."""
    combined = (prompt + " " + memory_ctx).lower()
    for mode, keywords in VISION_MODE_KEYWORDS.items():
        if any(kw in combined for kw in keywords):
            return mode
    return "general"

# ── Režiimispetsiifilised süsteemi juhised ────────────────────────────────────
# Standard 7-field format (spek: 29_VISION_BIBLE.md)
_FMT = """Respond in this exact 7-field format:
1. ВИЖУ: [what you see]
2. УВЕРЕННОСТЬ: [High / Medium / Low]
3. ПОЧЕМУ: [key visual signals that led to this conclusion]
4. ПРОБЛЕМЫ: [possible issues or faults — or 'None']
5. СЛЕДУЮЩИЙ ШАГ: [one concrete recommended action]
6. БЕЗОПАСНОСТЬ: [safety warnings — or 'None']
7. ДОКУМЕНТАЦИЯ: [relevant manual, part number, datasheet, or standard — or 'None']"""

VISION_MODE_PROMPTS = {
    "general": f"""Analyze this image as a knowledgeable engineering assistant.
{_FMT}""",

    "bmw": f"""You are analyzing a BMW vehicle component.
Recognize: engines, sensors, connectors, wiring harnesses, ECUs, hoses, bolts, fault indicators.
Output includes: probable fault, confidence, repair steps, required tools, manuals.
{_FMT}
For field 7: cite BMW ISTA reference, ETK part number, or WIS document if known.""",

    "boat": f"""You are analyzing a marine / boat component.
Recognize: engines, cooling systems, fuel systems, NMEA equipment, electrical systems, plumbing.
{_FMT}
For field 7: cite engine service manual, NMEA standard, or supplier reference if known.""",

    "construction": f"""You are analyzing a construction site, tools, materials or installation.
Recognize: structural elements, materials, tools, plumbing, electrical installations.
{_FMT}
For field 7: cite building code, standard (EN/ISO) or material spec if applicable.""",

    "electronics": f"""You are analyzing electronic components, PCB, connectors or wiring.
Recognize: PCBs, ICs, capacitors, relays, connectors, polarity markers, damaged components.
{_FMT}
For field 7: cite IC datasheet, connector standard, or board revision if visible.""",

    "documents": f"""You are performing OCR and document analysis.
Support: text extraction, translation hints, table extraction, part number extraction, summarization.
{_FMT}
For field 7: N/A (the document IS the reference).
After the 7 fields add:
ТЕКСТ: [full extracted text, preserve structure]
АРТИКУЛ: [any part numbers, order codes or serial numbers found — comma separated, or 'None']""",
}

def get_vision_system_prompt(mode: str, base_system: str) -> str:
    """Kombineerib JARVIS isiksuse + visioonirežiimi juhised."""
    vision_instruction = VISION_MODE_PROMPTS.get(mode, VISION_MODE_PROMPTS["general"])
    return f"{base_system}\n\nVISION MODE: {mode.upper()}\n{vision_instruction}"


# ── Pre-processing ────────────────────────────────────────────────────────────
def preprocess_image(image_b64: str) -> dict:
    """
    Lihtne eeltöötlus enne AI-le saatmist.
    Tagastab metaandmed: suurus, formaat, kvaliteedihoiatus.
    Päris suurendamine/teritamine nõuab Pillow — see on lihtne validaator.
    """
    if not image_b64:
        return {"ok": False, "reason": "empty"}
    try:
        data = base64.b64decode(image_b64)
        size_kb = len(data) / 1024
        # Väga väike pilt — kvaliteet kahtlane
        if size_kb < 5:
            return {"ok": True, "size_kb": size_kb, "warning": "very_small_image"}
        # Väga suur — saata ikkagi, AI toetab kuni ~20MB
        if size_kb > 15_000:
            return {"ok": False, "size_kb": size_kb, "reason": "image_too_large"}
        return {"ok": True, "size_kb": round(size_kb, 1)}
    except Exception as e:
        return {"ok": False, "reason": str(e)}


# ── Projekti salvestamine (Project Brain nimed) ───────────────────────────────
# project_name peab ühtima init_project_brain() nimedega (memory/memory.py)
_MODE_TO_PROJECT = {
    "bmw":          ("BMW",   "diagnosis"),
    "boat":         ("Paat",  "maintenance"),
    "construction": ("Kood",  "note"),      # ehitusprojekt → Kood alla kuni eraldi projekt
    "electronics":  ("Kood",  "note"),
    "documents":    (None,     None),        # dokumendid projekti pole → ainult notes
}

def should_save_to_project(mode: str, response: str) -> tuple[str | None, str | None]:
    """
    Otsustab kas visioonivastus tuleks projekti mällu salvestada.
    Tagastab (project_name, entry_type) või (None, None).
    Projekti nimed vastavad Project Brain nimedele (28_MEMORY_BIBLE.md).
    """
    return _MODE_TO_PROJECT.get(mode, (None, None))
