/**
 * Albert OS — AR HUD v3
 * Spek: 08_AR_UI_BIBLE.md
 * Layout: Top Bar | Left Panel | Center | Right Panel | Bottom Dock
 */
import { useRef, useState, useEffect, useCallback } from 'react'
import { useJarvis } from './hooks/useJarvis'
import JarvisSphere from './components/JarvisSphere'
import {
  attachTouchAdapter, detachTouchAdapter,
  onGesture, setSafetyContext,
  GESTURES, WS_ORDER, getGestureFeedback,
} from './engines/gestureEngine'

// ── Värvid (08_AR_UI_BIBLE.md) ────────────────────────────────────────────────
const C = {
  bg:       '#00000099',
  border:   '#ffffff18',
  blue:     '#3b82f6',   // system
  orange:   '#f97316',   // AI
  green:    '#22c55e',   // success
  yellow:   '#eab308',   // warning
  red:      '#ef4444',   // critical
  text:     '#f1f5f9',
  textDim:  '#94a3b8',
  gold:     '#ffaa00',
}

const font = "'Courier New', monospace"

function getDeviceId() {
  let id = localStorage.getItem('jarvis_device_id')
  if (!id) { id = 'glasses_' + Math.random().toString(36).slice(2,8); localStorage.setItem('jarvis_device_id', id) }
  return id
}

// ── Notifikatsiooni süsteem ───────────────────────────────────────────────────
let _notifId = 0
function useNotifications() {
  const [notifs, setNotifs] = useState([])
  const add = useCallback((msg, level = 'info') => {
    const id = ++_notifId
    setNotifs(n => [{ id, msg, level, ts: Date.now() }, ...n.slice(0, 9)])
    if (level !== 'critical') setTimeout(() => setNotifs(n => n.filter(x => x.id !== id)), 8000)
  }, [])
  const dismiss = useCallback((id) => setNotifs(n => n.filter(x => x.id !== id)), [])
  return { notifs, add, dismiss }
}

const NOTIF_COLOR = { critical: C.red, important: C.yellow, info: C.blue, success: C.green }

// ── Workspaces ────────────────────────────────────────────────────────────────
const WORKSPACES = {
  home:     { label: '🏠', name: 'Kodu',    wins: { jarvis:true, clock:true, notes:true } },
  workshop: { label: '🔧', name: 'Töökoda', wins: { jarvis:true, camera:true, browser:true } },
  office:   { label: '💼', name: 'Kontor',  wins: { jarvis:true, browser:true, notes:true } },
  coding:   { label: '💻', name: 'Kood',    wins: { jarvis:true, browser:true, notes:true } },
  boat:     { label: '⛵', name: 'Paat',    wins: { jarvis:true, camera:true, browser:true } },
  driving:  { label: '🚗', name: 'Sõit',    wins: { jarvis:true, clock:true } },
  walking:  { label: '🚶', name: 'Kõndimine', wins: { jarvis:true } },
}

const WIN_DEFS = {
  jarvis:  { title: 'JARVIS',    icon: '🤖', defaultPos: { x: 320, y: 80 },  w: 320, h: 340 },
  browser: { title: 'БРАУЗЕР',   icon: '🌐', defaultPos: { x: 660, y: 80 },  w: 480, h: 360 },
  camera:  { title: 'КАМЕРА',    icon: '📷', defaultPos: { x: 320, y: 430 }, w: 320, h: 220 },
  notes:   { title: 'ЗАМЕТКИ',   icon: '📝', defaultPos: { x: 1160, y: 80 }, w: 260, h: 280 },
  youtube: { title: 'YOUTUBE',   icon: '▶',  defaultPos: { x: 660, y: 80 },  w: 480, h: 340 },
  clock:   { title: 'ВРЕМЯ',     icon: '🕐', defaultPos: { x: 1160, y: 380 }, w: 200, h: 90  },
  plugins: { title: 'PLUGINAD',  icon: '🔌', defaultPos: { x: 660,  y: 430 }, w: 320, h: 280 },
}

