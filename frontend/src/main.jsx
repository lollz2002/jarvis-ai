import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './index.css'
import App from './App.jsx'
import GlassesHUD from './GlassesHUD.jsx'

// ── Shell selection — runs synchronously before React mounts anything ──────────
// This is the only place that decides which runtime to boot.
// Rules (in priority order):
//   1. URL path /glasses                        → Glasses shell
//   2. ?ar=1 query param                        → Glasses shell
//   3. albert_os_prefs.glassesMode persisted    → Glasses shell
//   4. XREAL via phone (landscape ratio > 1.6)  → Glasses shell
//   5. XREAL via PC (1920×1080 non-mobile)      → Glasses shell
//   6. Everything else                          → Phone shell

function resolveShell() {
  if (window.location.pathname === '/glasses') return 'glasses'
  if (new URLSearchParams(window.location.search).get('ar') === '1') return 'glasses'

  try {
    const p = JSON.parse(localStorage.getItem('albert_os_prefs') || '{}')
    if (p.glassesMode === true) return 'glasses'
  } catch { /* ignore */ }

  const ua  = navigator.userAgent.toLowerCase()
  const isMobile = /iphone|android|ipad/.test(ua)
  const w   = window.screen.width
  const h   = window.screen.height
  const isLandscape = w > h
  const ratio = w / h

  // XREAL ühendatud telefoniga USB-C kaudu → telefon läheb landscape-i, ratio > 1.6
  // Tavalisel mobiilil portrait-is ratio < 1 — see ei käivitu kogemata
  const isXREALPhone = isMobile && isLandscape && ratio > 1.6

  // XREAL ühendatud PC/Mac-iga — ekraan on täpselt 1920×1080
  const isXREALPC = !isMobile && w === 1920 && h === 1080

  if (isXREALPhone || isXREALPC) {
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
