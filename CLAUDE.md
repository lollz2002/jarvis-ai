# Albert OS — Claude Developer Bible
Source: 23_COMPLETE_CLAUDE_DEVELOPER_BIBLE.md | Version: 1.0

---

## Mission

This is NOT a chatbot project.

Albert OS is a modular AI operating system for phone, desktop and AR glasses (XREAL / Android XR).

Every implementation decision must support that mission.

---

## Architecture Layers (never bypass)

```
UI  (GlassesHUD.jsx, App.jsx)
↓
Window Manager  (hooks/useWindowManager.js)
↓
Device Manager  (hooks/useDeviceManager.js + adapters/XRAdapter.js)
↓
JarvisDirector  (agents/director.py)
↓
Memory / Vision / Voice / Tools  (memory/, engines/, voice/, core/tools.py)
↓
Provider Adapters  (core/adapters.py)
↓
External Services  (OpenAI, Claude, Gemini, Perplexity, ElevenLabs)
```

---

## Development Constitution

1. Never rebuild from scratch — improve existing code.
2. Keep architecture modular — one responsibility per file.
3. Avoid duplicated logic — reuse hooks, adapters, panels.
4. Separate UI, business logic and integrations.
5. Prefer composition over duplication.
6. Write readable, maintainable code.

---

## Coding Rules

**Always:**
- Keep functions small and focused.
- Handle errors at system boundaries (user input, external APIs).
- Use environment variables for all secrets — never hardcode.
- Document public APIs (one-line docstring is enough).

**Never:**
- Expose API keys or secrets in code or logs.
- Remove working features without explicit instruction.
- Create duplicate implementations of existing logic.
- Couple provider-specific code to UI or business logic.

---

## Workflow

Before coding:
1. Read relevant existing files.
2. Detect reusable components.
3. Confirm plan if the change is non-trivial.

During coding:
1. Implement one feature at a time.
2. Verify build succeeds (`npm run build` / `python -c "import server"`).
3. Commit with conventional commit message.

---

## Definition of Done

A feature is complete only when:
- Implementation finished.
- Build succeeds without errors.
- No critical regressions in existing features.
- Architecture layers remain consistent.
- Committed to `develop` branch.

---

## Key Files

| Layer | File |
|-------|------|
| AR HUD | `frontend/src/GlassesHUD.jsx` |
| Main app | `frontend/src/App.jsx` |
| Window manager | `frontend/src/hooks/useWindowManager.js` |
| Device manager | `frontend/src/hooks/useDeviceManager.js` |
| XR adapter | `frontend/src/adapters/XRAdapter.js` |
| Audio (mobile fix) | `frontend/src/hooks/useAudio.js` |
| User prefs | `frontend/src/hooks/useUserPrefs.js` |
| UI components | `frontend/src/components/ui.jsx` |
| AI director | `backend/agents/director.py` |
| AI personality | `backend/agents/personality.py` |
| Provider adapters | `backend/core/adapters.py` |
| Memory (SQLite) | `backend/memory/memory.py` |
| Vision engine | `backend/engines/vision_engine.py` |
| Gesture engine | `frontend/src/engines/gestureEngine.js` |
| Security | `backend/core/security.py` |
| Monitoring | `backend/core/monitor.py` |
| Plugin SDK | `backend/core/plugin_sdk.py` |

---

## Long-Term Platform Targets

Phone → Desktop → XREAL → Android XR → Vehicle → Smart home → Robotics

Every contribution must move the project closer to this vision.

---

## Git Workflow

- Branch: `develop` (features branch from here)
- Commits: conventional commits (`feat:`, `fix:`, `refactor:`, `docs:`)
- Deploy: Railway (backend) + Vercel (frontend) — Albert deploys manually
