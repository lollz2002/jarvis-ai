"""
Perplexity AI — internet research agent.
Kasuta päringute jaoks mis vajavad värsket infot internetist.
"""
import os
import httpx
from agents.personality import JARVIS_SYSTEM

API_KEY = os.getenv("PERPLEXITY_API_KEY", "")

async def analyze(prompt: str, image_b64: str = None) -> dict:
    if not API_KEY:
        return {"id": "perplexity", "name": "Perplexity", "response": None, "error": "No API key"}
    try:
        async with httpx.AsyncClient(timeout=20) as client:
            resp = await client.post(
                "https://api.perplexity.ai/chat/completions",
                headers={"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"},
                json={
                    "model": "llama-3.1-sonar-large-128k-online",
                    "messages": [
                        {"role": "system", "content": JARVIS_SYSTEM},
                        {"role": "user", "content": prompt}
                    ],
                    "max_tokens": 400,
                    "temperature": 0.2,
                    "return_citations": True,
                }
            )
        if resp.status_code == 200:
            data = resp.json()
            text = data["choices"][0]["message"]["content"]
            citations = data.get("citations", [])
            if citations:
                text += "\n[Источники: " + ", ".join(citations[:3]) + "]"
            return {"id": "perplexity", "name": "Perplexity", "response": text, "error": None}
        return {"id": "perplexity", "name": "Perplexity", "response": None, "error": f"HTTP {resp.status_code}"}
    except Exception as e:
        return {"id": "perplexity", "name": "Perplexity", "response": None, "error": str(e)}