// ── Ujuv aken ─────────────────────────────────────────────────────────────────
function FloatWin({ id, title, icon, open, minimized, children, onClose, onMinimize, defaultPos, defaultW, defaultH }) {
  const [pos, setPos]   = useState(defaultPos)
  const [size, setSize] = useState({ w: defaultW, h: defaultH })
  const [opacity, setOpacity] = useState(0.95)
  const drag   = useRef(null)
  const rsz    = useRef(null)

  if (!open) return null

  function onDragStart(e) {
    if (e.target.closest('.wc') || e.target.closest('.rh')) return
    drag.current = { sx: e.clientX - pos.x, sy: e.clientY - pos.y }
    const mv = e2 => { if (drag.current) setPos({ x: e2.clientX - drag.current.sx, y: e2.clientY - drag.current.sy }) }
    const up = () => { drag.current = null; window.removeEventListener('mousemove', mv); window.removeEventListener('mouseup', up) }
    window.addEventListener('mousemove', mv); window.addEventListener('mouseup', up)
  }
  function onRszStart(e) {
    e.stopPropagation()
    rsz.current = { sx: e.clientX, sy: e.clientY, w: size.w, h: size.h }
    const mv = e2 => { if (rsz.current) setSize({ w: Math.max(180, rsz.current.w + e2.clientX - rsz.current.sx), h: Math.max(80, rsz.current.h + e2.clientY - rsz.current.sy) }) }
    const up = () => { rsz.current = null; window.removeEventListener('mousemove', mv); window.removeEventListener('mouseup', up) }
    window.addEventListener('mousemove', mv); window.addEventListener('mouseup', up)
  }

  return (
    <div style={{
      position: 'absolute', left: pos.x, top: pos.y,
      width: size.w, height: minimized ? 36 : size.h,
      background: C.bg, border: `1px solid ${C.border}`,
      borderRadius: 10, overflow: 'hidden',
      backdropFilter: 'blur(16px)', opacity,
      display: 'flex', flexDirection: 'column',
      transition: 'height 0.2s, opacity 0.15s',
      animation: 'fadeIn 0.2s ease',
      zIndex: 20,
    }}>
      {/* Tiitelriba */}
      <div onMouseDown={onDragStart} style={{
        display: 'flex', alignItems: 'center', gap: 7, padding: '5px 10px',
        background: '#ffffff08', borderBottom: `1px solid ${C.border}`,
        cursor: 'grab', userSelect: 'none', flexShrink: 0,
      }}>
        <span style={{ fontSize: 13 }}>{icon}</span>
        <span style={{ flex: 1, fontSize: 10, color: C.orange, letterSpacing: 2, fontFamily: font }}>{title}</span>
        <div className="wc" style={{ display: 'flex', gap: 5 }}>
          <WBtn onClick={() => setOpacity(o => o > 0.6 ? 0.3 : 0.95)} title="Läbipaistvus">◑</WBtn>
          <WBtn onClick={onMinimize}>{minimized ? '□' : '–'}</WBtn>
          <WBtn onClick={onClose} color={C.red}>✕</WBtn>
        </div>
      </div>
      {/* Sisu */}
      {!minimized && <div style={{ flex: 1, overflow: 'hidden' }}>{children}</div>}
      {/* Resize */}
      {!minimized && <div className="rh" onMouseDown={onRszStart} style={{
        position: 'absolute', bottom: 0, right: 0, width: 14, height: 14, cursor: 'nwse-resize',
        background: `linear-gradient(135deg, transparent 50%, ${C.border} 50%)`,
      }} />}
    </div>
  )
}

function WBtn({ onClick, children, color, title }) {
  return <button onClick={onClick} title={title} style={{
    background: 'none', border: 'none', color: color || C.textDim,
    cursor: 'pointer', fontSize: 12, padding: '0 2px', fontFamily: font,
  }}>{children}</button>
}

// ── Akende sisud ──────────────────────────────────────────────────────────────
function JarvisPanel({ results, loading, interim, sphereState }) {
  return (
    <div style={{ padding: 12, height: '100%', display: 'flex', flexDirection: 'column', gap: 8, overflow: 'hidden' }}>
      <div style={{ display: 'flex', justifyContent: 'center', flexShrink: 0 }}>
        <div style={{ width: 110, height: 110 }}><JarvisSphere state={sphereState} /></div>
      </div>
      <div style={{ fontSize: 9, letterSpacing: 3, color: C.orange, textAlign: 'center', fontFamily: font, flexShrink: 0 }}>
        {{ idle: 'ОЖИДАНИЕ', listening: 'СЛУШАЮ...', thinking: 'АНАЛИЗ...', speaking: 'ОТВЕТ...' }[sphereState]}
      </div>
      {interim && <div style={{ fontSize: 12, color: C.yellow, fontStyle: 'italic', textAlign: 'center' }}>"{interim}"</div>}
      {loading && <div style={{ color: C.blue, fontSize: 11, textAlign: 'center' }}>⏳</div>}
      {results?.[0]?.response && !loading && (
        <div style={{ fontSize: 13, color: C.text, lineHeight: 1.65, fontFamily: 'system-ui', overflow: 'auto', flex: 1 }}>
          {results[0].response}
        </div>
      )}
    </div>
  )
}

