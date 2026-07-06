import asyncio
import os
import re
from agents import claude_agent, openai_agent, gemini_agent
from agents.director import run_with_tools
from memory.memory import get_context_for_prompt, save_fact

AGENTS = {
    "gpt4o":  {"name": "GPT-4o",  "fn": openai_agent.analyze,  "key": "OPENAI_API_KEY"},
    "claude": {"name": "Claude",  "fn": claude_agent.analyze,   "key": "ANTHROPIC_API_KEY"},
    "gemini": {"name": "Gemini",  "fn": gemini_agent.analyze,   "key": "GEMINI_API_KEY"},
}

def _extract_facts(prompt: str):
    m = re.search(r'меня зовут ([А-ЯЁA-Za-z][а-яёa-z]+)', prompt, re.IGNORECASE)
    if m: save_fact("user_name", m.group(1))
    m = re.search(r'minu nimi on (\w+)', prompt, re.IGNORECASE)
    if m: save_fact("user_name", m.group(1))
    m = re.search(r'я живу в ([А-ЯЁ][а-яё]+)', prompt, re.IGNORECASE)
    if m: save_fact("user_city", m.group(1))

async def run_smart(image_b64=None, mime="image/jpeg", prompt="", mode="default", model_hint=None):
    memory_ctx = get_context_for_prompt(prompt)  # prompt → aktiivse projekti tuvastus
    _extract_facts(prompt)

    # Direktor käivitab tööriistu + vastab
    response_text, ws_commands = await run_with_tools(
        prompt=prompt or _default_prompt(mode),
        image_b64=image_b64,
        memory_ctx=memory_ctx,
        model_hint=model_hint,
    )

    result = {
        "id": "jarvis", "name": "JARVIS", "response": response_text,
        "ms": None, "error": None, "ws_commands": ws_commands
    }
    return [result], ws_commands

async def run_all(image_b64=None, mime="image/jpeg", prompt="", mode="default", agents=None):
    results, _ = await run_smart(image_b64=image_b64, mime=mime, prompt=prompt, mode=mode)
    return results

async def run_primary(image_b64=None, mime="image/jpeg", prompt="", mode="default", model_hint=None):
    results, ws_commands = await run_smart(image_b64=image_b64, mime=mime, prompt=prompt, mode=mode, model_hint=model_hint)
    primary = results[0] if results else None
    if primary:
        primary["_ws_commands"] = ws_commands
    return primary

def get_agent_list():
    return [{"id": "jarvis", "name": "JARVIS Director", "enabled": True, "primary": True}] + [
        {"id": aid, "name": a["name"], "enabled": bool(os.getenv(a["key"])), "primary": False}
        for aid, a in AGENTS.items()
    ]

def _default_prompt(mode: str) -> str:
    return {
        "analyze": "Analüüsi pilti ja anna lühike aruanne.",
        "identify": "Идентифицируй объекты на изображении.",
        "translate": "Найди текст на изображении и переведи его на русский язык.",
        "default": "Valmis käskude täitmiseks.",
    }.get(mode, "Готов к вашим командам, сэр.")
