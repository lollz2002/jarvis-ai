import os
import httpx

async def text_to_speech(text: str) -> bytes | None:
    key = os.getenv("ELEVENLABS_API_KEY", "")
    voice_id = os.getenv("ELEVENLABS_VOICE_ID", "pNInz6obpgDQGcFmaJgB")
    if not key or not text:
        return None
    # Lühenda tekst (ElevenLabs max ~5000 tähemärki)
    text = text[:1000]
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(
                f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}",
                headers={"xi-api-key": key, "Content-Type": "application/json"},
                json={"text": text, "model_id": "eleven_multilingual_v2",
                      "voice_settings": {"stability": 0.5, "similarity_boost": 0.75}}
            )
            if resp.status_code == 200:
                return resp.content
            return None
    except Exception:
        return None
