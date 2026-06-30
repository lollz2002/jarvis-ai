import os
from google import genai
from agents.personality import JARVIS_SYSTEM

_client = None

def get_client():
    global _client
    if _client is None:
        _client = genai.Client(api_key=os.getenv("GEMINI_API_KEY", ""))
    return _client

async def analyze(image_b64: str = None, mime: str = "image/jpeg", prompt: str = "", mode: str = "default") -> str:
    client = get_client()
    parts = []

    if image_b64:
        import base64
        parts.append({"inline_data": {"mime_type": mime, "data": image_b64}})

    user_prompt = prompt or _default_prompt(mode)

    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=user_prompt if not parts else [*parts, user_prompt],
        config={"system_instruction": JARVIS_SYSTEM, "temperature": 1, "max_output_tokens": 1024}
    )
    return response.text

def _default_prompt(mode: str) -> str:
    return {
        "analyze": "Проанализируй изображение, сэр ожидает краткого отчёта.",
        "identify": "Идентифицируй объекты на изображении.",
        "translate": "Найди текст на изображении и переведи его на русский язык.",
        "default": "Готов к вашим командам, сэр.",
    }.get(mode, "Готов к вашим командам, сэр.")
