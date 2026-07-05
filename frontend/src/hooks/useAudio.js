/**
 * Albert OS — Audio playback hook
 *
 * Mobiilibrowserid blokeerivad autoplay ilma kasutaja žestita.
 * Lahendus:
 *   1. Esimese touch/click-i peale unlock AudioContext
 *   2. Mängi heli läbi AudioContext.decodeAudioData (mitte new Audio())
 *   3. Tagastab unlocked=true kui mäng on lubatud
 */
import { useEffect, useRef, useState, useCallback } from 'react'

let _ctx = null
function getAudioContext() {
  if (!_ctx) _ctx = new (window.AudioContext || window.webkitAudioContext)()
  return _ctx
}

export function useAudio() {
  const [unlocked, setUnlocked] = useState(false)
  const [playing, setPlaying]   = useState(false)
  const sourceRef = useRef(null)

  // Unlock AudioContext esimese kasutaja žestiga
  useEffect(() => {
    function unlock() {
      const ctx = getAudioContext()
      if (ctx.state === 'suspended') {
        ctx.resume().then(() => setUnlocked(true)).catch(() => {})
      } else {
        setUnlocked(true)
      }
    }
    document.addEventListener('touchstart', unlock, { once: true, passive: true })
    document.addEventListener('click',      unlock, { once: true })
    document.addEventListener('keydown',    unlock, { once: true })
    return () => {
      document.removeEventListener('touchstart', unlock)
      document.removeEventListener('click',      unlock)
      document.removeEventListener('keydown',    unlock)
    }
  }, [])

  /**
   * Mängi base64-kodeeritud MP3 andmed.
   * @param {string} base64 — audio_mpeg base64 string
   * @param {function} onEnded — kutsutakse lõpus
   */
  const playBase64 = useCallback(async (base64, onEnded) => {
    try {
      const ctx = getAudioContext()
      if (ctx.state === 'suspended') await ctx.resume()

      // Konverdi base64 → ArrayBuffer
      const binary = atob(base64)
      const buf = new ArrayBuffer(binary.length)
      const view = new Uint8Array(buf)
      for (let i = 0; i < binary.length; i++) view[i] = binary.charCodeAt(i)

      const decoded = await ctx.decodeAudioData(buf)
      const source  = ctx.createBufferSource()
      source.buffer = decoded
      source.connect(ctx.destination)

      // Peata eelmine
      if (sourceRef.current) {
        try { sourceRef.current.stop() } catch (_) {}
      }
      sourceRef.current = source
      setPlaying(true)

      source.onended = () => {
        setPlaying(false)
        if (onEnded) onEnded()
      }
      source.start(0)
    } catch (err) {
      console.warn('[useAudio] playback failed:', err)
      // Fallback: new Audio() — töötab desktopil
      try {
        const binary = atob(base64)
        const view = new Uint8Array(binary.length)
        for (let i = 0; i < binary.length; i++) view[i] = binary.charCodeAt(i)
        const blob = new Blob([view], { type: 'audio/mpeg' })
        const url  = URL.createObjectURL(blob)
        const a    = new Audio(url)
        a.onended = () => { setPlaying(false); URL.revokeObjectURL(url); if (onEnded) onEnded() }
        a.onerror = () => { setPlaying(false); URL.revokeObjectURL(url) }
        await a.play()
        setPlaying(true)
      } catch (_) { setPlaying(false) }
    }
  }, [])

  const stop = useCallback(() => {
    if (sourceRef.current) {
      try { sourceRef.current.stop() } catch (_) {}
      sourceRef.current = null
    }
    setPlaying(false)
  }, [])

  return { unlocked, playing, playBase64, stop }
}
