import anthropic
import os
from agents.personality import JARVIS_SYSTEM

client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

async def analyze(image_b64: str = None, mime: str = "image/jpeg", prompt: str = "", mode: str = "default") -> str:
    content = []
    if image_b64:
        content.append({"type": "image", "source": {"type": "base64", "media_type": mime, "data": image_b64}})

    user_prompt = prompt or _default_prompt(mode)
    content.append({"type": "text", "text": user_prompt})

    resp = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=1024,
        system=JARVIS_SYSTEM,
        messages=[{"role": "user", "content": content}]
    )
    return resp.content[0].text

def _default_prompt(mode: str) -> str:
    return {
        "analyze": "Проанализируй изображение, сэр ожидает краткого отчёта.",
        "identify": "Идентифицируй объекты на изображении.",
        "translate": "Найди текст на изображении и переведи его на русский язык.",
        "default": "Готов к вашим командам, сэр.",
    }.get(mode, "Готов к вашим командам, сэр.")
