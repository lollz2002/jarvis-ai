import asyncio
import base64
import json
import os
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse

from agents.orchestrator import run_all, run_primary, get_agent_list
from memory.memory import (save_interaction, get_stats, get_recent, save_pref, get_prefs,
                           save_fact, get_context_for_prompt, export_memory)
from voice.tts import text_to_speech
from core.plugin_sdk import get_registry
from core.monitor import get_stats as mon_stats, get_errors, get_tool_usage, get_audit_log, get_provider_health, audit
from core.adapters import get_adapter, list_adapters

API_VERSION = "v1"

app = FastAPI(title="Albert OS API", version=API_VERSION)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

# ── Plugin käivitamine ─────────────────────────────────────────────────────────
@app.on_event("startup")
async def _load_plugins():
    reg = get_registry()
    try:
        from plugins.calendar_plugin      import CalendarPlugin
        from plugins.obd_plugin           import OBDPlugin
        from plugins.homeassistant_plugin import HomeAssistantPlugin
        for cls in [CalendarPlugin, OBDPlugin, HomeAssistantPlugin]:
            p = cls()
            reg.register(p)
        await reg.initialize_all()
    except Exception as e:
        import logging
        logging.getLogger("server").warning(f"Plugin load viga: {e}")

# ── Ühendatud seadmed ──────────────────────────────────────────────────────────
connected_devices: dict[str, WebSocket] = {}

@app.websocket("/ws/{device_id}")
async def websocket_endpoint(websocket: WebSocket, device_id: str):
    await websocket.accept()
    connected_devices[device_id] = websocket
    await broadcast({"type": "device_joined", "device": device_id, "total": len(connected_devices)}, exclude=device_id)
    await websocket.send_json({"type": "welcome", "device": device_id,
                                "agents": get_agent_list(), "online": list(connected_devices.keys())})
    try:
        while True:
            data = await websocket.receive_json()
            await handle_ws_message(websocket, device_id, data)
    except WebSocketDisconnect:
        connected_devices.pop(device_id, None)
        await broadcast({"type": "device_left", "device": device_id, "total": len(connected_devices)})

async def handle_ws_message(ws: WebSocket, device_id: str, data: dict):
    msg_type = data.get("type")

    if msg_type == "analyze":
        image_b64 = data.get("image")
        prompt = data.get("prompt", "")
        mode = data.get("mode", "default")
        targets = data.get("target_devices", [])

        # 0. Plugin voice command dispatch (enne AI-d)
        if prompt:
            from agents.director import detect_language
            lang = detect_language(prompt)
            plugin_results = await get_registry().dispatch("voice_command", text=prompt, lang=lang)
            if plugin_results:
                plugin_text = " | ".join(r["result"] for r in plugin_results)
                audio_raw = await text_to_speech(plugin_text)
                audio_b64 = base64.b64encode(audio_raw).decode() if audio_raw else None
                await ws.send_json({"type": "analysis_result",
                    "results": [{"id": "plugin", "name": "Plugin", "response": plugin_text, "ms": 0, "error": None}],
                    "audio": audio_b64, "ts": datetime.now().isoformat(), "final": True})
                return

        # 1. Nutikas vastus — direktor valib AI-d, sünteesib
        primary = await run_primary(image_b64=image_b64, prompt=prompt, mode=mode)
        # Tuvasta brauserikäsklused vastusest
        browser_cmd = _detect_browser_command(prompt)
        audio_b64 = None
        if primary and primary.get("response"):
            audio_raw = await text_to_speech(primary["response"])
            if audio_raw:
                audio_b64 = base64.b64encode(audio_raw).decode()

        fast_response = {"type": "analysis_result", "results": [primary] if primary else [],
                         "audio": audio_b64, "ts": datetime.now().isoformat(), "final": True}
        await ws.send_json(fast_response)

        # Saada tööriistavastused kõigile seadmetele
        ws_commands = (primary or {}).pop("_ws_commands", [])
        if browser_cmd:
            ws_commands.append(browser_cmd)
        for cmd in ws_commands:
            await broadcast(cmd)
        for tid in targets:
            if tid in connected_devices and tid != device_id:
                await connected_devices[tid].send_json({**fast_response, "from_device": device_id})

        # 2. Salvesta taustal
        async def run_rest():
            save_interaction(device_id, prompt, [primary] if primary else [])

        asyncio.create_task(run_rest())

    elif msg_type == "broadcast":
        # Saada sõnum kõigile seadmetele
        await broadcast({"type": "broadcast_msg", "from": device_id, "text": data.get("text", ""),
                         "ts": datetime.now().isoformat()})

    elif msg_type == "send_to":
        # Saada sõnum konkreetsele seadmele
        target = data.get("target")
        if target in connected_devices:
            await connected_devices[target].send_json({"type": "direct_msg", "from": device_id,
                                                        "text": data.get("text", "")})

    elif msg_type == "computer_command_direct":
        # Saada otse Windows agendile
        if "windows_agent" in connected_devices:
            await connected_devices["windows_agent"].send_json({
                "type": "computer_command",
                "command": data.get("command"),
                "args": data.get("args", {}),
                "request_id": str(datetime.now().timestamp())
            })
        # Edasta screen_frame kõigile (v.a. agendile)
    elif msg_type == "screen_frame":
        await broadcast(data, exclude=device_id)

    elif msg_type == "remember":
        # Salvesta fakt mällu
        save_fact(data.get("key", "note"), data.get("value", ""))
        await ws.send_json({"type": "remembered", "key": data.get("key"), "value": data.get("value")})

    elif msg_type == "get_memory":
        ctx = get_context_for_prompt()
        await ws.send_json({"type": "memory_context", "context": ctx})

    elif msg_type == "computer_result":
        # Windows agendi vastus — tee sellest häälvastus ja saada kõigile
        result_text = data.get("result", "")
        if result_text:
            audio_raw = await text_to_speech(result_text)
            audio_b64 = base64.b64encode(audio_raw).decode() if audio_raw else None
            fake_result = {"id": "windows", "name": "Windows", "response": result_text, "ms": None, "error": None}
            await broadcast({"type": "analysis_result", "results": [fake_result],
                             "audio": audio_b64, "ts": datetime.now().isoformat(), "final": True})

    elif msg_type == "ping":
        await ws.send_json({"type": "pong"})

