"""
Albert OS — Vision Engine
Spek: 06_VISION_ENGINE.md

Pipeline: capture → enhance → detect scene → OCR → memory → AI → response → save
"""
import re

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
VISION_MODE_PROMPTS = {
    "general": """Analyze this image and respond in this exact format:
1. ВИЖУ: [what you see, briefly]
2. УВЕРЕННОСТЬ: [High/Medium/Low]
3. ПОЧЕМУ: [reasoning]
4. СЛЕДУЮЩИЙ ШАГ: [practical recommendation]
5. БЕЗОПАСНОСТЬ: [any safety notes, or 'None']
6. ДОКУМЕНТАЦИЯ: [relevant manual/reference, or 'None']""",

    "bmw": """You are analyzing a BMW vehicle component. Identify engine parts, sensors, connectors, wiring, hoses.
Respond in this exact format:
1. ВИЖУ: [component name and location]
2. УВЕРЕННОСТЬ: [High/Medium/Low]
3. ПОЧЕМУ: [identifying features]
4. СЛЕДУЮЩИЙ ШАГ: [repair suggestion or diagnostic step]
5. БЕЗОПАСНОСТЬ: [safety warnings if applicable]
6. ДОКУМЕНТАЦИЯ: [BMW repair manual reference or ETK part number if known]""",

    "boat": """You are analyzing a marine/boat component. Identify engine, electrical, plumbing components.
Respond in this exact format:
1. ВИЖУ: [component and condition]
2. УВЕРЕННОСТЬ: [High/Medium/Low]
3. ПОЧЕМУ: [identifying features]
4. СЛЕДУЮЩИЙ ШАГ: [maintenance or repair recommendation]
5. БЕЗОПАСНОСТЬ: [marine safety notes]
6. ДОКУМЕНТАЦИЯ: [service manual reference if known]""",

    "construction": """You are analyzing a construction site, tools, or materials.
Respond in this exact format:
1. ВИЖУ: [tool/material/installation]
2. УВЕРЕННОСТЬ: [High/Medium/Low]
3. ПОЧЕМУ: [identifying features]
4. СЛЕДУЮЩИЙ ШАГ: [practical recommendation]
5. БЕЗОПАСНОСТЬ: [construction safety notes]
6. ДОКУМЕНТАЦИЯ: [building code or standard if applicable]""",

    "electronics": """You are analyzing electronic components, PCB, connectors, or wiring.
Respond in this exact format:
1. ВИЖУ: [component type and condition]
2. УВЕРЕННОСТЬ: [High/Medium/Low]
3. ПОЧЕМУ: [identifying features — markings, layout, pins]
4. СЛЕДУЮЩИЙ ШАГ: [repair or measurement recommendation]
5. БЕЗОПАСНОСТЬ: [electrical safety notes]
6. ДОКУМЕНТАЦИЯ: [datasheet or standard if known]""",

    "documents": """You are performing OCR and document analysis.
Respond in this exact format:
1. ВИЖУ: [document type and content summary]
2. УВЕРЕННОСТЬ: [High/Medium/Low for OCR accuracy]
3. ПОЧЕМУ: [document structure clues]
4. СЛЕДУЮЩИЙ ШАГ: [suggested action — sign, translate, file, review]
5. БЕЗОПАСНОСТЬ: [privacy notes if sensitive info detected]
6. ДОКУМЕНТАЦИЯ: [N/A]
Also provide: ТЕКСТ: [full extracted text if readable]""",
}

def get_vision_system_prompt(mode: str, base_system: str) -> str:
    """Kombineerib JARVIS isiksuse + visioonirežiimi juhised."""
    vision_instruction = VISION_MODE_PROMPTS.get(mode, VISION_MODE_PROMPTS["general"])
    return f"{base_system}\n\nVISION MODE: {mode.upper()}\n{vision_instruction}"

def should_save_to_project(mode: str, response: str) -> tuple[str | None, str | None]:
    """
    Otsustab kas visioonivastus tuleks projekti mällu salvestada.
    Tagastab (project_name, entry_type) või (None, None).
    """
    if mode == "bmw":
        return "BMW", "note"
    if mode == "boat":
        return "Boat", "maintenance"
    if mode == "construction":
        return "Construction", "note"
    return None, None
