/**
 * Albert OS — XR Session Recovery Hook
 * Spek: 26_AR_RUNTIME_AND_RENDER_ENGINE.md
 *
 * Vastutusalad:
 *   - Seire: XR adapteri muutused (ühendus kadus / taastus)
 *   - Disconnect: salvesta workspace olek localStorage-sse
 *   - Reconnect: taasta viimane workspace automaatselt
 *   - FPS mõõtmine: requestAnimationFrame põhine
 */
import { useEffect, useRef, useState, useCallback } from 'react'

const SESSION_KEY = 'albert_os_xr_session'

function saveSession(data) {
  try {
    localStorage.setItem(SESSION_KEY, JSON.stringify({ ...data, savedAt: Date.now() }))
  } catch (_) {}
}

function loadSession() {
  try {
    const raw = localStorage.getItem(SESSION_KEY)
    if (!raw) return null
    const d = JSON.parse(raw)
    // Eira vanemaid kui 4 tundi
    if (Date.now() - d.savedAt > 4 * 60 * 60 * 1000) return null
    return d
  } catch { return null }
}

/**
 * useXRSession — XR seansi haldus ja taastamine
 *
 * @param {object} opts
 * @param {string} opts.currentProfile   — aktiivne XR profiil ('xreal', 'phone', ...)
 * @param {string} opts.currentWorkspace — aktiivne workspace ('home', 'boat', ...)
 * @param {object} opts.wins             — akende olek useWindowManager-ist
 * @param {function} opts.onRestore      — (sessionData) → kutsutakse reconnect-il
 *
 * @returns {{ fps, sessionRestored, clearSession }}
 */
export function useXRSession({ currentProfile, currentWorkspace, wins, onRestore }) {
  const prevProfileRef   = useRef(currentProfile)
  const [fps, setFps]    = useState(null)
  const [sessionRestored, setSessionRestored] = useState(false)
  const fpsFrames = useRef(0)
  const fpsStart  = useRef(performance.now())
  const rafId     = useRef(null)

  // ── FPS mõõtmine ────────────────────────────────────────────────────────────
  useEffect(() => {
    function tick() {
      fpsFrames.current += 1
      const now = performance.now()
      const elapsed = now - fpsStart.current
      if (elapsed >= 1000) {
        setFps(Math.round((fpsFrames.current * 1000) / elapsed))
        fpsFrames.current = 0
        fpsStart.current  = now
      }
      rafId.current = requestAnimationFrame(tick)
    }
    rafId.current = requestAnimationFrame(tick)
    return () => cancelAnimationFrame(rafId.current)
  }, [])

  // ── XR profiiliga seotud disconnect/reconnect tuvastus ────────────────────
  useEffect(() => {
    const prev = prevProfileRef.current

    // Disconnect: XR profiil kadus (xreal/android_xr → phone/desktop)
    const wasXR = prev === 'xreal' || prev === 'android_xr'
    const isXR  = currentProfile === 'xreal' || currentProfile === 'android_xr'

    if (wasXR && !isXR) {
      // Salvesta praegune sessiooni olek
      saveSession({
        workspace: currentWorkspace,
        openWins:  Object.entries(wins)
          .filter(([, w]) => w?.open)
          .map(([id]) => id),
        profile: prev,
      })
    }

    // Reconnect: XR profiil taastus
    if (!wasXR && isXR) {
      const saved = loadSession()
      if (saved && onRestore) {
        onRestore(saved)
        setSessionRestored(true)
        setTimeout(() => setSessionRestored(false), 5000)
      }
    }

    prevProfileRef.current = currentProfile
  }, [currentProfile]) // eslint-disable-line react-hooks/exhaustive-deps

  const clearSession = useCallback(() => {
    localStorage.removeItem(SESSION_KEY)
  }, [])

  return { fps, sessionRestored, clearSession }
}

/**
 * useXRFeatures — runtime feature detection (37_ANDROID_XR_IMPLEMENTATION_BIBLE.md)
 * Kontrollib mis XR võimalused on seadmel saadaval.
 * Toetamata funktsioonid keelatakse automaatselt.
 */
export function useXRFeatures() {
  const [features, setFeatures] = useState(null)

  useEffect(() => {
    import('../adapters/XRAdapter.js').then(({ detectXRFeatures }) => {
      detectXRFeatures().then(setFeatures)
    })
  }, [])

  return features   // null kuni tuvastamine lõpeb
}

/**
 * useFPS — lihtne FPS hook teistele komponentidele
 */
export function useFPS() {
  const [fps, setFps] = useState(null)
  const frames = useRef(0)
  const start  = useRef(performance.now())
  const rafId  = useRef(null)

  useEffect(() => {
    function tick() {
      frames.current += 1
      const now = performance.now()
      if (now - start.current >= 1000) {
        setFps(Math.round((frames.current * 1000) / (now - start.current)))
        frames.current = 0
        start.current  = now
      }
      rafId.current = requestAnimationFrame(tick)
    }
    rafId.current = requestAnimationFrame(tick)
    return () => cancelAnimationFrame(rafId.current)
  }, [])

  return fps
}
