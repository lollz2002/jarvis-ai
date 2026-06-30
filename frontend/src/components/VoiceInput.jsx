import { useState, useRef, useEffect } from 'react'

export default function VoiceInput({ onResult, disabled, onListeningChange }) {
  const [listening, setListening] = useState(false)
  const recogRef = useRef(null)

  useEffect(() => { onListeningChange?.(listening) }, [listening])

  function toggle() {
    if (listening) { recogRef.current?.stop(); return }
    const SR = window.SpeechRecognition || window.webkitSpeechRecognition
    if (!SR) { alert('Используй Chrome для распознавания речи.'); return }
    const r = new SR()
    r.lang = 'ru-RU'
    r.interimResults = false
    r.maxAlternatives = 1
    r.onstart = () => setListening(true)
    r.onend = () => setListening(false)
    r.onerror = () => setListening(false)
    r.onresult = e => onResult(e.results[0][0].transcript)
    r.start()
    recogRef.current = r
  }

  return (
    <button className={`btn-voice ${listening ? 'listening' : ''}`} onClick={toggle} disabled={disabled}>
      {listening ? '🔴 Слушаю, сэр...' : '🎤 Говорите, сэр'}
    </button>
  )
}
