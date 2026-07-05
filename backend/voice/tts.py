import os
import httpx

async def text_to_speech(text: str) -> bytes | None:
    if not text:
        return None

    try:
        from core.tools import get_cfg
        engine = get_cfg("voice_engine", "openai")
        speed = get_cfg("voice_speed", 0.95)
        voice_id = get_cfg("voice_id", "onyx")
    except Exception:
        engine, speed, voice_id = "openai", 0.95, "onyx"

    text = text[:500]

    if engine == "openai":
        openai_key = os.getenv("OPENAI_API_KEY", "")
        if openai_key:
            result = await _openai_tts(text, openai_key, voice=voice_id, speed=speed)
            if result:
                return result

    # Fallback: ElevenLabs
    el_key = os.getenv("ELEVENLABS_API_KEY", "")
    voice_id = os.getenv("ELEVENLABS_VOICE_ID", "pNInz6obpgDQGcFmaJgB")
    if el_key:
        return await _elevenlabs_tts(text, el_key, voice_id)

    return None

async def _openai_tts(text: str, key: str, voice: str = "onyx", speed: float = 0.95) -> bytes | None:
    # Veendu et hääl on kehtiv OpenAI hääl
    valid_voices = {"onyx", "alloy", "echo", "fable", "nova", "shimmer"}
    if voice not in valid_voices:
        voice = "onyx"
    try:
        async with httpx.AsyncClient(timeout=20) as client:
            resp = await client.post(
                "https://api.openai.com/v1/audio/speech",
                headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
                json={"model": "tts-1", "input": text, "voice": voice, "speed": speed}
            )
            if resp.status_code == 200:
                return resp.content
    except Exception:
        pass
    return None

async def _elevenlabs_tts(text: str, key: str, voice_id: str) -> bytes | None:
    try:
        async with httpx.AsyncClient(timeout=20) as client:
            resp = await client.post(
                f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}/stream",
                headers={"xi-api-key": key, "Content-Type": "application/json"},
                json={
                    "text": text,
                    "model_id": "eleven_flash_v2_5",
                    "voice_settings": {"stability": 0.75, "similarity_boost": 0.85,
                                       "style": 0.2, "use_speaker_boost": True, "speed": 0.95}
                }
            )
            if resp.status_code == 200:
                return resp.content
    except Exception:
        pass
    return None
