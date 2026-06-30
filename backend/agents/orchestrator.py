import asyncio
import os
from agents import claude_agent, openai_agent, gemini_agent

AGENTS = [
    {"id": "claude", "name": "Claude", "fn": claude_agent.analyze, "key": "ANTHROPIC_API_KEY"},
    {"id": "gpt4o", "name": "GPT-4o", "fn": openai_agent.analyze, "key": "OPENAI_API_KEY"},
    {"id": "gemini", "name": "Gemini", "fn": gemini_agent.analyze, "key": "GEMINI_API_KEY"},
]

async def run_all(image_b64=None, mime="image/jpeg", prompt="", mode="default", agents=None):
    active = [a for a in AGENTS if os.getenv(a["key"]) and (agents is None or a["id"] in agents)]

    async def run_one(agent):
        start = asyncio.get_event_loop().time()
        try:
            response = await agent["fn"](image_b64=image_b64, mime=mime, prompt=prompt, mode=mode)
            return {"id": agent["id"], "name": agent["name"], "response": response,
                    "ms": int((asyncio.get_event_loop().time() - start) * 1000), "error": None}
        except Exception as e:
            return {"id": agent["id"], "name": agent["name"], "response": None,
                    "ms": None, "error": str(e)}

    results = await asyncio.gather(*[run_one(a) for a in active])
    return list(results)

def get_agent_list():
    return [{"id": a["id"], "name": a["name"], "enabled": bool(os.getenv(a["key"]))} for a in AGENTS]
