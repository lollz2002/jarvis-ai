/**
 * Albert OS — Voice Engine (07_VOICE_ENGINE.md)
 * Wake word, interrupt, mute, repeat, language switch, subtitles
 */
import { useState, useRef, useEffect, useCallback } from 'react'

const WAKE_WORDS = ['jarvis', 'джарвис', 'ярвис', 'jarvis']
const LANGS = [
  { code: 'ru-RU', label: 'RU' },
  { code: 'et-EE', label: 'ET' },
  { code: 'en-US', label: 'EN' },
]

export default function VoiceInput({
  onResult, disabled, onListeningChange, getCameraFrame,
  onInterrupt,       // callback kui kasutaja katkestab TTS-i
  lastResponse = '', // viimane JARVIS vastus kordusnupuks
}) {
  const [active, setActive]       = useState(false)
  const [interim, setInterim]     = useState('')
  const [langIdx, setLangIdx]     = useState(0)
  const [muted, setMuted]         = useState(false)
  const [wakeMode, setWakeMode]   = useState(false) // ainult wake word kuulab
  const recogRef    = useRef(null)
  const activeRef   = useRef(false)
  const wakeModeRef = useRef(false)
  const restartTimer = useRef(null)
  const currentLang = LANGS[langIdx]

  useEffect(() => { onListeningChange?.(active) }, [active])

  // ── Kõne katkestamine kui kasutaja räägib TTS ajal ───────────────────────
  function interruptIfSpeaking() {
    onInterrupt?.()
  }

  const startRecognition = useCallback(() => {
    if (!activeRef.current) return
    const SR = window.SpeechRecognition || window.webkitSpeechRecognition
    if (!SR) return

    const r = new SR()
    r.lang = currentLang.code
    r.interimResults = true
    r.maxAlternatives = 1
    r.continuous = false

    r.onstart = () => setActive(true)

    r.onresult = (e) => {
      let itr = '', fin = ''
      for (let i = e.resultIndex; i < e.results.length; i++) {
        if (e.results[i].isFinal) fin += e.results[i][0].transcript
        else itr += e.results[i][0].transcript
      }

      // Wake word tuvastus interim tekstist
      const combined = (itr + fin).toLowerCase()
      const wakeDetected = WAKE_WORDS.some(w => combined.includes(w))

      if (wakeModeRef.current) {
        // Wake word režiimis — ainult wake word aktiveerib
        if (wakeDetected) {
          setWakeMode(false)
          wakeModeRef.current = false
          activeRef.current = true
          setInterim('🎤 Слушаю...')
        }
        return
      }

      setInterim(itr)

      if (fin.trim()) {
        setInterim('')
        // Katkesta TTS kui kasutaja räägib
        interruptIfSpeaking()
        const frame = getCameraFrame?.()
        onResult(fin.trim(), frame)
      }
    }

    r.onend = () => {
      setInterim('')
      if (activeRef.current) {
        restartTimer.current = setTimeout(startRecognition, 200)
      } else {
        setActive(false)
      }
    }

    r.onerror = (e) => {
      if (e.error === 'no-speech') {
        if (activeRef.current) restartTimer.current = setTimeout(startRecognition, 300)
      } else if (e.error === 'not-allowed') {
        activeRef.current = false
        setActive(false)
        alert('Mikrofon pole lubatud. Luba mikrofon brauseri seadetes.')
      }
    }

    recogRef.current = r
    try { r.start() } catch (_) {}
  }, [onResult, getCameraFrame, currentLang.code])

  function toggle() {
    if (activeRef.current) {
      activeRef.current = false
      wakeModeRef.current = false
      clearTimeout(restartTimer.current)
      recogRef.current?.abort()
      setActive(false)
      setWakeMode(false)
      setInterim('')
    } else {
      activeRef.current = true
      startRecognition()
    }
  }

  // Wake word režiim — kuulab passiivselt ainult "Jarvis"
  function toggleWakeMode() {
    if (wakeModeRef.current) {
      wakeModeRef.current = false
      activeRef.current = false
      setWakeMode(false)
      recogRef.current?.abort()
      setActive(false)
    } else {
      wakeModeRef.current = true
      activeRef.current = true
      setWakeMode(true)
      startRecognition()
    }
  }

  // Keele tsükkel ET → EN → RU → ET
  function cycleLang() {
    const wasActive = activeRef.current
    if (wasActive) {
      recogRef.current?.abort()
      clearTimeout(restartTimer.current)
    }
    setLangIdx(i => (i + 1) % LANGS.length)
    if (wasActive) {
      setTimeout(() => { activeRef.current = true; startRecognition() }, 300)
    }
  }

  // Mute väljund
  function toggleMute() {
    setMuted(m => {
      if (!m) onInterrupt?.() // mute → katkesta kohe
      return !m
    })
  }

  // Korda viimast vastust
  function repeatLast() {
    if (lastResponse) onResult(`[REPEAT] ${lastResponse}`, null)
  }

  useEffect(() => {
    return () => {
      activeRef.current = false
      wakeModeRef.current = false
      clearTimeout(restartTimer.current)
      recogRef.current?.abort()
    }
  }, [])

  // Keel muutus → taaskäivita
  useEffect(() => {
    if (activeRef.current) {
      recogRef.current?.abort()
      clearTimeout(restartTimer.current)
      restartTimer.current = setTimeout(startRecognition, 300)
    }
  }, [langIdx])

  return (
    <div className="voice-wrap">
      {/* Peamine mikrofoni nupp */}
      <button
        className={`btn-voice ${active && !wakeMode ? 'listening' : ''} ${wakeMode ? 'wake-mode' : ''}`}
        onClick={toggle}
        disabled={disabled}
        title={active ? 'Peata mikrofon' : 'Käivita mikrofon'}
      >
        {active && !wakeMode ? '🔴 СЛУШАЮ' : '🎤 МИК'}
      </button>

      {/* Kontrollriba */}
      <div style={{ display: 'flex', gap: 4, marginTop: 4, flexWrap: 'wrap', justifyContent: 'center' }}>
        {/* Wake word nupp */}
        <button
          onClick={toggleWakeMode}
          disabled={disabled}
          title='Wake word "Jarvis" — passiivne kuulamine'
          style={miniBtn(wakeMode ? '#ff6600' : '#333')}
        >
          {wakeMode ? '👁 JARVIS' : '👁'}
        </button>

        {/* Keelevalija */}
        <button onClick={cycleLang} disabled={disabled} title="Vaheta keelt" style={miniBtn('#333')}>
          {currentLang.label}
        </button>

        {/* Mute */}
        <button onClick={toggleMute} disabled={disabled} title={muted ? 'Helesta' : 'Vaigista'} style={miniBtn(muted ? '#ff4444' : '#333')}>
          {muted ? '🔇' : '🔊'}
        </button>

        {/* Korda viimast vastust */}
        {lastResponse && (
          <button onClick={repeatLast} disabled={disabled} title="Korda viimast vastust" style={miniBtn('#333')}>
            ↺
          </button>
        )}
      </div>

      {/* Interim subtiitrid */}
      {interim && <div className="interim-text">"{interim}"</div>}

      {/* Mute hoiatus */}
      {muted && <div style={{ fontSize: '0.6rem', color: '#ff4444', letterSpacing: 1 }}>VAIGISTATUD</div>}
    </div>
  )
}

function miniBtn(borderColor) {
  return {
    background: 'none',
    border: `1px solid ${borderColor}`,
    color: borderColor === '#333' ? '#888' : borderColor,
    borderRadius: 4,
    padding: '2px 7px',
    cursor: 'pointer',
    fontSize: '0.7rem',
    fontFamily: 'Courier New',
  }
}
