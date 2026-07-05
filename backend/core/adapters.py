"""
Albert OS — Provider Adapter Layer
Spek: 12_API_AND_INTEGRATION_BIBLE.md, 33_PROVIDER_SDK_BIBLE.md

Iga adapter implementeerib BaseAdapter täieliku Provider Contract'iga:
  initialize(), health_check(), chat(), stream_chat(), vision(),
  embeddings(), speech_to_text(), text_to_speech(), list_models()

Äriloogika ei tohi sõltuda konkreetsest providerist — kasuta ainult seda kihti.
"""
import os
import time
import asyncio
import httpx
from abc import ABC, abstractmethod
from typing import AsyncIterator
from core.monitor import record_call


class ProviderMeta:
    """Provider metaandmed — capability deklaratsioon (33_PROVIDER_SDK_BIBLE.md)."""
    def __init__(self, *,
                 provider_id: str,
                 supported_models: list[str],
                 supported_features: list[str],
                 pricing_class: str,       # 'budget' | 'standard' | 'premium'
                 latency_class: str,       # 'fast' | 'normal' | 'slow'
                 max_context: int,
                 supports_streaming: bool,
                 supports_vision: bool):
        self.provider_id       = provider_id
        self.supported_models  = supported_models
        self.supported_features = supported_features
        self.pricing_class     = pricing_class
        self.latency_class     = latency_class
        self.max_context       = max_context
        self.supports_streaming = supports_streaming
        self.supports_vision   = supports_vision

    def to_dict(self) -> dict:
        return self.__dict__


class BaseAdapter(ABC):
    """Ühine liides kõigile AI provideritele (Provider Contract v2)."""
    name: str = "base"
    meta: ProviderMeta | None = None

    # ── Lifecycle ─────────────────────────────────────────────────────────────
    async def initialize(self) -> bool:
        """Provider initsialiseerimine (API key kontroll jne). Tagastab True kui OK."""
        return True

    async def health_check(self) -> dict:
        """Kontrollib et provider vastab — latentsustest."""
        t0 = time.monotonic()
        try:
            result = await self.chat([{"role": "user", "content": "ping"}], max_tokens=5)
            ok = result is not None
        except Exception as e:
            return {"provider": self.name, "ok": False, "error": str(e), "ms": 0}
        ms = int((time.monotonic() - t0) * 1000)
        return {"provider": self.name, "ok": ok, "ms": ms}

    # ── Core methods (implementeerib iga provider) ────────────────────────────
    @abstractmethod
    async def chat(self, messages: list, system: str = "", max_tokens: int = 400) -> str | None:
        """Tekst → tekst. messages = [{"role":"user","content":"..."}]"""

    async def stream_chat(self, messages: list, system: str = "", max_tokens: int = 400) -> AsyncIterator[str]:
        """Streaming chat — tagastab token generator.
        Vaikimisi: mittestreamiv fallback (üks chunk)."""
        result = await self.chat(messages, system=system, max_tokens=max_tokens)
        if result:
            yield result

    async def vision(self, image_b64: str, prompt: str, system: str = "", max_tokens: int = 400) -> str | None:
        """Pilt + tekst → tekst."""
        return None

    async def embeddings(self, text: str) -> list[float] | None:
        """Tekst → vektor. Tulevane semantic search."""
        return None

    async def speech_to_text(self, audio_b64: str, lang: str = "ru") -> str | None:
        """Heli → tekst (Whisper jne)."""
        return None

    async def text_to_speech(self, text: str, voice: str = "onyx") -> bytes | None:
        """Tekst → heli."""
        return None

    async def list_models(self) -> list[str]:
        """Tagastab provider toetatud mudelite nimekirja."""
        return self.meta.supported_models if self.meta else []

    # ── Internal helpers ──────────────────────────────────────────────────────
    async def _timed_call(self, coro, intent: str = "chat"):
        """Wrapper: mõõdab latentsust + registreerib monitoris."""
        t0 = time.monotonic()
        try:
            result = await coro
            ms = int((time.monotonic() - t0) * 1000)
            record_call(self.name, intent, ms, success=result is not None)
            return result
        except Exception as e:
            ms = int((time.monotonic() - t0) * 1000)
            record_call(self.name, intent, ms, success=False, error=str(e))
            return None


