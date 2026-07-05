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
from core.security import device_trust, rate_limiter, input_sanitizer, is_dangerous_action, create_backup, restore_backup

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

    # Project Brain — initsialiseerib vaikimisi projektiruumid
    try:
        from memory.memory import init_project_brain
        init_project_brain()
    except Exception:
        pass

    # Runtime Kernel käivitus (36_RUNTIME_AND_EVENT_SYSTEM_BIBLE.md)
    try:
        from core.runtime import kernel
        await kernel.start()
    except Exception as e:
        import logging
        logging.getLogger("server").warning("Runtime kernel start warning: %s", e)

    # Networking Layer + Sync Engine (39_NETWORKING_AND_CLOUD_BIBLE.md)
    try:
        from core.networking import networking
        from core.sync import sync_engine
        await networking.start_retry_loop(interval_s=60)
        await sync_engine.start(interval_s=120)
    except Exception as e:
        import logging
        logging.getLogger("server").warning("Networking/Sync start warning: %s", e)

# ── Ühendatud seadmed ──────────────────────────────────────────────────────────
connected_devices: dict[str, WebSocket] = {}

@app.websocket("/ws/{device_id}")
async def websocket_endpoint(websocket: WebSocket, device_id: str):
    await websocket.accept()

    # Seadme usalduse kontroll
    trust = device_trust.get_trust_level(device_id)
    if trust == "unknown":
        device_trust.register_device(device_id, auto_approve=True)
        audit("device_first_seen", {"device_id": device_id})
    elif trust == "pending":
        await websocket.send_json({"type": "error", "msg": "Seade pole kinnitatud."})
        await websocket.close()
        return

    connected_devices[device_id] = websocket
    await broadcast({"type": "device_joined", "device": device_id, "total": len(connected_devices)}, exclude=device_id)
    await websocket.send_json({"type": "welcome", "device": device_id,
                                "agents": get_agent_list(), "online": list(connected_devices.keys()),
                                "trust": device_trust.get_trust_level(device_id)})
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

        # Rate limiting
        allowed, reason = rate_limiter.is_allowed(device_id)
        if not allowed:
            await ws.send_json({"type": "error", "msg": reason})
            return

        # Input sanitization
        if prompt:
            prompt, suspicious = input_sanitizer.sanitize(prompt)
            if suspicious:
                audit("suspicious_input", {"device": device_id, "hint": prompt[:60]})
                await ws.send_json({"type": "warning", "msg": "Kahtlane sisend tuvastatud — töötlen ettevaatlikult."})

        # Ohtlike toimingute kinnitus
        if prompt:
            dangerous, danger_desc = is_dangerous_action(prompt)
            if dangerous:
                audit("dangerous_action_blocked", {"device": device_id, "desc": danger_desc})
                await ws.send_json({"type": "confirm_required",
                    "msg": f"⚠ {danger_desc}. Kinnita: saada sama sõnum tekstiga 'KINNITAN: {prompt[:30]}'"})
                return

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

@app.get("/api/v1/memory/projects")
def memory_projects(status: str = "active"):
    from memory.memory import get_projects
    return get_projects(status)

@app.get("/api/v1/memory/facts")
def memory_facts():
    from memory.memory import get_all_facts
    return get_all_facts()

@app.post("/api/v1/memory/forget")
async def memory_forget(request: Request):
    from memory.memory import forget_fact
    body = await request.json()
    forget_fact(body["key"])
    return {"ok": True}

@app.get("/api/v1/memory/search")
async def memory_search(q: str = "", project: str = None):
    from memory.memory import search_all_memory
    return search_all_memory(q, project or None)

@app.post("/api/v1/memory/archive/{memory_id}")
def memory_archive(memory_id: int):
    from memory.memory import archive_memory
    archive_memory(memory_id)
    return {"ok": True, "id": memory_id}

@app.post("/api/v1/memory/restore/{memory_id}")
def memory_restore(memory_id: int):
    from memory.memory import restore_memory
    ok = restore_memory(memory_id)
    return {"ok": ok, "id": memory_id}

@app.put("/api/v1/memory/facts/{key}")
async def memory_edit_fact(key: str, request: Request):
    from memory.memory import edit_fact
    body = await request.json()
    ok = edit_fact(key, body.get("value", ""))
    return {"ok": ok, "key": key}

@app.get("/api/v1/memory/index")
async def memory_index(q: str = "", project: str = None, include_archived: bool = False):
    from memory.memory import search_memory_index
    return search_memory_index(q, project or None, include_archived=include_archived)

@app.get("/api/v1/memory/projects/{name}/entries")
def memory_project_entries(name: str, entry_type: str = None):
    from memory.memory import get_project_entries
    return get_project_entries(name, entry_type or None)

@app.get("/api/v1/memory/projects/{name}/milestones")
def memory_project_milestones(name: str):
    from memory.memory import get_milestones
    return get_milestones(name, include_done=True)

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

@app.post("/plugins/{plugin_id}/enable")
async def plugin_enable(plugin_id: str):
    return await get_registry().enable(plugin_id)

@app.post("/plugins/{plugin_id}/disable")
async def plugin_disable(plugin_id: str):
    return await get_registry().disable(plugin_id)

@app.delete("/plugins/{plugin_id}")
async def plugin_remove(plugin_id: str):
    return await get_registry().uninstall(plugin_id)

@app.post("/plugins/manifest/validate")
async def plugin_manifest_validate(request: Request):
    """Manifest JSON valideerimine (spec 38 — Testing Checklist)."""
    from core.plugin_sdk import PluginLoader
    body = await request.json()
    errors = PluginLoader.validate_manifest(body)
    return {"valid": len(errors) == 0, "errors": errors, "sdk_version": "2.0.0"}

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

