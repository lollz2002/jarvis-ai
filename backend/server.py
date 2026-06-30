import asyncio
import base64
import json
import os
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Request
from fastapi.middleware.cors import CORSMiddleware

from agents.orchestrator import run_all, get_agent_list
from memory.memory import save_interaction, get_stats, get_recent, save_pref, get_prefs
from voice.tts import text_to_speech

app = FastAPI(title="JARVIS")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

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
        # Analüüsi + saada tulemused tagasi (ja valikuliselt teistele seadmetele)
        results = await run_all(
            image_b64=data.get("image"),
            prompt=data.get("prompt", ""),
            mode=data.get("mode", "default"),
            agents=data.get("agents")
        )
        save_interaction(device_id, data.get("prompt", ""), results)

        # TTS esimesest edukast vastusest
        audio_b64 = None
        for r in results:
            if r.get("response"):
                audio = await text_to_speech(r["response"])
                if audio:
                    audio_b64 = base64.b64encode(audio).decode()
                break

        response = {"type": "analysis_result", "results": results, "audio": audio_b64,
                    "ts": datetime.now().isoformat()}

        # Saada algsele seadmele
        await ws.send_json(response)

        # Kui target_devices määratud, saada ka sinna
        targets = data.get("target_devices", [])
        for tid in targets:
            if tid in connected_devices and tid != device_id:
                await connected_devices[tid].send_json({**response, "from_device": device_id})

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

    elif msg_type == "ping":
        await ws.send_json({"type": "pong"})

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

@app.get("/health")
def health():
    return {"ok": True, "devices": len(connected_devices)}

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run("server:app", host="0.0.0.0", port=port, reload=True)
