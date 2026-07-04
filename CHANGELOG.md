# Albert OS Changelog

Kõik olulised muutused on siin dokumenteeritud.
Formaat: [Semver](https://semver.org) | Kuupäevad: ISO 8601

---

## [Unreleased] — develop

### Added
- Plugin SDK (10_PLUGIN_SDK) — BasePlugin, PluginRegistry, lifecycle, permissions
  - CalendarPlugin (Google Calendar häälkäsklused)
  - OBDPlugin (ELM327 OBD-II diagnostika)
  - HomeAssistantPlugin (seadmete juhtimine häälega)
- Gesture Engine (09_GESTURE_SYSTEM) — touch/swipe/pinch abstraktsioon, keyboard sim, safety guard
- AR HUD v3 (08_AR_UI_BIBLE) — Top Bar (aku/WiFi/AI/ONLINE), Left/Right panelid, Bottom Dock
- Provider Adapter Layer (12_API_AND_INTEGRATION) — BaseAdapter, OpenAI/Claude/Gemini/Perplexity
- Monitoring (12_API_AND_INTEGRATION) — latentsus, vead, audit log, tool usage stats
- Streaming SSE endpoint `/api/v1/stream`
- API versioning `/api/v1/`
- Memory Engine v3 (11_DATABASE_SCHEMA) — user_profile, knowledge, memory_index, milestones
- GDPR: `delete_all_memory(confirm='DELETE')`
- Knowledge base (repair/workflow/manual/code/checklist)
- Conversation auto-summarize (>100 kirjet)

### Changed
- `memory/memory.py` — v2→v3, uued tabelid, laiendatud retrieval pipeline
- `server.py` — plugin startup, streaming, monitoring endpointid
- `GlassesHUD.jsx` — täielik HUD ümberkujundus vastavalt AR UI Bible spekile
- `director.py` — audit log integratsioon

---

## [0.9.0] — 2025-07 — MVP Pre-release

### Added
- Voice Engine v2 (07_VOICE_ENGINE) — wake word "Jarvis", interrupt TTS, mute, repeat, 3 keelt
- Vision Engine (06_VISION_ENGINE) — 6 režiimi: BMW/Boat/Construction/Electronics/Documents/General
- Memory Engine v2 (05_MEMORY_ENGINE) — SQLite, faktid/projektid/kontaktid/märkmed/vestlused/sõidukid
- JarvisDirector v2 (04_JARVIS_DIRECTOR) — 10 intent klassi, parallel execution, fallback chain
- Routing Config (03_SYSTEM_ARCHITECTURE) — provider mapping, FALLBACK_CHAIN
- AR UI v1 (GlassesHUD) — ujuvad aknad, drag/resize/transparency, workspaces
- Device Manager — XREAL detekteerimine, switchToAR()
- Windows Agent — Claude Vision, clipboard, window capture
- Multi-model: GPT-4o + Claude Sonnet + Gemini Flash + Perplexity

### Infrastructure
- FastAPI + WebSocket backend (Railway)
- React + Vite PWA frontend (Vercel)
- Three.js 3D kuldne sfäär (idle/listening/thinking/speaking)
- Web Speech API (ru-RU / et-EE / en-US)
- OpenAI TTS "onyx" + ElevenLabs fallback

---

## [0.1.0] — 2025-06 — JARVIS Alpha

### Added
- Algne JARVIS prototüüp
- OpenAI GPT-4o integratsioon
- Põhiline hääl + tekst sisend
- Lihtne mälüsüsteem

---

## Release Plan

| Versioon | Seis | Eesmärk |
|----------|------|---------|
| MVP | ✅ Valmis | Stabiilne UI, Director, Memory, Vision, Voice, AR |
| v1.0 | 🔄 Arendus | Plugin SDK, workspace persistence, production ready |
| v2.0 | 📋 Plaan | Android XR, käe jälgimine, smart home, sõidukid |
