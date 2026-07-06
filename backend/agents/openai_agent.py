from openai import AsyncOpenAI
import os
from agents.personality import JARVIS_SYSTEM

_client = None

def get_client():
    global _client
    if _client is None:
        _client = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY", ""))
    return _client

async def analyze(image_b64: str = None, mime: str = "image/jpeg", prompt: str = "", mode: str = "default") -> str:
    content = []
    if image_b64:
        content.append({"type": "image_url", "image_url": {"url": f"data:{mime};base64,{image_b64}"}})

    user_prompt = prompt or _default_prompt(mode)
    content.append({"type": "text", "text": user_prompt})

    resp = await get_client().chat.completions.create(
        model="gpt-4o-mini",
        max_tokens=300,
        messages=[
            {"role": "system", "content": JARVIS_SYSTEM},
            {"role": "user", "content": content}
        ]
    )
    return resp.choices[0].message.content

def _default_prompt(mode: str) -> str:
    return {
        "analyze": "Analüüsi pilti ja anna lühike aruanne.",
        "identify": "Идентифицируй объекты на изображении.",
        "translate": "Найди текст на изображении и переведи его на русский язык.",
        "default": "Valmis käskude täitmiseks.",
    }.get(mode, "Готов к вашим командам, сэр.")