function BrowserPanel() {
  const [url, setUrl] = useState('https://google.com')
  const [input, setInput] = useState('https://google.com')
  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%' }}>
      <div style={{ display: 'flex', gap: 4, padding: '5px 7px', background: '#ffffff06', borderBottom: `1px solid ${C.border}`, flexShrink: 0 }}>
        <input value={input} onChange={e => setInput(e.target.value)}
          onKeyDown={e => e.key === 'Enter' && setUrl(input.startsWith('http') ? input : 'https://' + input)}
          style={{ flex: 1, background: '#ffffff0a', border: `1px solid ${C.border}`, color: C.text, padding: '3px 7px', borderRadius: 4, fontSize: 11, fontFamily: font, outline: 'none' }} />
        <WBtn onClick={() => setUrl(input.startsWith('http') ? input : 'https://' + input)}>→</WBtn>
      </div>
      <iframe src={url} style={{ flex: 1, border: 'none', width: '100%' }} sandbox="allow-scripts allow-same-origin allow-forms" />
    </div>
  )
}

function CameraPanel() {
  const vRef = useRef(null)
  useEffect(() => {
    navigator.mediaDevices.getUserMedia({ video: { facingMode: 'environment' } })
      .then(s => { if (vRef.current) vRef.current.srcObject = s }).catch(() => {})
    return () => vRef.current?.srcObject?.getTracks().forEach(t => t.stop())
  }, [])
  return (
    <div style={{ position: 'relative', height: '100%', background: '#000' }}>
      <video ref={vRef} autoPlay muted playsInline style={{ width: '100%', height: '100%', objectFit: 'cover' }} />
      <div style={{ position: 'absolute', top: 6, right: 8, color: C.red, fontSize: 8, letterSpacing: 2, fontFamily: font, animation: 'blink 1.2s infinite' }}>● LIVE</div>
    </div>
  )
}

function NotesPanel({ notes, onAdd }) {
  const [txt, setTxt] = useState('')
  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%', padding: 8, gap: 6 }}>
      <div style={{ flex: 1, overflow: 'auto', display: 'flex', flexDirection: 'column', gap: 4 }}>
        {notes.map((n, i) => (
          <div key={i} style={{ background: '#ffffff08', border: `1px solid ${C.border}`, borderRadius: 4, padding: '4px 8px', fontSize: 12, color: C.text }}>{n}</div>
        ))}
      </div>
      <div style={{ display: 'flex', gap: 4 }}>
        <input value={txt} onChange={e => setTxt(e.target.value)}
          onKeyDown={e => { if (e.key === 'Enter' && txt.trim()) { onAdd(txt); setTxt('') } }}
          placeholder="Lisa märkus..." style={{ flex: 1, background: '#ffffff08', border: `1px solid ${C.border}`, color: C.text, padding: '4px 8px', borderRadius: 4, fontSize: 11, fontFamily: font, outline: 'none' }} />
      </div>
    </div>
  )
}

