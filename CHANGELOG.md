# Albert OS Changelog

Kõik olulised muutused on siin dokumenteeritud.
Formaat: [Semver](https://semver.org) | Kuupäevad: ISO 8601

---

## [1.0.0-alpha] — 2026-07-05 — Albert OS v1 Alpha

### Added
- **File 31** UI Bible — Follow-up shortcuts, Camera Compare A/B, winClose animation, Dock keyboard nav
- **File 32** Code Architecture Bible — Event Bus v2 structured envelope, Repository Pattern, emit_sync
- **File 33** Provider SDK Bible — ProviderMeta, stream_chat SSE, list_models live API, all 4 adapters
- **File 34** Autonomous Agent Bible — AgentManager, 6 agent types, safety gates, Progress tracking
- **File 35** Database Bible — 5 uut tabelit, migration v4, 8 Repository singletonit
- **File 36** Runtime & Event System Bible — RuntimeKernel, ServiceRegistry, Worker, RuntimeState, 3 background workers
- **File 37** Android XR Implementation Bible — XRSessionLifecycle 6-state, spatial window contract, feature detection
- **File 38** Plugin SDK Implementation Bible — SDK v2.0.0, PluginState, hot-plug enable/disable
- **File 39** Networking & Cloud Bible — NetworkingLayer, ConflictResolution, SyncEngine, mark_dirty
- **File 40** Security Implementation Bible — SecretManager, RoleManager (RBAC), PromptInjectionDetector, audit events
- **File 41** Testing & Quality Bible — pytest suite (45 tests): security, events, networking
- **File 42** DevOps & CI/CD Bible — GitHub Actions CI pipeline (lint→test→build→security scan)
- **File 43** Sync Engine Bible — SyncState machine (Idle→DetectChanges→Upload→Download→Resolve→Complete)
- **File 44** Task & Automation Engine Bible — TaskEngine, 6 task types, safety gates, recurring tasks
- **File 45** Performance & Observability Bible — performance budgets, record_perf(), budget violation tracking
- **File 47** Albert OS SDK Bible — core/sdk.py public SDK module (kõik SDK-d ühest kohast)
- **File 49** Release & Versioning Bible — core/version.py semver, version_info()

### Security
- Prompt injection detection (18 mustrit: EN/ET/RU + DAN/jailbreak)
- RBAC 5 rolli: User/Administrator/Developer/Plugin/Service
- Audit events: login, memory_deletion, plugin_install, permission_change, provider_change

### Known Issues
- Android XR native mode: stub implementatsioon (WebXR probe)
- Local AI runtime: puudub (v2.0 plaan)
- Automated E2E tests: osaliselt (backend unit tests olemas, frontend E2E puudub)

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