# ── OpenAI Adapter ────────────────────────────────────────────────────────────
class OpenAIAdapter(BaseAdapter):
    name = "openai"
    BASE = "https://api.openai.com/v1"
    meta = ProviderMeta(
        provider_id="openai",
        supported_models=["gpt-4o", "gpt-4o-mini", "gpt-4-turbo"],
        supported_features=["chat", "vision", "embeddings", "tts", "stt", "streaming", "function_calling"],
        pricing_class="premium",
        latency_class="normal",
        max_context=128000,
        supports_streaming=True,
        supports_vision=True,
    )

    def __init__(self, model_smart="gpt-4o", model_fast="gpt-4o-mini"):
        self._key = os.getenv("OPENAI_API_KEY", "")
        self.model_smart = model_smart
        self.model_fast  = model_fast

    async def initialize(self) -> bool:
        return bool(self._key)

    def _headers(self):
        return {"Authorization": f"Bearer {self._key}", "Content-Type": "application/json"}

    async def chat(self, messages: list, system: str = "", max_tokens: int = 400) -> str | None:
        if not self._key: return None
        msgs = ([{"role": "system", "content": system}] if system else []) + messages
        async def _do():
            async with httpx.AsyncClient(timeout=30) as c:
                r = await c.post(f"{self.BASE}/chat/completions", headers=self._headers(),
                    json={"model": self.model_smart, "max_tokens": max_tokens, "messages": msgs})
                if r.status_code == 200:
                    return r.json()["choices"][0]["message"]["content"]
            return None
        return await self._timed_call(_do(), "chat")

    async def vision(self, image_b64: str, prompt: str, system: str = "", max_tokens: int = 400) -> str | None:
        if not self._key: return None
        content = [
            {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{image_b64}"}},
            {"type": "text", "text": prompt or "Analysи изображение."},
        ]
        msgs = ([{"role": "system", "content": system}] if system else []) + \
               [{"role": "user", "content": content}]
        async def _do():
            async with httpx.AsyncClient(timeout=30) as c:
                r = await c.post(f"{self.BASE}/chat/completions", headers=self._headers(),
                    json={"model": self.model_smart, "max_tokens": max_tokens, "messages": msgs})
                if r.status_code == 200:
                    return r.json()["choices"][0]["message"]["content"]
            return None
        return await self._timed_call(_do(), "vision")

    async def embeddings(self, text: str) -> list[float] | None:
        if not self._key: return None
        async with httpx.AsyncClient(timeout=15) as c:
            r = await c.post(f"{self.BASE}/embeddings", headers=self._headers(),
                json={"model": "text-embedding-3-small", "input": text[:8000]})
            if r.status_code == 200:
                return r.json()["data"][0]["embedding"]
        return None

    async def text_to_speech(self, text: str, voice: str = "onyx") -> bytes | None:
        if not self._key: return None
        async with httpx.AsyncClient(timeout=20) as c:
            r = await c.post(f"{self.BASE}/audio/speech", headers=self._headers(),
                json={"model": "tts-1", "voice": voice, "input": text[:4096]})
            if r.status_code == 200:
                return r.content
        return None

    async def speech_to_text(self, audio_b64: str, lang: str = "ru") -> str | None:
        if not self._key: return None
        import base64
        audio_bytes = base64.b64decode(audio_b64)
        async with httpx.AsyncClient(timeout=30) as c:
            r = await c.post(f"{self.BASE}/audio/transcriptions",
                headers={"Authorization": f"Bearer {self._key}"},
                files={"file": ("audio.webm", audio_bytes, "audio/webm")},
                data={"model": "whisper-1", "language": lang})
            if r.status_code == 200:
                return r.json().get("text")
        return None

    async def stream_chat(self, messages: list, system: str = "", max_tokens: int = 400):
        if not self._key: return
        msgs = ([{"role": "system", "content": system}] if system else []) + messages
        async with httpx.AsyncClient(timeout=60) as c:
            async with c.stream("POST", f"{self.BASE}/chat/completions",
                    headers=self._headers(),
                    json={"model": self.model_smart, "max_tokens": max_tokens,
                          "messages": msgs, "stream": True}) as r:
                async for line in r.aiter_lines():
                    if line.startswith("data: ") and line != "data: [DONE]":
                        import json
                        try:
                            delta = json.loads(line[6:])["choices"][0]["delta"]
                            if "content" in delta and delta["content"]:
                                yield delta["content"]
                        except Exception:
                            pass

    async def list_models(self) -> list[str]:
        if not self._key: return self.meta.supported_models
        try:
            async with httpx.AsyncClient(timeout=10) as c:
                r = await c.get(f"{self.BASE}/models", headers=self._headers())
                if r.status_code == 200:
                    return [m["id"] for m in r.json()["data"] if "gpt" in m["id"]]
        except Exception:
            pass
        return self.meta.supported_models


# ── Claude Adapter ────────────────────────────────────────────────────────────
class ClaudeAdapter(BaseAdapter):
    name = "claude"
    BASE = "https://api.anthropic.com/v1/messages"
    meta = ProviderMeta(
        provider_id="claude",
        supported_models=["claude-sonnet-4-6", "claude-haiku-4-5-20251001", "claude-opus-4-8"],
        supported_features=["chat", "vision", "streaming", "long_context"],
        pricing_class="premium",
        latency_class="normal",
        max_context=200000,
        supports_streaming=True,
        supports_vision=True,
    )

    def __init__(self, model="claude-sonnet-4-6"):
        self._key  = os.getenv("ANTHROPIC_API_KEY", "")
        self.model = model

    async def initialize(self) -> bool:
        return bool(self._key)

    def _headers(self):
        return {"x-api-key": self._key, "anthropic-version": "2023-06-01",
                "content-type": "application/json"}

    async def chat(self, messages: list, system: str = "", max_tokens: int = 400) -> str | None:
        if not self._key: return None
        async def _do():
            body = {"model": self.model, "max_tokens": max_tokens, "messages": messages}
            if system: body["system"] = system
            async with httpx.AsyncClient(timeout=30) as c:
                r = await c.post(self.BASE, headers=self._headers(), json=body)
                if r.status_code == 200:
                    return r.json()["content"][0]["text"]
            return None
        return await self._timed_call(_do(), "chat")

    async def vision(self, image_b64: str, prompt: str, system: str = "", max_tokens: int = 400) -> str | None:
        if not self._key: return None
        content = [
            {"type": "image", "source": {"type": "base64", "media_type": "image/jpeg", "data": image_b64}},
            {"type": "text", "text": prompt or "Analysи изображение."},
        ]
        return await self.chat([{"role": "user", "content": content}], system=system, max_tokens=max_tokens)

    async def stream_chat(self, messages: list, system: str = "", max_tokens: int = 400):
        if not self._key: return
        body = {"model": self.model, "max_tokens": max_tokens, "messages": messages, "stream": True}
        if system: body["system"] = system
        headers = {**self._headers(), "anthropic-beta": "messages-2023-06-01"}
        async with httpx.AsyncClient(timeout=60) as c:
            async with c.stream("POST", self.BASE, headers=headers, json=body) as r:
                async for line in r.aiter_lines():
                    if line.startswith("data: "):
                        import json
                        try:
                            ev = json.loads(line[6:])
                            if ev.get("type") == "content_block_delta":
                                text = ev.get("delta", {}).get("text", "")
                                if text: yield text
                        except Exception:
                            pass


# ── Gemini Adapter ────────────────────────────────────────────────────────────
class GeminiAdapter(BaseAdapter):
    name = "gemini"
    meta = ProviderMeta(
        provider_id="gemini",
        supported_models=["gemini-2.5-flash", "gemini-2.5-pro", "gemini-2.0-flash"],
        supported_features=["chat", "vision", "streaming", "long_context"],
        pricing_class="budget",
        latency_class="fast",
        max_context=1000000,
        supports_streaming=True,
        supports_vision=True,
    )

    def __init__(self, model="gemini-2.5-flash"):
        self._key  = os.getenv("GEMINI_API_KEY", "")
        self.model = model

    async def initialize(self) -> bool:
        return bool(self._key)

    async def chat(self, messages: list, system: str = "", max_tokens: int = 400) -> str | None:
        if not self._key: return None
        async def _do():
            try:
                from google import genai
                from google.genai import types
                client = genai.Client(api_key=self._key)
                parts = [types.Part.from_text(text=m["content"]) for m in messages if m.get("role") == "user"]
                resp = await asyncio.to_thread(
                    client.models.generate_content,
                    model=self.model,
                    contents=types.Content(parts=parts, role="user"),
                    config=types.GenerateContentConfig(
                        system_instruction=system or None, max_output_tokens=max_tokens))
                return resp.text
            except Exception:
                return None
        return await self._timed_call(_do(), "chat")

    async def vision(self, image_b64: str, prompt: str, system: str = "", max_tokens: int = 400) -> str | None:
        if not self._key: return None
        async def _do():
            try:
                import base64
                from google import genai
                from google.genai import types
                client = genai.Client(api_key=self._key)
                parts = [
                    types.Part.from_bytes(data=base64.b64decode(image_b64), mime_type="image/jpeg"),
                    types.Part.from_text(text=prompt or "Analysи."),
                ]
                resp = await asyncio.to_thread(
                    client.models.generate_content,
                    model=self.model,
                    contents=types.Content(parts=parts, role="user"),
                    config=types.GenerateContentConfig(
                        system_instruction=system or None, max_output_tokens=max_tokens))
                return resp.text
            except Exception:
                return None
        return await self._timed_call(_do(), "vision")


# ── Perplexity Adapter ────────────────────────────────────────────────────────
class PerplexityAdapter(BaseAdapter):
    name = "perplexity"
    BASE = "https://api.perplexity.ai/chat/completions"
    meta = ProviderMeta(
        provider_id="perplexity",
        supported_models=["llama-3.1-sonar-large-128k-online", "llama-3.1-sonar-small-128k-online"],
        supported_features=["chat", "web_search", "citations"],
        pricing_class="standard",
        latency_class="normal",
        max_context=128000,
        supports_streaming=False,
        supports_vision=False,
    )

    def __init__(self, model="llama-3.1-sonar-large-128k-online"):
        self._key  = os.getenv("PERPLEXITY_API_KEY", "")
        self.model = model

    async def initialize(self) -> bool:
        return bool(self._key)

    async def chat(self, messages: list, system: str = "", max_tokens: int = 400) -> str | None:
        if not self._key: return None
        msgs = ([{"role": "system", "content": system}] if system else []) + messages
        async def _do():
            async with httpx.AsyncClient(timeout=20) as c:
                r = await c.post(self.BASE,
                    headers={"Authorization": f"Bearer {self._key}", "Content-Type": "application/json"},
                    json={"model": self.model, "messages": msgs, "max_tokens": max_tokens,
                          "temperature": 0.2, "return_citations": True})
                if r.status_code == 200:
                    data = r.json()
                    text = data["choices"][0]["message"]["content"]
                    cits = data.get("citations", [])
                    if cits: text += "\n[" + ", ".join(cits[:2]) + "]"
                    return text
            return None
        return await self._timed_call(_do(), "search")


# ── Registry ──────────────────────────────────────────────────────────────────
_adapters: dict[str, BaseAdapter] = {}

def get_adapter(name: str) -> BaseAdapter | None:
    if not _adapters:
        _register_defaults()
    return _adapters.get(name)

def register_adapter(adapter: BaseAdapter):
    _adapters[adapter.name] = adapter

def list_adapters() -> list[str]:
    if not _adapters: _register_defaults()
    return list(_adapters.keys())

def list_adapters_meta() -> list[dict]:
    """Tagastab kõigi providerite metadata (33_PROVIDER_SDK_BIBLE.md)."""
    if not _adapters: _register_defaults()
    result = []
    for a in _adapters.values():
        d = {"name": a.name}
        if a.meta:
            d.update(a.meta.to_dict())
        result.append(d)
    return result

def _register_defaults():
    for cls in [OpenAIAdapter, ClaudeAdapter, GeminiAdapter, PerplexityAdapter]:
        a = cls()
        _adapters[a.name] = a