def _detect_browser_command(prompt: str) -> dict | None:
    import re
    p = prompt.lower()
    # Otsing
    m = re.search(r'(найди|поищи|search|otsi|guugelda)\s+(.+)', p)
    if m:
        return {"type": "browser_search", "query": m.group(2).strip()}
    # URL avamine
    m = re.search(r'(открой|avа|open)\s+(https?://\S+)', p)
    if m:
        return {"type": "browser_open", "url": m.group(2)}
    # YouTube
    m = re.search(r'(youtube|ютуб).+?(найди|поищи|otsi|search)\s+(.+)', p)
    if m:
        return {"type": "browser_open", "url": f"https://www.youtube.com/results?search_query={m.group(3)}"}
    return None

async def broadcast(message: dict, exclude: str = None):
    dead = []
    for did, ws in connected_devices.items():
        if did == exclude:
            continue
        try:
            await ws.send_json(message)
        except Exception:
            dead.append(did)
    for d in dead:
        connected_devices.pop(d, None)

# ── REST API ───────────────────────────────────────────────────────────────────
@app.post("/analyze")
async def analyze(request: Request):
    req = await request.json()
    results = await run_all(image_b64=req.get("image"), prompt=req.get("prompt",""), mode=req.get("mode","default"), agents=req.get("agents"))
    save_interaction("api", req.get("prompt",""), results)
    audio = None
    for r in results:
        if r.get("response"):
            raw = await text_to_speech(r["response"])
            if raw:
                audio = base64.b64encode(raw).decode()
            break
    return {"results": results, "audio": audio}

@app.get("/agents")
def agents():
    return get_agent_list()

@app.get("/devices")
def devices():
    return {"online": list(connected_devices.keys()), "total": len(connected_devices)}

@app.get("/memory/stats")
def memory_stats():
    return get_stats()

@app.get("/memory/recent")
def memory_recent():
    return get_recent(20)

@app.get("/memory/export")
def memory_export():
    from memory.memory import export_memory
    return export_memory()

@app.post("/memory/knowledge")
async def memory_add_knowledge(request: Request):
    from memory.memory import add_knowledge
    body = await request.json()
    kid = add_knowledge(body["title"], body["content"],
                        body.get("category", "general"),
                        body.get("tags", ""), body.get("project", ""))
    return {"ok": True, "id": kid}

@app.get("/memory/knowledge")
async def memory_search_knowledge(q: str = "", category: str = None, project: str = None):
    from memory.memory import search_knowledge
    return search_knowledge(q, category, project)