function YouTubePanel() {
  const [q, setQ] = useState('')
  const [src, setSrc] = useState('')
  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%' }}>
      <div style={{ display: 'flex', gap: 4, padding: '5px 7px', background: '#ffffff06', borderBottom: `1px solid ${C.border}`, flexShrink: 0 }}>
        <input value={q} onChange={e => setQ(e.target.value)}
          onKeyDown={e => e.key === 'Enter' && setSrc(`https://www.youtube.com/results?search_query=${encodeURIComponent(q)}`)}
          placeholder="Otsi..." style={{ flex: 1, background: '#ffffff0a', border: `1px solid ${C.border}`, color: C.text, padding: '3px 7px', borderRadius: 4, fontSize: 11, fontFamily: font, outline: 'none' }} />
        <WBtn onClick={() => setSrc(`https://www.youtube.com/results?search_query=${encodeURIComponent(q)}`)}>▶</WBtn>
      </div>
      {src ? <iframe src={src} style={{ flex: 1, border: 'none' }} allowFullScreen />
           : <div style={{ flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center', color: C.textDim, fontSize: 13 }}>YouTube</div>}
    </div>
  )
}

function ClockPanel() {
  const [t, setT] = useState(new Date())
  useEffect(() => { const i = setInterval(() => setT(new Date()), 1000); return () => clearInterval(i) }, [])
  return (
    <div style={{ padding: '8px 12px', textAlign: 'center' }}>
      <div style={{ fontSize: '1.8rem', color: C.gold, fontFamily: font, textShadow: `0 0 15px ${C.gold}` }}>
        {t.toLocaleTimeString('et-EE', { hour: '2-digit', minute: '2-digit', second: '2-digit' })}
      </div>
      <div style={{ fontSize: 10, color: C.textDim, marginTop: 2 }}>
        {t.toLocaleDateString('ru-RU', { weekday: 'short', day: 'numeric', month: 'short' })}
      </div>
    </div>
  )
}

const BACKEND = import.meta.env.VITE_BACKEND_URL || 'https://carefree-gentleness-production-6657.up.railway.app'

function PluginsPanel() {
  const [plugins, setPlugins] = useState([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    fetch(`${BACKEND}/plugins`)
      .then(r => r.json()).then(setPlugins).catch(() => setPlugins([]))
      .finally(() => setLoading(false))
  }, [])

  const stateColor = { ready: C.green, error: C.red, suspended: C.yellow, registered: C.blue }

  return (
    <div style={{ padding: '10px 12px', height: '100%', overflowY: 'auto', display: 'flex', flexDirection: 'column', gap: 8 }}>
      <div style={{ fontSize: 9, color: C.textDim, letterSpacing: 2 }}>INSTALLITUD PLUGINAD</div>
      {loading && <div style={{ color: C.textDim, fontSize: 12 }}>Laen...</div>}
      {!loading && plugins.length === 0 && <div style={{ color: C.textDim, fontSize: 12 }}>Pluginaid pole</div>}
      {plugins.map(p => (
        <div key={p.plugin_id} style={{
          background: '#ffffff06', border: `1px solid ${C.border}`,
          borderLeft: `3px solid ${stateColor[p.state] || C.border}`,
          borderRadius: 6, padding: '6px 10px',
        }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <span style={{ fontSize: 12, color: C.text, fontWeight: 600 }}>{p.name}</span>
            <span style={{ fontSize: 9, color: stateColor[p.state] || C.textDim, letterSpacing: 1 }}>{p.state.toUpperCase()}</span>
          </div>
          <div style={{ fontSize: 10, color: C.textDim, marginTop: 2 }}>{p.description}</div>
          <div style={{ fontSize: 9, color: C.textDim, marginTop: 3 }}>
            v{p.version} · {p.permissions.length > 0 ? `🔒 ${p.permissions.join(', ')}` : 'Lubad puuduvad'}
          </div>
          {p.commands.length > 0 && (
            <div style={{ fontSize: 9, color: C.blue, marginTop: 2 }}>
              Käsud: {p.commands.join(' · ')}
            </div>
          )}
        </div>
      ))}
    </div>
  )
}

// ── Peamine HUD ───────────────────────────────────────────────────────────────
export default function GlassesHUD() {
  const { status, results, loading, audio, analyze, securityAlert } = useJarvis(getDeviceId())
  const { notifs, add: addNotif, dismiss } = useNotifications()
  const [sphereState, setSphereState] = useState('idle')
  const [listening, setListening]     = useState(false)
  const [interim, setInterim]         = useState('')
  const [ws, setWs]                   = useState('home')
  const [wins, setWins]               = useState(() => Object.fromEntries(Object.keys(WIN_DEFS).map(k => [k, { open: k === 'jarvis' || k === 'clock', minimized: false }])))
  const [notes, setNotes]             = useState([])
  const [subtitles, setSubtitles]     = useState(false)
  const [gestureFeedback, setGestureFeedback] = useState(null) // { text, ts }
  const recogRef  = useRef(null)
  const activeRef = useRef(false)
  const timerRef  = useRef(null)

  // Sfääri olek
  useEffect(() => {
    if (listening) setSphereState('listening')
    else if (loading) setSphereState('thinking')
    else if (audio) setSphereState('speaking')
    else setSphereState('idle')
  }, [listening, loading, audio])

  // Heli
  useEffect(() => {
    if (!audio) return
    const blob = new Blob([Uint8Array.from(atob(audio), c => c.charCodeAt(0))], { type: 'audio/mpeg' })
    const url = URL.createObjectURL(blob)
    const a = new Audio(url)
    a.play().catch(() => {})
    return () => { a.pause(); URL.revokeObjectURL(url) }
  }, [audio])

  // Status notifid
  useEffect(() => {
    if (status === 'online')       addNotif('Albert OS ühendatud', 'success')
    if (status === 'disconnected') addNotif('Ühendus katkes — taasühendan...', 'important')
  }, [status])

  // Kõnetuvastus
  const startRec = useCallback(() => {
    if (!activeRef.current) return
    const SR = window.SpeechRecognition || window.webkitSpeechRecognition
    if (!SR) return
    const r = new SR()
    r.lang = 'ru-RU'; r.interimResults = true; r.continuous = false
    r.onstart = () => setListening(true)
    r.onresult = (e) => {
      let itr = '', fin = ''
      for (let i = e.resultIndex; i < e.results.length; i++) {
        if (e.results[i].isFinal) fin += e.results[i][0].transcript
        else itr += e.results[i][0].transcript
      }
      setInterim(itr)
      if (fin.trim()) { setInterim(''); handleCmd(fin.trim()) }
    }
    r.onend = () => { setInterim(''); if (activeRef.current) timerRef.current = setTimeout(startRec, 200); else setListening(false) }
    r.onerror = (e) => { if (e.error !== 'no-speech') { activeRef.current = false; setListening(false) } else if (activeRef.current) timerRef.current = setTimeout(startRec, 300) }
    recogRef.current = r
    try { r.start() } catch (_) {}
  }, [])

  function handleCmd(text) {
    const t = text.toLowerCase()
    // Workspace
    const wsMatch = Object.entries(WORKSPACES).find(([, v]) => t.includes(v.name.toLowerCase()) || t.includes(v.label))
    if (wsMatch) { applyWs(wsMatch[0]); return }
    // Aknad
    if (t.includes('открой браузер') || t.includes('ava brauser')) return openWin('browser')
    if (t.includes('youtube') || t.includes('ютуб')) return openWin('youtube')
    if (t.includes('камер') || t.includes('kaamera')) return openWin('camera')
    if (t.includes('заметки') || t.includes('märkmed')) return openWin('notes')
    if (t.includes('закрой всё') || t.includes('sulge kõik')) return closeAll()
    // JARVIS
    analyze({ prompt: text, mode: 'default' })
  }

  function applyWs(id) {
    setWs(id)
    const cfg = WORKSPACES[id]
    setWins(prev => Object.fromEntries(Object.keys(WIN_DEFS).map(k => [k, { ...prev[k], open: !!cfg.wins[k], minimized: false }])))
    addNotif(`Workspace: ${cfg.name}`, 'info')
  }
  function openWin(id) { setWins(w => ({ ...w, [id]: { open: true, minimized: false } })) }
  function closeWin(id) { setWins(w => ({ ...w, [id]: { ...w[id], open: false } })) }
  function minWin(id)   { setWins(w => ({ ...w, [id]: { ...w[id], minimized: !w[id].minimized } })) }
  function closeAll()   { setWins(w => Object.fromEntries(Object.keys(w).map(k => [k, { ...w[k], open: k === 'jarvis' }]))) }

  function toggleMic() {
    if (activeRef.current) { activeRef.current = false; clearTimeout(timerRef.current); recogRef.current?.abort(); setListening(false) }
    else { activeRef.current = true; startRec() }
  }

  useEffect(() => {
    if (status === 'online') { setTimeout(() => { activeRef.current = true; startRec() }, 800) }
    return () => { activeRef.current = false; clearTimeout(timerRef.current) }
  }, [status])

  // ── Gesture Engine ─────────────────────────────────────────────────────────
  function showGestureFeedback(type) {
    setGestureFeedback({ text: getGestureFeedback(type), ts: Date.now() })
    setTimeout(() => setGestureFeedback(null), 1400)
  }

  useEffect(() => {
    attachTouchAdapter()

    const offs = [
      onGesture(GESTURES.SWIPE_LEFT, () => {
        setWs(cur => {
          const i = WS_ORDER.indexOf(cur)
          const next = WS_ORDER[Math.max(0, i - 1)]
          if (next !== cur) { applyWs(next); showGestureFeedback(GESTURES.SWIPE_LEFT) }
          return cur
        })
      }),
      onGesture(GESTURES.SWIPE_RIGHT, () => {
        setWs(cur => {
          const i = WS_ORDER.indexOf(cur)
          const next = WS_ORDER[Math.min(WS_ORDER.length - 1, i + 1)]
          if (next !== cur) { applyWs(next); showGestureFeedback(GESTURES.SWIPE_RIGHT) }
          return cur
        })
      }),
      onGesture(GESTURES.SWIPE_UP, () => {
        openWin('browser')
        showGestureFeedback(GESTURES.SWIPE_UP)
      }),
      onGesture(GESTURES.SWIPE_DOWN, () => {
        setWins(w => {
          const open = Object.keys(w).filter(k => w[k]?.open && k !== 'jarvis')
          if (open.length) { showGestureFeedback(GESTURES.SWIPE_DOWN); return { ...w, [open[0]]: { ...w[open[0]], minimized: true } } }
          return w
        })
      }),
      onGesture(GESTURES.OPEN_PALM, () => {
        openWin('jarvis'); showGestureFeedback(GESTURES.OPEN_PALM)
      }),
      onGesture(GESTURES.CLOSED_FIST, () => {
        setWins(w => {
          const open = Object.keys(w).filter(k => w[k]?.open && k !== 'jarvis')
          if (open.length) { showGestureFeedback(GESTURES.CLOSED_FIST); return { ...w, [open[open.length - 1]]: { ...w[open[open.length - 1]], open: false } } }
          return w
        })
      }),
    ]
    return () => { detachTouchAdapter(); offs.forEach(off => off()) }
  }, [])

  // Safety context sünkroniseerimine workspace-ga
  useEffect(() => { setSafetyContext(ws) }, [ws])

  const statusColor = { online: C.green, connecting: C.yellow, disconnected: C.red }[status]

  // Aku tase (simuleeritud — päris iOS Battery API vajab native appi)
  const [battery, setBattery] = useState(null)
  useEffect(() => { navigator.getBattery?.().then(b => { setBattery(Math.round(b.level * 100)); b.onlevelchange = () => setBattery(Math.round(b.level * 100)) }) }, [])

  return (
    <div style={{ width: '100vw', height: '100vh', background: '#000', overflow: 'hidden', position: 'relative', fontFamily: font }}>
      {/* Taust-grid */}
      <svg style={{ position: 'absolute', inset: 0, width: '100%', height: '100%', pointerEvents: 'none', opacity: 0.4 }}>
        <defs><pattern id="g" width="60" height="60" patternUnits="userSpaceOnUse"><path d="M60 0L0 0 0 60" fill="none" stroke="#ffffff08" strokeWidth="0.5"/></pattern></defs>
        <rect width="100%" height="100%" fill="url(#g)"/>
      </svg>

      {/* ══ TOP BAR ══════════════════════════════════════════════════════════ */}
      <div style={{
        position: 'absolute', top: 0, left: 0, right: 0, height: 44,
        background: C.bg, borderBottom: `1px solid ${C.border}`,
        backdropFilter: 'blur(20px)',
        display: 'flex', alignItems: 'center', padding: '0 16px', gap: 14, zIndex: 100,
      }}>
        <span style={{ fontSize: 11, letterSpacing: 4, color: C.orange, fontWeight: 700 }}>ALBERT OS</span>
        <div style={{ width: 1, height: 18, background: C.border }} />

        {/* Kellaaeg */}
        <ClockMini />

        {/* Aku */}
        {battery !== null && <TopItem color={battery < 20 ? C.red : C.green}>🔋{battery}%</TopItem>}

        {/* WiFi */}
        <TopItem color={navigator.onLine ? C.green : C.red}>{navigator.onLine ? '📶' : '📵'}</TopItem>

        {/* AI Provider */}
        <TopItem color={C.orange}>AI: {status === 'online' ? 'GPT-4o' : '—'}</TopItem>

        {/* Ühendus */}
        <TopItem color={statusColor}>● {status.toUpperCase()}</TopItem>

        <div style={{ flex: 1 }} />

        {/* Subtiitrid */}
        <TopBtn active={subtitles} onClick={() => setSubtitles(s => !s)} title="Subtiitrid">CC</TopBtn>

        {/* Mikrofon */}
        <TopBtn active={listening} onClick={toggleMic} color={listening ? C.red : undefined}>
          {listening ? '🔴' : '🎤'}
        </TopBtn>
      </div>

      {/* ══ VASAKPANEEL — Notifid + Aktiivne projekt ══════════════════════════ */}
      <div style={{
        position: 'absolute', top: 44, left: 0, bottom: 52,
        width: 200, padding: '10px 8px',
        background: C.bg, borderRight: `1px solid ${C.border}`,
        backdropFilter: 'blur(12px)', overflowY: 'auto', zIndex: 50,
      }}>
        <div style={{ fontSize: 9, color: C.textDim, letterSpacing: 2, marginBottom: 8 }}>NOTIFICATIONS</div>
        {notifs.length === 0 && <div style={{ fontSize: 11, color: '#333', textAlign: 'center', marginTop: 20 }}>Puhas</div>}
        {notifs.map(n => (
          <div key={n.id} onClick={() => dismiss(n.id)} style={{
            background: `${NOTIF_COLOR[n.level] || C.blue}18`,
            border: `1px solid ${NOTIF_COLOR[n.level] || C.blue}50`,
            borderLeft: `3px solid ${NOTIF_COLOR[n.level] || C.blue}`,
            borderRadius: 5, padding: '5px 8px', marginBottom: 5, cursor: 'pointer',
            fontSize: 11, color: C.text, animation: 'fadeIn 0.2s ease',
          }}>{n.msg}</div>
        ))}

        <div style={{ fontSize: 9, color: C.textDim, letterSpacing: 2, margin: '14px 0 8px' }}>WORKSPACE</div>
        {Object.entries(WORKSPACES).map(([id, cfg]) => (
          <button key={id} onClick={() => applyWs(id)} style={{
            display: 'block', width: '100%', textAlign: 'left',
            background: ws === id ? `${C.orange}20` : 'none',
            border: `1px solid ${ws === id ? C.orange : C.border}`,
            color: ws === id ? C.orange : C.textDim,
            borderRadius: 5, padding: '5px 8px', marginBottom: 3,
            cursor: 'pointer', fontSize: 11, fontFamily: font,
          }}>{cfg.label} {cfg.name}</button>
        ))}
      </div>

      {/* ══ PAREMKÜLG — Avatud aknad ══════════════════════════════════════════ */}
      <div style={{
        position: 'absolute', top: 44, right: 0, bottom: 52,
        width: 160, padding: '10px 8px',
        background: C.bg, borderLeft: `1px solid ${C.border}`,
        backdropFilter: 'blur(12px)', zIndex: 50,
      }}>
        <div style={{ fontSize: 9, color: C.textDim, letterSpacing: 2, marginBottom: 8 }}>AVATUD AKNAD</div>
        {Object.entries(WIN_DEFS).filter(([id]) => wins[id]?.open).map(([id, def]) => (
            <div key={id} style={{
              display: 'flex', alignItems: 'center', justifyContent: 'space-between',
              background: '#ffffff08', border: `1px solid ${C.border}`,
              borderRadius: 5, padding: '4px 8px', marginBottom: 3,
              fontSize: 11, color: C.text,
            }}>
              <span>{def.icon} {def.title}</span>
              <button onClick={() => closeWin(id)} style={{ background: 'none', border: 'none', color: C.textDim, cursor: 'pointer', fontSize: 11 }}>✕</button>
            </div>
        ))}
      </div>

      {/* ══ UJUVAD AKNAD ══════════════════════════════════════════════════════ */}
      <div style={{ position: 'absolute', top: 44, left: 200, right: 160, bottom: 52, overflow: 'hidden' }}>
        {Object.entries(WIN_DEFS).map(([id, def]) => (
          <FloatWin key={id} id={id} title={def.title} icon={def.icon}
            open={wins[id]?.open} minimized={wins[id]?.minimized}
            onClose={() => closeWin(id)} onMinimize={() => minWin(id)}
            defaultPos={def.defaultPos} defaultW={def.w} defaultH={def.h}>
            {id === 'jarvis'  && <JarvisPanel results={results} loading={loading} interim={subtitles ? interim : ''} sphereState={sphereState} />}
            {id === 'browser' && <BrowserPanel />}
            {id === 'camera'  && <CameraPanel />}
            {id === 'notes'   && <NotesPanel notes={notes} onAdd={n => setNotes(p => [n, ...p])} />}
            {id === 'youtube' && <YouTubePanel />}
            {id === 'clock'   && <ClockPanel />}
            {id === 'plugins' && <PluginsPanel />}
          </FloatWin>
        ))}

        {/* Turvahoiatus */}
        {securityAlert && (
          <div style={{
            position: 'absolute', top: 16, left: '50%', transform: 'translateX(-50%)',
            background: securityAlert.type === 'confirm_required' ? `${C.red}dd` :
                        securityAlert.type === 'warning'          ? `${C.yellow}dd` : `${C.red}dd`,
            border: `1px solid ${C.red}`,
            borderRadius: 10, padding: '10px 20px', maxWidth: 480,
            color: '#fff', fontSize: 13, fontFamily: 'system-ui',
            animation: 'fadeIn 0.2s ease', zIndex: 200, pointerEvents: 'none',
            textAlign: 'center',
          }}>
            {securityAlert.type === 'confirm_required' ? '⚠ ' : '🔒 '}{securityAlert.msg}
          </div>
        )}

        {/* Gesture tagasiside */}
        {gestureFeedback && (
          <div style={{
            position: 'absolute', top: '42%', left: '50%', transform: 'translateX(-50%)',
            background: '#000000cc', border: `1px solid ${C.orange}`,
            borderRadius: 10, padding: '10px 24px',
            color: C.orange, fontSize: 18, fontFamily: font, letterSpacing: 3,
            animation: 'fadeIn 0.15s ease',
            pointerEvents: 'none', zIndex: 99,
          }}>{gestureFeedback.text}</div>
        )}

        {/* Subtiitrid globaalselt */}
        {subtitles && interim && (
          <div style={{
            position: 'absolute', bottom: 12, left: '50%', transform: 'translateX(-50%)',
            background: '#000000dd', border: `1px solid ${C.border}`, borderRadius: 8,
            padding: '6px 18px', color: C.yellow, fontSize: 14, fontStyle: 'italic',
          }}>"{interim}"</div>
        )}
      </div>

      {/* ══ BOTTOM DOCK ══════════════════════════════════════════════════════ */}
      <div style={{
        position: 'absolute', bottom: 0, left: 200, right: 160, height: 52,
        background: C.bg, borderTop: `1px solid ${C.border}`,
        backdropFilter: 'blur(20px)',
        display: 'flex', alignItems: 'center', justifyContent: 'center',
        gap: 8, zIndex: 100,
      }}>
        {[
          { id: 'browser', icon: '🌐', label: 'Brauser' },
          { id: 'camera',  icon: '📷', label: 'Kaamera' },
          { id: 'notes',   icon: '📝', label: 'Märkmed' },
          { id: 'youtube', icon: '▶',  label: 'YouTube'  },
          { id: 'clock',   icon: '🕐', label: 'Kell'    },
        ].map(({ id, icon, label }) => (
          <button key={id} onClick={() => openWin(id)} style={{
            display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 2,
            background: wins[id]?.open ? `${C.orange}20` : 'none',
            border: `1px solid ${wins[id]?.open ? C.orange : C.border}`,
            borderRadius: 8, padding: '5px 10px', cursor: 'pointer',
            color: wins[id]?.open ? C.orange : C.textDim,
            transition: 'all 0.15s', minWidth: 56,
          }}>
            <span style={{ fontSize: 16 }}>{icon}</span>
            <span style={{ fontSize: 8, letterSpacing: 1, fontFamily: font }}>{label}</span>
          </button>
        ))}

        {/* Pluginad nupp */}
        <button onClick={() => openWin('plugins')} style={{
          display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 2,
          background: wins['plugins']?.open ? `${C.blue}20` : 'none',
          border: `1px solid ${wins['plugins']?.open ? C.blue : C.border}`,
          borderRadius: 8, padding: '5px 10px', cursor: 'pointer',
          color: wins['plugins']?.open ? C.blue : C.textDim, minWidth: 56,
        }}>
          <span style={{ fontSize: 16 }}>🔌</span>
          <span style={{ fontSize: 8, letterSpacing: 1, fontFamily: font }}>PLUGINAD</span>
        </button>

        <div style={{ width: 1, height: 30, background: C.border, margin: '0 4px' }} />

        {/* Mikrofon */}
        <button onClick={toggleMic} style={{
          display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 2,
          background: listening ? `${C.red}20` : 'none',
          border: `1px solid ${listening ? C.red : C.border}`,
          borderRadius: 8, padding: '5px 12px', cursor: 'pointer',
          color: listening ? C.red : C.textDim, minWidth: 56,
          animation: listening ? 'pulse 0.8s infinite' : 'none',
        }}>
          <span style={{ fontSize: 16 }}>{listening ? '🔴' : '🎤'}</span>
          <span style={{ fontSize: 8, letterSpacing: 1, fontFamily: font }}>MIK</span>
        </button>
      </div>

      <style>{`
        @keyframes fadeIn { from { opacity: 0; transform: scale(0.97); } to { opacity: 1; transform: scale(1); } }
        @keyframes blink  { 50% { opacity: 0.2; } }
        @keyframes pulse  { 50% { opacity: 0.4; } }
        * { box-sizing: border-box; margin: 0; padding: 0; }
        ::-webkit-scrollbar { width: 3px; }
        ::-webkit-scrollbar-thumb { background: ${C.border}; border-radius: 2px; }
      `}</style>
    </div>
  )
}

function ClockMini() {
  const [t, setT] = useState(new Date())
  useEffect(() => { const i = setInterval(() => setT(new Date()), 1000); return () => clearInterval(i) }, [])
  return <span style={{ fontSize: 12, color: C.gold, letterSpacing: 2, fontFamily: font }}>{t.toLocaleTimeString('et-EE', { hour: '2-digit', minute: '2-digit' })}</span>
}

function TopItem({ children, color }) {
  return <span style={{ fontSize: 10, color: color || C.textDim, letterSpacing: 1, fontFamily: font }}>{children}</span>
}

function TopBtn({ children, active, onClick, color, title }) {
  const ac = color || (active ? C.red : C.textDim)
  return <button onClick={onClick} title={title} style={{
    background: active ? `${ac}20` : 'none',
    border: `1px solid ${active ? ac : C.border}`,
    color: ac, borderRadius: 5, padding: '3px 8px',
    cursor: 'pointer', fontSize: 10, fontFamily: font, letterSpacing: 1,
  }}>{children}</button>
}