@app.get("/api/v1/providers/meta")
def api_v1_providers_meta():
    """Provider metadata — supported_features, pricing_class, latency_class jne."""
    from core.adapters import list_adapters_meta
    return {"providers": list_adapters_meta()}

@app.get("/api/v1/events")
def api_v1_events(n: int = 50):
    """Viimased N sündmust event bus'ist (debug/monitor)."""
    from core.events import get_history
    return {"events": get_history(n)}

@app.get("/api/v1/network/status")
async def api_network_status():
    """Networking Layer olek: online/offline, queue suurus."""
    from core.networking import networking
    state = await networking.check_connectivity()
    return {**networking.status(), "state": state}

@app.post("/api/v1/sync/now")
async def api_sync_now():
    """Käivita sünkroniseerimine kohe (spec 39)."""
    from core.sync import sync_engine
    return await sync_engine.sync_now()

@app.get("/api/v1/sync/status")
def api_sync_status():
    from core.sync import sync_engine, pending_count
    return {**sync_engine.status(), "pending": pending_count()}

@app.get("/api/v1/runtime/status")
def api_runtime_status():
    """Runtime Kernel olek: state, uptime, workers, services."""
    from core.runtime import kernel
    return kernel.status()

@app.get("/api/v1/schema/version")
def api_schema_version():
    """Andmebaasi skeemi versioon (35_DATABASE_BIBLE.md — Migration Rules)."""
    from memory.repositories import memories
    return {"schema_version": memories.schema_version()}

@app.get("/api/v1/vision/inspections")
def api_vision_inspections(project: str = None, limit: int = 20):
    from memory.repositories import vision as vrepo
    if project:
        return {"inspections": vrepo.get_by_project(project, limit)}
    return {"inspections": vrepo.get_recent(limit)}

@app.get("/api/v1/ai-sessions/stats")
def api_ai_session_stats():
    from memory.repositories import ai_sessions
    return {"stats": ai_sessions.get_stats()}

@app.get("/api/v1/agents/tasks/persisted")
def api_persisted_tasks(status: str = None):
    """Agendi ülesanded püsivalt DB-st (agent_manager in-memory + DB)."""
    from memory.repositories import tasks
    return {"tasks": tasks.list(status=status)}

# ── Agent Manager endpoints (34_AUTONOMOUS_AGENT_BIBLE.md) ───────────────────
from agents.agent_manager import manager as agent_manager

@app.get("/api/v1/agents/types")
def agents_types():
    return {"agent_types": agent_manager.agent_types()}

@app.post("/api/v1/agents/tasks")
async def agents_create_task(request: Request):
    """Loo uus agendi ülesanne ja käivita taustal."""
    body = await request.json()
    agent_type = body.get("agent_type", "research")
    objective  = body.get("objective", "")
    background = body.get("background", True)
    if not objective:
        return {"error": "objective required"}
    extra = {k: v for k, v in body.items() if k not in ("agent_type", "objective", "background")}
    task = agent_manager.create_task(agent_type, objective)
    if background:
        await agent_manager.run_task_background(task.task_id, **extra)
        return {"task_id": task.task_id, "status": "started"}
    else:
        task = await agent_manager.run_task(task.task_id, **extra)
        return task.to_dict()

@app.get("/api/v1/agents/tasks")
def agents_list_tasks(agent_type: str = None, status: str = None):
    return {"tasks": agent_manager.list_tasks(agent_type=agent_type, status=status)}

@app.get("/api/v1/agents/tasks/{task_id}")
def agents_get_task(task_id: str):
    task = agent_manager.get_task(task_id)
    if not task:
        return {"error": "not found"}
    return task.to_dict()

# ── Security endpoints ────────────────────────────────────────────────────────
@app.get("/security/devices")
def sec_devices():
    return device_trust.list_devices()

@app.post("/security/devices/{device_id}/approve")
def sec_approve(device_id: str):
    device_trust.approve_device(device_id)
    audit("device_approved", {"device_id": device_id})
    return {"ok": True}

@app.post("/security/devices/{device_id}/revoke")
def sec_revoke(device_id: str):
    device_trust.revoke_device(device_id)
    audit("device_revoked", {"device_id": device_id})
    return {"ok": True}

@app.delete("/security/devices/{device_id}")
def sec_remove(device_id: str):
    device_trust.remove_device(device_id)
    audit("device_removed", {"device_id": device_id})
    return {"ok": True}

@app.get("/security/rate/{device_id}")
def sec_rate(device_id: str):
    return rate_limiter.get_usage(device_id)

@app.post("/security/backup")
async def sec_backup(request: Request):
    body = await request.json()
    password = body.get("password", "")
    if len(password) < 8:
        return {"error": "Parool peab olema vähemalt 8 tähemärki"}
    encrypted = create_backup(password)
    import base64
    audit("backup_created", {})
    return {"backup": base64.b64encode(encrypted).decode(), "ts": datetime.now().isoformat()}

@app.post("/security/restore")
async def sec_restore(request: Request):
    body = await request.json()
    password = body.get("password", "")
    backup_b64 = body.get("backup", "")
    if not backup_b64 or not password:
        return {"error": "backup ja password on kohustuslikud"}
    import base64
    try:
        encrypted = base64.b64decode(backup_b64)
        data = restore_backup(encrypted, password)
        audit("backup_restored", {"tables": list(data.keys())})
        return {"ok": True, "restored": list(data.keys())}
    except Exception as e:
        return {"error": f"Taastamine ebaõnnestus: {e}"}

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run("server:app", host="0.0.0.0", port=port, reload=True)
