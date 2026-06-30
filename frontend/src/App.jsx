import { useRef, useState, useEffect } from 'react'
import { useJarvis } from './hooks/useJarvis'
import JarvisSphere from './components/JarvisSphere'
import Camera from './components/Camera'
import VoiceInput from './components/VoiceInput'
import Results from './components/Results'
import DevicePanel from './components/DevicePanel'
import './App.css'

function getDeviceId() {
  let id = localStorage.getItem('jarvis_device_id')
  if (!id) { id = 'device_' + Math.random().toString(36).slice(2, 8); localStorage.setItem('jarvis_device_id', id) }
  return id
}
const DEVICE_ID = getDeviceId()

const MODES = [
  { id: 'default', label: '💬 Спросить' },
  { id: 'analyze', label: '🔍 Анализ' },
  { id: 'identify', label: '🏷 Что это?' },
  { id: 'translate', label: '🌐 Перевод' },
]

export default function App() {
  const [mode, setMode] = useState('default')
  const [prompt, setPrompt] = useState('')
  const [sendTarget, setSendTarget] = useState(null)
  const [sphereState, setSphereState] = useState('idle')
  const [showCamera, setShowCamera] = useState(false)
  const [listening, setListening] = useState(false)
  const cameraRef = useRef(null)

  const { status, devices, agents, results, loading, audio, lastMsg, analyze, sendTo, broadcast } = useJarvis(DEVICE_ID)

  // Sfääri olek oleneb süsteemi olekust
  useEffect(() => {
    if (listening) setSphereState('listening')
    else if (loading) setSphereState('thinking')
    else if (audio) setSphereState('speaking')
    else setSphereState('idle')
  }, [listening, loading, audio])

  // Pärast häälvastust tagasi idle
  useEffect(() => {
    if (audio) {
      const t = setTimeout(() => setSphereState('idle'), 6000)
      return () => clearTimeout(t)
    }
  }, [audio])

  useEffect(() => {
    if (lastMsg) alert(`📨 ${lastMsg.from}: ${lastMsg.text}`)
  }, [lastMsg])

  function handleAnalyze(voiceText) {
    const image = showCamera ? cameraRef.current?.capture() : null
    const finalPrompt = voiceText || prompt || undefined
    analyze({ image, prompt: finalPrompt, mode, target_devices: sendTarget ? [sendTarget] : [] })
    if (!voiceText) setPrompt('')
  }

  const statusColor = { online: '#ffaa00', connecting: '#ff6600', disconnected: '#333' }[status]
  const stateLabel = { idle: 'В ОЖИДАНИИ', listening: 'СЛУШАЮ, СЭР...', thinking: 'АНАЛИЗИРУЮ...', speaking: 'ОТВЕЧАЮ...' }[sphereState]

  return (
    <div className="app">
      {/* Header */}
      <header className="header">
        <div className="jarvis-logo">
          <div className="logo-ring" style={{ borderColor: statusColor, boxShadow: `0 0 10px ${statusColor}` }} />
          <span className="logo-text">J.A.R.V.I.S</span>
        </div>
        <div className="header-right">
          <span className="status-dot" style={{ background: statusColor }} />
          <span className="status-text">{status.toUpperCase()}</span>
        </div>
      </header>

      {/* Agendid */}
      <div className="agents-bar">
        {agents.map(a => (
          <span key={a.id} className={`agent-chip ${a.enabled ? 'on' : 'off'}`}>{a.name}</span>
        ))}
      </div>

      {/* Peamine vaade — 3D sfäär */}
      <div className="sphere-container">
        <JarvisSphere state={sphereState} />
        <div className="sphere-overlay">
          <div className="state-label">{stateLabel}</div>
          {results.length > 0 && !loading && (
            <div className="sphere-result-preview">
              {results[0]?.response?.slice(0, 120)}{results[0]?.response?.length > 120 ? '...' : ''}
            </div>
          )}
        </div>
        {/* Kaamera toggle */}
        <button className="cam-toggle" onClick={() => setShowCamera(v => !v)} title="Kaamera">
          {showCamera ? '📷 ON' : '📷 OFF'}
        </button>
      </div>

      {/* Kaamera (peidetud vaikimisi) */}
      {showCamera && <Camera ref={cameraRef} />}

      {/* Seadmed */}
      <DevicePanel devices={devices} currentDevice={DEVICE_ID}
        onSendTo={d => setSendTarget(sendTarget === d ? null : d)} />
      {sendTarget && (
        <div className="send-target-bar">
          → Результат на: <strong>{sendTarget}</strong>
          <button onClick={() => setSendTarget(null)}>✕</button>
        </div>
      )}

      {/* Режим */}
      <div className="mode-bar">
        {MODES.map(m => (
          <button key={m.id} className={`mode-btn ${mode === m.id ? 'active' : ''}`} onClick={() => setMode(m.id)}>
            {m.label}
          </button>
        ))}
      </div>

      {/* Ввод */}
      <div className="input-row">
        <input
          className="text-input"
          placeholder="Ваши команды, сэр..."
          value={prompt}
          onChange={e => setPrompt(e.target.value)}
          onKeyDown={e => e.key === 'Enter' && handleAnalyze()}
        />
      </div>

      {/* Кнопки */}
      <div className="controls">
        <button className="btn-analyze" onClick={() => handleAnalyze()} disabled={loading || status !== 'online'}>
          {loading ? '⏳ АНАЛИЗ...' : '⚡ АКТИВИРОВАТЬ'}
        </button>
        <VoiceInput
          onResult={handleAnalyze}
          disabled={loading || status !== 'online'}
          onListeningChange={setListening}
        />
        <button className="btn-broadcast" onClick={() => broadcast(prompt || 'JARVIS активирован')}
          disabled={status !== 'online'} title="Kõigile seadmetele">📡</button>
      </div>

      {/* Tulemused */}
      <Results results={results} loading={loading} audio={audio} />
    </div>
  )
}
