import { useRef, useState, useEffect } from 'react'
import { useJarvis } from './hooks/useJarvis'
import { useDeviceManager } from './hooks/useDeviceManager'
import { useAudio } from './hooks/useAudio'
import { useUserPrefs } from './hooks/useUserPrefs'
import JarvisSphere from './components/JarvisSphere'
import Camera from './components/Camera'
import VoiceInput from './components/VoiceInput'
import Results from './components/Results'
import DevicePanel from './components/DevicePanel'
import FileUpload from './components/FileUpload'
import RemoteDesktop from './components/RemoteDesktop'
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
  const [attachedFile, setAttachedFile] = useState(null)
  const [sendTarget, setSendTarget] = useState(null)
  const [sphereState, setSphereState] = useState('idle')
  const [showCamera, setShowCamera] = useState(false)
  const [listening, setListening] = useState(false)
  const [muted, setMuted] = useState(false)
  const [incomingMsg, setIncomingMsg] = useState(null)
  const cameraRef = useRef(null)
  const audioRef = useRef(null)

  const { status, devices, agents, results, loading, audio, lastMsg, analyze, sendTo, broadcast, wsRef } = useJarvis(DEVICE_ID)
  const { device, switchToAR } = useDeviceManager()
  const { unlocked, playing: audioPlaying, playBase64, stop: stopAudio } = useAudio()
  const { prefs, setPrefs } = useUserPrefs()

  // XREAL auto-detect: DeviceManager sets type='glasses' for 1920×1080 non-mobile, /glasses, or ?ar=1
  const isXREALDetected = device.type === 'glasses' || device.isAR

  // If Glasses Mode pref is active, redirect to /glasses immediately
  useEffect(() => {
    if (prefs.glassesMode && window.location.pathname !== '/glasses') {
      window.location.replace('/glasses')
    }
  }, [])

  function toggleGlassesMode() {
    if (prefs.glassesMode) {
      setPrefs({ glassesMode: false })
    } else {
      setPrefs({ glassesMode: true })
      window.location.href = '/glasses'
    }
  }

  // Sfääri olek oleneb süsteemi olekust
  useEffect(() => {
    if (listening) setSphereState('listening')
    else if (loading) setSphereState('thinking')
    else if (audio) setSphereState('speaking')
    else setSphereState('idle')
  }, [listening, loading, audio])

  // Audio mängimine + interrupt tugi (useAudio = mobiili-autoplay fix)
  useEffect(() => {
    if (!audio || muted) return
    playBase64(audio, () => setSphereState('idle'))
    setSphereState('speaking')
    const t = setTimeout(() => setSphereState('idle'), 12000)
    return () => { stopAudio(); clearTimeout(t) }
  }, [audio])

  function handleInterrupt() {
    stopAudio()
    setSphereState('idle')
  }

  useEffect(() => {
    if (lastMsg) {
      setIncomingMsg(`📨 ${lastMsg.from}: ${lastMsg.text}`)
      setTimeout(() => setIncomingMsg(null), 8000)
    }
  }, [lastMsg])

  function getCameraFrame() {
    return cameraRef.current?.capture() ?? null
  }

  function handleAnalyze(voiceText, frameFromVoice) {
    let image = frameFromVoice || (showCamera ? cameraRef.current?.capture() : null)
    let finalPrompt = voiceText || prompt || undefined

    // Lisa manustatud fail
    if (attachedFile) {
      if (attachedFile.type === 'image') {
        image = attachedFile.data
      } else {
        finalPrompt = `${finalPrompt || 'Analysи этот файл'}\n\n[Файл: ${attachedFile.name}]\n${attachedFile.data?.slice(0, 3000)}`
      }
      setAttachedFile(null)
    }

    if (!finalPrompt && !image) return
    analyze({ image, prompt: finalPrompt, mode, target_devices: sendTarget ? [sendTarget] : [] })
    if (!voiceText) setPrompt('')
  }

  function handleFile(file) {
    setAttachedFile(file)
    setPrompt(p => p || `Analysи файл: ${file.name}`)
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
          {/* Glasses Mode toggle — always visible, prominent when XREAL detected */}
          <button
            onClick={toggleGlassesMode}
            title={prefs.glassesMode ? 'Välju Glasses Mode\'ist' : 'Lülita Glasses Mode sisse (XREAL / AR)'}
            style={{
              background: prefs.glassesMode ? '#ffaa0025' : isXREALDetected ? '#00aaff20' : 'none',
              border: `1px solid ${prefs.glassesMode ? '#ffaa0080' : isXREALDetected ? '#00aaff80' : '#ffaa0040'}`,
              color: prefs.glassesMode ? '#ffaa00' : isXREALDetected ? '#00aaff' : '#ffaa0060',
              borderRadius: 5, padding: '2px 8px', cursor: 'pointer',
              fontSize: '0.65rem', letterSpacing: 1, fontFamily: 'inherit',
              animation: isXREALDetected && !prefs.glassesMode ? 'glassesGlow 1.4s infinite' : 'none',
            }}
          >
            {prefs.glassesMode ? '🥽 GLASSES ON' : isXREALDetected ? '🥽 XREAL' : '🥽'}
          </button>
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
        <FileUpload onFile={handleFile} disabled={status !== 'online'} />
        <input
          className="text-input"
          placeholder="Ваши команды, сэр..."
          value={prompt}
          onChange={e => setPrompt(e.target.value)}
          onKeyDown={e => e.key === 'Enter' && handleAnalyze()}
        />
        {attachedFile && (
          <span className="file-badge" onClick={() => setAttachedFile(null)} title="Eemalda">
            📎 {attachedFile.name} ✕
          </span>
        )}
      </div>

      {/* Кнопки */}
      <div className="controls">
        <button className="btn-analyze" onClick={() => handleAnalyze()} disabled={loading || status !== 'online'}>
          {loading ? '⏳ АНАЛИЗ...' : '⚡ АКТИВИРОВАТЬ'}
        </button>
        <VoiceInput
          onResult={handleAnalyze}
          disabled={status !== 'online'}
          onListeningChange={setListening}
          getCameraFrame={showCamera ? getCameraFrame : null}
          onInterrupt={handleInterrupt}
          lastResponse={results?.[0]?.response || ''}
        />
        <button className="btn-broadcast" onClick={() => broadcast(prompt || 'JARVIS активирован')}
          disabled={status !== 'online'} title="Kõigile seadmetele">📡</button>
      </div>

      {/* Kaugjuhtimine */}
      <RemoteDesktop ws={wsRef?.current} onCommand={analyze} />

      {/* XREAL auto-detect banner */}
      {isXREALDetected && !prefs.glassesMode && (
        <div style={{ background: '#00aaff12', border: '1px solid #00aaff50', borderRadius: 6, padding: '8px 14px', margin: '0 0 8px', fontSize: '0.8rem', color: '#00aaff', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <span>🥽 XREAL tuvastatud — lülita Glasses Mode sisse täisekraani AR liidese jaoks</span>
          <button onClick={toggleGlassesMode} style={{ background: '#00aaff20', border: '1px solid #00aaff80', color: '#00aaff', borderRadius: 5, padding: '3px 10px', cursor: 'pointer', fontSize: '0.75rem', marginLeft: 12, fontFamily: 'inherit', letterSpacing: 1 }}>
            AKTIVEERI
          </button>
        </div>
      )}

      {/* Sissetulev sõnum teistelt seadmetelt */}
      {incomingMsg && (
        <div style={{ background: '#1a1a1a', border: '1px solid #ffaa0060', borderRadius: 6, padding: '8px 14px', margin: '0 0 8px', fontSize: '0.8rem', color: '#ffaa00', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <span>{incomingMsg}</span>
          <button onClick={() => setIncomingMsg(null)} style={{ background: 'none', border: 'none', color: '#888', cursor: 'pointer', fontSize: '1rem' }}>✕</button>
        </div>
      )}

      {/* Tulemused */}
      <Results results={results} loading={loading} audio={audio} />

      {/* Build version footer */}
      <div style={{ textAlign: 'center', padding: '6px 0 2px', fontSize: '0.55rem', color: '#333', letterSpacing: 1 }}>
        ALBERT OS v{typeof __APP_VERSION__ !== 'undefined' ? __APP_VERSION__ : '1.1.0'} · {typeof __GIT_HASH__ !== 'undefined' ? __GIT_HASH__ : 'dev'}
      </div>
    </div>
  )
}
