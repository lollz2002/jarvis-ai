import { useEffect, useRef } from 'react'

function speakText(text) {
  if (!window.speechSynthesis) return
  window.speechSynthesis.cancel()
  const utt = new SpeechSynthesisUtterance(text)
  utt.lang = 'ru-RU'
  utt.rate = 0.9
  utt.pitch = 0.85
  utt.volume = 1.0
  // Vali venekeelne hääl kui saadaval
  const voices = window.speechSynthesis.getVoices()
  const ruVoice = voices.find(v => v.lang.startsWith('ru')) || voices.find(v => v.lang.startsWith('en'))
  if (ruVoice) utt.voice = ruVoice
  window.speechSynthesis.speak(utt)
}

export default function Results({ results, loading, audio }) {
  const audioRef = useRef(null)
  const spokenRef = useRef(null)

  // ElevenLabs hääl (kui saadaval)
  useEffect(() => {
    if (audio) {
      const blob = new Blob([Uint8Array.from(atob(audio), c => c.charCodeAt(0))], { type: 'audio/mpeg' })
      const url = URL.createObjectURL(blob)
      if (audioRef.current) { audioRef.current.src = url; audioRef.current.play() }
    }
  }, [audio])

  // Brauser TTS fallback — räägib esimese eduka vastuse
  useEffect(() => {
    if (!results.length || audio) return
    const first = results.find(r => r.response && !r.error)
    if (first && first.response !== spokenRef.current) {
      spokenRef.current = first.response
      // Laadi hääled (mõnikord tuleb oodata)
      if (window.speechSynthesis.getVoices().length === 0) {
        window.speechSynthesis.onvoiceschanged = () => speakText(first.response)
      } else {
        speakText(first.response)
      }
    }
  }, [results, audio])

  return (
    <div className="results">
      <audio ref={audioRef} style={{ display: 'none' }} />
      {loading && (
        <div className="loading-wrap">
          <div className="hud-ring" />
          <p className="loading-text">МОИ СИСТЕМЫ АНАЛИЗИРУЮТ, СЭР...</p>
        </div>
      )}
      {results.map(r => (
        <div key={r.id} className={`result-card ${r.error ? 'err' : ''}`}>
          <div className="result-head">
            <span className="result-name">{r.name}</span>
            {r.ms && <span className="result-ms">{r.ms}ms</span>}
          </div>
          <p className="result-text">{r.error ? `⚠ ${r.error}` : r.response}</p>
        </div>
      ))}
    </div>
  )
}
