import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './index.css'
import App from './App.jsx'
import GlassesHUD from './GlassesHUD.jsx'

// ── Shell selection — runs synchronously before React mounts anything ──────────
// This is the only place that decides which runtime to boot.
// Rules (in priority order):
//   1. URL path /glasses             → Glasses shell
//   2. ?ar=1 query param             → Glasses shell
//   3. albert_os_prefs.glassesMode   → Glasses shell
//   4. XREAL hardware screen (1920×1080 non-mobile) → Glasses shell
//   5. Everything else               → Phone shell

function resolveShell() {
  if (window.location.pathname === '/glasses') return 'glasses'
  if (new URLSearchParams(window.location.search).get('ar') === '1') return 'glasses'

  try {
    const p = JSON.parse(localStorage.getItem('albert_os_prefs') || '{}')
    if (p.glassesMode === true) return 'glasses'
  } catch { /* ignore */ }

  // XREAL Air 2 Ultra connects via USB-C at 1920×1080 on a non-mobile host
  const ua = navigator.userAgent.toLowerCase()
  const isMobile = /iphone|android|ipad/.test(ua)
  if (!isMobile && window.screen.width === 1920 && window.screen.height === 1080) {
    // Persist so next load is instant
    try {
      const p = JSON.parse(localStorage.getItem('albert_os_prefs') || '{}')
      localStorage.setItem('albert_os_prefs', JSON.stringify({ ...p, glassesMode: true }))
    } catch { /* ignore */ }
    return 'glasses'
  }

  return 'phone'
}

const SHELL = resolveShell()

// Enforce scroll-lock at document level before first paint — glasses runtime
// must never scroll. Phone shell resets these to defaults.
if (SHELL === 'glasses') {
  document.documentElement.style.overflow = 'hidden'
  document.documentElement.style.height   = '100%'
  document.body.style.overflow = 'hidden'
  document.body.style.height   = '100%'
  document.body.style.margin   = '0'
  document.body.style.padding  = '0'
  // Push real URL to /glasses so history/devtools reflect the active shell
  if (window.location.pathname !== '/glasses') {
    window.history.replaceState(null, '', '/glasses')
  }
}

createRoot(document.getElementById('root')).render(
  <StrictMode>
    {SHELL === 'glasses' ? <GlassesHUD /> : <App />}
  </StrictMode>
)
