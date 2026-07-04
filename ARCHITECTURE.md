# Albert OS — Arhitektuur

Version: 1.0 | Viimati uuendatud: 2025-07

---

## Ülevaade

Albert OS on modulaarne AI operatsioonisüsteem telefoni, lauaarvuti ja AR prillide jaoks.

```
Kasutaja (hääl / puudutus / gesti)
        ↓
  UI Engine (React PWA / AR HUD)
        ↓
  WebSocket (FastAPI)
        ↓
  JarvisDirector
    ├── Intent classifier (10 klassi)
    ├── Language detector (et/ru/en)
    ├── Routing Config → Provider valija
    └── Tool Executor
        ↓
  Provider Adapter Layer
    ├── OpenAIAdapter   (gpt-4o, whisper, tts, embeddings)
    ├── ClaudeAdapter   (claude-sonnet-4-6)
    ├── GeminiAdapter   (gemini-2.5-flash)
    └── PerplexityAdapter (online search)
        ↓
  Memory Engine (SQLite)
    ├── user_profile, facts, contacts, notes
    ├── projects, project_entries, milestones
    ├── knowledge, memory_index
    ├── vehicles, documents, conversations
    └── Retrieval pipeline (ranked context)
        ↓
  Plugin System
    ├── CalendarPlugin
    ├── OBDPlugin
    └── HomeAssistantPlugin
```

---

## Backend (`/backend`)

| Moodul | Fail | Vastutus |
|--------|------|----------|
| Server | `server.py` | FastAPI, WebSocket, REST API v1 |
| Director | `agents/director.py` | Intent → provider → vastus |
| Adapters | `core/adapters.py` | Unified AI provider interface |
| Routing | `core/routing_config.py` | Intent → provider mapping |
| Tools | `core/tools.py` | OpenAI function calling tööriistad |
| Monitor | `core/monitor.py` | Latentsus, vead, audit log |
| Plugin SDK | `core/plugin_sdk.py` | Plugin lifecycle + registry |
| Memory | `memory/memory.py` | SQLite v3, 11 tabelit |
| Vision | `engines/vision_engine.py` | 6 vision režiimi |
| TTS | `voice/tts.py` | OpenAI TTS + ElevenLabs fallback |
| Personality | `agents/personality.py` | JARVIS süsteemiprompt |
| Plugins | `plugins/` | Calendar, OBD-II, HomeAssistant |

---

## Frontend (`/frontend/src`)

| Komponent | Fail | Vastutus |
|-----------|------|----------|
| App | `App.jsx` | Peamine telefoni/desktop UI |
| AR HUD | `GlassesHUD.jsx` | XREAL prillide HUD v3 |
| Sphere | `components/JarvisSphere.jsx` | Three.js 3D animatsioon |
| Voice | `components/VoiceInput.jsx` | Wake word, interrupt, mute |
| Gesture | `engines/gestureEngine.js` | Touch/swipe abstraktsioon |
| Device | `hooks/useDeviceManager.js` | XREAL detekteerimine |
| JARVIS | `hooks/useJarvis.js` | WebSocket hook |

---

## Andmebaas (SQLite)

```
albert_os.db
├── user_profile    — keel, ajavöönd, AI seaded
├── facts           — lühimälu faktid
├── projects        — aktiivsed projektid
├── project_entries — projekti alamkanded
├── milestones      — verstapostid
├── contacts        — kontaktid
├── notes           — märkmed
├── conversations   — vestluste ajalugu
├── knowledge       — teadmistebaas
├── memory_index    — kõigi mälukannete indeks
├── vehicles        — sõidukid
└── documents       — dokumendid
```

---

## API Endpointid

### WebSocket
- `ws://.../ws/{device_id}` — peamine reaalajaühendus

### REST v1
- `POST /api/v1/analyze` — analüüs
- `POST /api/v1/stream` — SSE streaming
- `GET  /api/v1/health` — tervisekontroll
- `GET  /api/v1/providers/health` — providerite seis
- `GET  /api/v1/monitor/stats` — metrikad
- `GET  /api/v1/monitor/audit` — audit log
- `GET  /plugins` — pluginate nimekiri
- `GET  /memory/export` — GDPR eksport
- `GET  /memory/knowledge` — teadmistebaas otsing

---

## Deployment

| Komponent | Platvorm | URL |
|-----------|----------|-----|
| Backend | Railway.app | `carefree-gentleness-production-6657.up.railway.app` |
| Frontend | Vercel | PWA + `/glasses` AR route |
| Windows Agent | Kohalik | WebSocket ühendub backendiga |

---

## Git Workflow

```
main        ← stabiilne tootmine
develop     ← integratsioon
feature/*   ← uued funktsioonid
hotfix/*    ← kiirparandused
```

Commit formaat:
```
feat: lisa AR workspace manager
fix: paranda mälu tagasilaadimine
docs: uuenda Vision Engine spek
refactor: lihtsusta provider adapter
```