@app.get("/memory/profile")
def memory_profile():
    from memory.memory import get_user_profile
    return get_user_profile()

@app.post("/memory/profile")
async def memory_update_profile(request: Request):
    from memory.memory import update_user_profile
    body = await request.json()
    update_user_profile(**body)
    return {"ok": True}

@app.get("/health")
def health():
    return {"ok": True, "devices": len(connected_devices)}

# ── Plugin REST API ────────────────────────────────────────────────────────────
@app.get("/plugins")
def plugins_list():
    return get_registry().list_plugins()

@app.post("/plugins/{plugin_id}/approve")
async def plugin_approve(plugin_id: str, request: Request):
    body = await request.json()
    return get_registry().approve_permissions(plugin_id, body.get("permissions", []))

@app.post("/plugins/{plugin_id}/command")
async def plugin_command(plugin_id: str, request: Request):
    body = await request.json()
    reg = get_registry()
    plugin = reg.get_plugin(plugin_id)
    if not plugin:
        return {"error": "Plugin ei leitud"}
    result = await plugin.run_command(body.get("cmd", ""), body.get("args", {}))
    return {"result": result}

@app.delete("/plugins/{plugin_id}")
async def plugin_remove(plugin_id: str):
    await get_registry().remove(plugin_id)
    return {"ok": True}

# ── Monitoring & Observability (API v1) ───────────────────────────────────────
@app.get("/api/v1/monitor/stats")
def api_monitor_stats():
    return {"provider_metrics": mon_stats(), "tool_usage": get_tool_usage()}

@app.get("/api/v1/monitor/errors")
def api_monitor_errors(n: int = 20):
    return get_errors(n)

@app.get("/api/v1/monitor/audit")
def api_monitor_audit(n: int = 50):
    return get_audit_log(n)

@app.get("/api/v1/providers/health")
async def api_providers_health():
    """Kontrollib iga provider tervist — latentsus + status."""
    from core.adapters import OpenAIAdapter, ClaudeAdapter, GeminiAdapter, PerplexityAdapter
    results = {}
    checks = await asyncio.gather(
        OpenAIAdapter().health_check(),
        ClaudeAdapter().health_check(),
        GeminiAdapter().health_check(),
        PerplexityAdapter().health_check(),
        return_exceptions=True
    )
    for r in checks:
        if isinstance(r, dict):
            results[r["provider"]] = r
    trend = get_provider_health()
    return {"checks": results, "trend": trend, "adapters": list_adapters()}

# ── Streaming endpoint (SSE) ──────────────────────────────────────────────────
@app.post("/api/v1/stream")
async def api_stream(request: Request):
    """
    Server-Sent Events streaming vastus.
    Body: {"prompt": "...", "image": null, "system": ""}
    """
    body   = await request.json()
    prompt = body.get("prompt", "")
    image  = body.get("image")
    system = body.get("system", "")

    async def generate():
        try:
            from agents.director import run_with_tools
            from memory.memory import get_context_for_prompt
            ctx = get_context_for_prompt(prompt)
            # Jooksev vastus tervikuna (streaming impl nõuab httpx streaming)
            text, _ = await run_with_tools(prompt, image, ctx)
            # Streams teksti sõna haaval (simulatsioon; päris streaming vajab provider-side SSE)
            words = (text or "").split(" ")
            for i, word in enumerate(words):
                chunk = word + (" " if i < len(words) - 1 else "")
                yield f"data: {json.dumps({'delta': chunk})}\n\n"
                await asyncio.sleep(0.01)
            yield "data: [DONE]\n\n"
            audit("stream_completed", {"prompt_len": len(prompt)})
        except Exception as e:
            yield f"data: {json.dumps({'error': str(e)})}\n\n"

    return StreamingResponse(generate(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})

# ── API v1 aliased ─────────────────────────────────────────────────────────────
@app.post("/api/v1/analyze")
async def api_v1_analyze(request: Request):
    return await analyze(request)

@app.get("/api/v1/health")
def api_v1_health():
    return {"ok": True, "version": API_VERSION, "devices": len(connected_devices),
            "provider_health": get_provider_health()}

@app.get("/api/v1/adapters")
def api_v1_adapters():
    return {"adapters": list_adapters(), "version": API_VERSION}

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run("server:app", host="0.0.0.0", port=port, reload=True)
