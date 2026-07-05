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
import { C, FONT as font, HUDWidget, NotificationCard, StatusDot, Button, LoadingDots } from './components/ui'
import { useWindowManager } from './hooks/useWindowManager'
import { useDeviceManager } from './hooks/useDeviceManager'
import { useUserPrefs } from './hooks/useUserPrefs'
import FirstLaunchWizard from './components/FirstLaunchWizard'
import { useAudio } from './hooks/useAudio'
import { useXRSession } from './hooks/useXRSession'

function getDeviceId() {
  let id = localStorage.getItem('jarvis_device_id')
  if (!id) { id = 'glasses_' + Math.random().toString(36).slice(2,8); localStorage.setItem('jarvis_device_id', id) }
  return id
}

// ── Notifikatsiooni süsteem ───────────────────────────────────────────────────
// Tasemed (19_JARVIS_USER_EXPERIENCE.md):
//   critical  — alati nähtav, ei kao
//   important — nähtav kuni dismiss
//   info      — peidetakse 8s pärast
//   silent    — salvestatakse, ei kuvata riba-teavitusena
const NOTIF_TTL = { critical: null, important: null, info: 8000, silent: 0 }

function useNotifications() {
  const [notifs, setNotifs] = useState([])
  const add = useCallback((msg, level = 'info') => {
    const id = `${Date.now()}_${Math.random().toString(36).slice(2, 6)}`
    // Silent: salvesta kuid ära kuva kohe
    if (level === 'silent') {
      setNotifs(n => [{ id, msg, level, ts: Date.now(), hidden: true }, ...n.slice(0, 19)])
      return
    }
    setNotifs(n => [{ id, msg, level, ts: Date.now() }, ...n.slice(0, 14)])
    const ttl = NOTIF_TTL[level]
    if (ttl !== null) setTimeout(() => setNotifs(n => n.filter(x => x.id !== id)), ttl)
  }, [])
  const dismiss = useCallback((id) => setNotifs(n => n.filter(x => x.id !== id)), [])
  const clearAll = useCallback(() => setNotifs(n => n.filter(x => x.level === 'critical')), [])
  // Ainult mittepeidetud teavitused kuvamiseks
  const visible = notifs.filter(n => !n.hidden)
  return { notifs, visible, add, dismiss, clearAll }
}

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
  jarvis:   { title: 'JARVIS',    icon: '🤖', defaultPos: { x: 320, y: 80 },  w: 320, h: 340 },
  browser:  { title: 'БРАУЗЕР',   icon: '🌐', defaultPos: { x: 660, y: 80 },  w: 480, h: 360 },
  camera:   { title: 'КАМЕРА',    icon: '📷', defaultPos: { x: 320, y: 430 }, w: 340, h: 320 },
  notes:    { title: 'ЗАМЕТКИ',   icon: '📝', defaultPos: { x: 1160, y: 80 }, w: 260, h: 280 },
  youtube:  { title: 'YOUTUBE',   icon: '▶',  defaultPos: { x: 660, y: 80 },  w: 480, h: 340 },
  clock:    { title: 'ВРЕМЯ',     icon: '🕐', defaultPos: { x: 1160, y: 380 }, w: 200, h: 90  },
  plugins:  { title: 'PLUGINAD',  icon: '🔌', defaultPos: { x: 660,  y: 430 }, w: 320, h: 280 },
  settings: { title: 'SEADED',    icon: '⚙',  defaultPos: { x: 860,  y: 80 },  w: 360, h: 440 },
  projects: { title: 'PROJEKTID', icon: '📁', defaultPos: { x: 660,  y: 430 }, w: 380, h: 320 },
}

// ── Ujuv aken ─────────────────────────────────────────────────────────────────
function FloatWin({ winState, title, icon, children, onClose, onMinimize, onMaximize, onPin, onFocus, onPos, onSize, onOpacity, onSnap, focused }) {
  const drag = useRef(null)
  const rsz  = useRef(null)
  const [closing, setClosing] = useState(false)

  function handleClose() {
    setClosing(true)
    setTimeout(() => { setClosing(false); onClose() }, 180)
  }

  if (!winState?.open) return null

  const { pos, size, opacity, minimized, maximized, pinned, zIndex } = winState

  function onDragStart(e) {
    if (maximized || pinned) return
    if (e.target.closest('.wc') || e.target.closest('.rh')) return
    onFocus()
    drag.current = { sx: e.clientX - pos.x, sy: e.clientY - pos.y }
    const mv = e2 => { if (drag.current) onPos({ x: e2.clientX - drag.current.sx, y: e2.clientY - drag.current.sy }) }
    const up = () => { drag.current = null; window.removeEventListener('mousemove', mv); window.removeEventListener('mouseup', up) }
    window.addEventListener('mousemove', mv); window.addEventListener('mouseup', up)
  }

  function onRszStart(e) {
    if (maximized) return
    e.stopPropagation()
    rsz.current = { sx: e.clientX, sy: e.clientY, w: size.w, h: size.h }
    const mv = e2 => { if (rsz.current) onSize({ w: Math.max(180, rsz.current.w + e2.clientX - rsz.current.sx), h: Math.max(80, rsz.current.h + e2.clientY - rsz.current.sy) }) }
    const up = () => { rsz.current = null; window.removeEventListener('mousemove', mv); window.removeEventListener('mouseup', up) }
    window.addEventListener('mousemove', mv); window.addEventListener('mouseup', up)
  }

  const maxStyle = maximized
    ? { left: 0, top: 0, width: '100%', height: '100%', borderRadius: 0 }
    : { left: pos.x, top: pos.y, width: size.w, height: minimized ? 36 : size.h }

  return (
    <div
      onMouseDown={onFocus}
      style={{
        position: 'absolute',
        ...maxStyle,
        background: C.bg,
        border: `1px solid ${focused ? C.orange + '80' : C.border}`,
        borderRadius: maximized ? 0 : 10,
        overflow: 'hidden',
        backdropFilter: 'blur(16px)',
        opacity,
        display: 'flex', flexDirection: 'column',
        transition: 'height 0.2s, opacity 0.15s, border-color 0.15s, width 0.2s, left 0.2s, top 0.2s',
        animation: closing ? 'winClose 0.18s ease forwards' : 'winOpen 0.2s ease',
        zIndex,
      }}
    >
      {/* Tiitelriba */}
      <div onMouseDown={onDragStart} style={{
        display: 'flex', alignItems: 'center', gap: 7, padding: '5px 10px',
        background: focused ? '#ffffff12' : '#ffffff08',
        borderBottom: `1px solid ${C.border}`,
        cursor: maximized || pinned ? 'default' : 'grab',
        userSelect: 'none', flexShrink: 0,
        transition: 'background 0.15s',
      }}>
        <span style={{ fontSize: 13 }}>{icon}</span>
        <span style={{ flex: 1, fontSize: 10, color: focused ? C.orange : C.textDim, letterSpacing: 2, fontFamily: font, transition: 'color 0.15s' }}>{title}</span>
        {pinned && <span style={{ fontSize: 9, color: C.blue, marginRight: 4 }}>📌</span>}
        <div className="wc" style={{ display: 'flex', gap: 5 }}>
          <WBtn onClick={() => onOpacity(opacity > 0.6 ? 0.3 : 0.95)} title="Läbipaistvus">◑</WBtn>
          {onSnap && <SnapMenu onSnap={onSnap} />}
          <WBtn onClick={onPin} title={pinned ? 'Vabasta' : 'Kinnita'} color={pinned ? C.blue : undefined}>📌</WBtn>
          <WBtn onClick={onMaximize} title={maximized ? 'Taasta' : 'Maksimeeri'}>{maximized ? '❐' : '□'}</WBtn>
          <WBtn onClick={onMinimize}>{minimized ? '▲' : '–'}</WBtn>
          <WBtn onClick={handleClose} color={C.red}>✕</WBtn>
        </div>
      </div>
      {/* Sisu — lazy: ei renderdeta minimeeritud akende sisu */}
      {!minimized && <div style={{ flex: 1, overflow: 'hidden' }}>{children}</div>}
      {/* Resize */}
      {!minimized && !maximized && <div className="rh" onMouseDown={onRszStart} style={{
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

// Snap menu — aseta aken ekraani servale/nurka
function SnapMenu({ onSnap }) {
  const [open, setOpen] = useState(false)
  const SNAPS = [
    ['tl','↖'],['top','↑'],['tr','↗'],
    ['left','←'],['center','·'],['right','→'],
    ['bl','↙'],['br','↘'],
  ]
  return (
    <div style={{ position: 'relative' }}>
      <WBtn onClick={() => setOpen(v => !v)} title="Snap">⊞</WBtn>
      {open && (
        <div onMouseLeave={() => setOpen(false)} style={{
          position: 'absolute', top: 18, right: 0,
          background: '#111', border: `1px solid ${C.border}`,
          borderRadius: 6, padding: 4, zIndex: 999,
          display: 'grid', gridTemplateColumns: 'repeat(3,22px)', gap: 2,
        }}>
          {SNAPS.map(([pos, label]) => (
            <button key={pos} onClick={() => { onSnap(pos); setOpen(false) }} style={{
              background: 'none', border: `1px solid ${C.border}`, color: C.textDim,
              borderRadius: 3, cursor: 'pointer', fontSize: 11, padding: '2px 0',
              fontFamily: font, textAlign: 'center',
            }}>{label}</button>
          ))}
        </div>
      )}
    </div>
  )
}

// ── Akende sisud ──────────────────────────────────────────────────────────────
const FOLLOWUP_SHORTCUTS = {
  bmw_diagnostics:  ['Mis osad vajan?', 'Näita skeem', 'Mitu see maksab?'],
  boat_diagnostics: ['Hooldusplaan', 'Varuosad', 'Ohutussoovitused'],
  coding:           ['Refaktori', 'Lisa testid', 'Selgita lähemalt'],
  research:         ['Kokkuvõte', 'Allikad', 'Võrdle alternatiividega'],
  general:          ['Selgita lähemalt', 'Järgmine samm', 'Salvesta mällu'],
}

function JarvisPanel({ results, loading, interim, sphereState, onFollowUp, intent }) {
  const shortcuts = FOLLOWUP_SHORTCUTS[intent] || FOLLOWUP_SHORTCUTS.general
  const hasResponse = results?.[0]?.response && !loading

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
      {hasResponse && (
        <div style={{ fontSize: 13, color: C.text, lineHeight: 1.65, fontFamily: 'system-ui', overflow: 'auto', flex: 1 }}>
          {results[0].response}
        </div>
      )}
      {/* Follow-up shortcuts — näita vastuse järel */}
      {hasResponse && onFollowUp && (
        <div style={{ display: 'flex', gap: 4, flexShrink: 0, flexWrap: 'wrap' }}>
          {shortcuts.map(s => (
            <button key={s} onClick={() => onFollowUp(s)} style={{
              background: `${C.orange}12`, border: `1px solid ${C.orange}40`,
              color: C.orange, borderRadius: 12, padding: '3px 8px',
              fontSize: 9, fontFamily: font, cursor: 'pointer', letterSpacing: 0.5,
            }}>{s}</button>
          ))}
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

function CameraPanel({ onAnalyze }) {
  const vRef  = useRef(null)
  const cvRef = useRef(null)
  const [snap, setSnap]     = useState(null)
  const [snap2, setSnap2]   = useState(null)   // Compare: teine pilt
  const [compare, setCompare] = useState(false)
  const [status, setCameraStatus] = useState('starting')

  useEffect(() => {
    navigator.mediaDevices.getUserMedia({ video: { facingMode: 'environment' } })
      .then(s => { if (vRef.current) { vRef.current.srcObject = s; setCameraStatus('live') } })
      .catch(() => setCameraStatus('error'))
    return () => vRef.current?.srcObject?.getTracks().forEach(t => t.stop())
  }, [])

  function capture() {
    const v = vRef.current
    if (!v) return null
    const c = cvRef.current || document.createElement('canvas')
    c.width = v.videoWidth; c.height = v.videoHeight
    c.getContext('2d').drawImage(v, 0, 0)
    const b64 = c.toDataURL('image/jpeg', 0.8).split(',')[1]
    setSnap(b64)
    return b64
  }

  const btnStyle = (color) => ({
    flex: 1, background: `${color}18`, border: `1px solid ${color}50`,
    color, borderRadius: 5, padding: '5px 4px', fontSize: 9,
    fontFamily: font, cursor: 'pointer', letterSpacing: 1,
  })

  function captureCompare() {
    const b = capture()
    if (!b) return
    setSnap2(b)
    setCompare(true)
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%', background: '#000' }}>
      {/* Võrdlusrežiim: kaks pilti kõrvuti */}
      {compare && snap && snap2 ? (
        <div style={{ flex: 1, display: 'flex', gap: 2 }}>
          <div style={{ flex: 1, position: 'relative' }}>
            <img src={`data:image/jpeg;base64,${snap}`} style={{ width: '100%', height: '100%', objectFit: 'cover' }} alt="A" />
            <div style={{ position: 'absolute', top: 4, left: 6, fontSize: 8, color: C.orange, fontFamily: font, letterSpacing: 1, background: '#000a', padding: '1px 5px', borderRadius: 3 }}>A</div>
          </div>
          <div style={{ flex: 1, position: 'relative' }}>
            <img src={`data:image/jpeg;base64,${snap2}`} style={{ width: '100%', height: '100%', objectFit: 'cover' }} alt="B" />
            <div style={{ position: 'absolute', top: 4, left: 6, fontSize: 8, color: C.blue, fontFamily: font, letterSpacing: 1, background: '#000a', padding: '1px 5px', borderRadius: 3 }}>B</div>
          </div>
        </div>
      ) : (
        <div style={{ position: 'relative', flex: 1 }}>
          <video ref={vRef} autoPlay muted playsInline style={{ width: '100%', height: '100%', objectFit: 'cover', display: snap ? 'none' : 'block' }} />
          {snap && <img src={`data:image/jpeg;base64,${snap}`} style={{ width: '100%', height: '100%', objectFit: 'cover' }} alt="snap" />}
          <div style={{ position: 'absolute', top: 4, right: 6, fontSize: 8, letterSpacing: 2, fontFamily: font,
            color: status === 'live' ? C.red : C.textDim }}>
            {status === 'live' ? '● LIVE' : status === 'error' ? '✖ VIGA' : '○ ...'}
          </div>
          {snap && <button onClick={() => { setSnap(null); setCompare(false) }} style={{ position: 'absolute', top: 4, left: 6, background: '#000a', border: 'none', color: C.textDim, fontSize: 9, cursor: 'pointer', borderRadius: 3, padding: '2px 6px' }}>✕ LIVE</button>}
        </div>
      )}
      <div style={{ display: 'flex', gap: 4, padding: '6px 6px', background: '#ffffff06', borderTop: `1px solid ${C.border}`, flexShrink: 0, flexWrap: 'wrap' }}>
        <button style={btnStyle(C.orange)} onClick={capture}>📷 JÄÄDV</button>
        <button style={btnStyle(C.blue)}   onClick={() => { const b = capture(); if (b && onAnalyze) onAnalyze(b, 'analyze') }}>🔍 ANALÜÜS</button>
        <button style={btnStyle(C.green)}  onClick={() => { const b = capture(); if (b && onAnalyze) onAnalyze(b, 'translate') }}>🌐 TÕLGI</button>
        <button style={btnStyle(C.yellow)} onClick={() => { const b = capture(); if (b && onAnalyze) onAnalyze(b, 'identify') }}>🏷 MIS?</button>
        {/* Compare: jäädvusta 2. pilt ja näita kõrvuti */}
        {snap && <button style={btnStyle(C.textDim)} onClick={captureCompare}>⊞ VÕRDL</button>}
        {compare && <button style={btnStyle(C.red)} onClick={() => { setCompare(false); setSnap2(null) }}>✕ VÕRDL</button>}
        <button style={btnStyle(C.textDim)} onClick={() => { if (snap) { const a = document.createElement('a'); a.href = `data:image/jpeg;base64,${snap}`; a.download = `albert_${Date.now()}.jpg`; a.click() } }}>💾 SALVESTA</button>
      </div>
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

function ProjectsPanel() {
  const [projects, setProjects] = useState([])
  const [loading, setLoading]   = useState(true)

  useEffect(() => {
    fetch(`${BACKEND}/api/v1/memory/projects`)
      .then(r => r.json()).then(d => setProjects(Array.isArray(d) ? d : d.projects || []))
      .catch(() => setProjects([]))
      .finally(() => setLoading(false))
  }, [])

  const statusColor = { active: C.green, paused: C.yellow, completed: C.blue, archived: C.textDim }
  const statusLabel = { active: 'AKTIIVNE', paused: 'PAUSIL', completed: 'VALMIS', archived: 'ARHIIV' }

  return (
    <div style={{ padding: '10px 12px', height: '100%', overflowY: 'auto', display: 'flex', flexDirection: 'column', gap: 8 }}>
      <div style={{ fontSize: 9, color: C.textDim, letterSpacing: 2 }}>PROJEKTID</div>
      {loading && <div style={{ color: C.textDim, fontSize: 12 }}>Laen...</div>}
      {!loading && projects.length === 0 && (
        <div style={{ color: C.textDim, fontSize: 12, textAlign: 'center', marginTop: 24 }}>
          <div style={{ fontSize: 24, marginBottom: 8 }}>📁</div>
          Projekte pole. Räägi JARVISELE projekti alustamiseks.
        </div>
      )}
      {projects.map(p => (
        <div key={p.id || p.name} style={{
          background: '#ffffff06', border: `1px solid ${C.border}`,
          borderLeft: `3px solid ${statusColor[p.status] || C.border}`,
          borderRadius: 6, padding: '7px 10px',
        }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <span style={{ fontSize: 12, color: C.text, fontWeight: 600 }}>{p.name}</span>
            <span style={{ fontSize: 8, color: statusColor[p.status] || C.textDim, letterSpacing: 1 }}>{statusLabel[p.status] || (p.status || '').toUpperCase()}</span>
          </div>
          {p.description && <div style={{ fontSize: 10, color: C.textDim, marginTop: 2 }}>{p.description}</div>}
          {p.updated_at && (
            <div style={{ fontSize: 9, color: '#444', marginTop: 3 }}>
              {new Date(p.updated_at).toLocaleDateString('et-EE', { day: 'numeric', month: 'short', year: 'numeric' })}
            </div>
          )}
        </div>
      ))}
    </div>
  )
}

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

function SettingsPanel({ prefs, setPrefs, onResetWizard }) {
  const row = (label, children) => (
    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '7px 0', borderBottom: `1px solid ${C.border}` }}>
      <span style={{ fontSize: 11, color: C.textDim, fontFamily: font, letterSpacing: 1 }}>{label}</span>
      <span style={{ fontSize: 11, color: C.text }}>{children}</span>
    </div>
  )
  const sel = (key, opts) => (
    <select value={prefs[key] || ''} onChange={e => setPrefs({ [key]: e.target.value })}
      style={{ background: '#000', border: `1px solid ${C.border}`, color: C.text, borderRadius: 4, padding: '2px 6px', fontSize: 10, fontFamily: font, outline: 'none' }}>
      {opts.map(o => <option key={o.value} value={o.value}>{o.label}</option>)}
    </select>
  )
  return (
    <div style={{ padding: '12px 14px', height: '100%', overflowY: 'auto', fontFamily: 'system-ui' }}>
      <div style={{ fontSize: 9, color: C.textDim, letterSpacing: 2, marginBottom: 12 }}>AI</div>
      {row('Mudel', sel('preferredAI', [
        { label: 'GPT-4o', value: 'gpt-4o' },
        { label: 'Claude Sonnet', value: 'claude-sonnet-4-6' },
        { label: 'Gemini Flash', value: 'gemini-2.5-flash' },
      ]))}

      <div style={{ fontSize: 9, color: C.textDim, letterSpacing: 2, margin: '12px 0 8px' }}>HÄÄL</div>
      {row('Keel', sel('preferredLang', [
        { label: 'Vene (ru-RU)', value: 'ru-RU' },
        { label: 'Eesti (et-EE)', value: 'et-EE' },
        { label: 'Inglise (en-US)', value: 'en-US' },
      ]))}
      {row('Hääl sees', (
        <button onClick={() => setPrefs({ voiceEnabled: !prefs.voiceEnabled })}
          style={{ background: prefs.voiceEnabled ? `${C.green}20` : '#ffffff0a', border: `1px solid ${prefs.voiceEnabled ? C.green : C.border}`, color: prefs.voiceEnabled ? C.green : C.textDim, borderRadius: 4, padding: '2px 10px', fontSize: 10, cursor: 'pointer', fontFamily: font }}>
          {prefs.voiceEnabled ? 'SEES' : 'VÄLJAS'}
        </button>
      ))}

      <div style={{ fontSize: 9, color: C.textDim, letterSpacing: 2, margin: '12px 0 8px' }}>TEAVITUSED</div>
      {row('Tase', sel('notifLevel', [
        { label: 'Kõik', value: 'info' },
        { label: 'Olulised', value: 'important' },
        { label: 'Kriitilised', value: 'critical' },
        { label: 'Vaikne', value: 'silent' },
      ]))}

      <div style={{ fontSize: 9, color: C.textDim, letterSpacing: 2, margin: '12px 0 8px' }}>VISIOON</div>
      {row('Analüüsi režiim', sel('visionMode', [
        { label: 'Automaatne', value: 'auto' },
        { label: 'BMW / Auto', value: 'bmw' },
        { label: 'Dokument', value: 'document' },
        { label: 'Paat', value: 'boat' },
      ]))}
      {row('Auto-analüüs', (
        <button onClick={() => setPrefs({ autoAnalyze: !prefs.autoAnalyze })}
          style={{ background: prefs.autoAnalyze ? `${C.green}20` : '#ffffff0a', border: `1px solid ${prefs.autoAnalyze ? C.green : C.border}`, color: prefs.autoAnalyze ? C.green : C.textDim, borderRadius: 4, padding: '2px 10px', fontSize: 10, cursor: 'pointer', fontFamily: font }}>
          {prefs.autoAnalyze ? 'SEES' : 'VÄLJAS'}
        </button>
      ))}

      <div style={{ fontSize: 9, color: C.textDim, letterSpacing: 2, margin: '12px 0 8px' }}>AR / SEADE</div>
      {row('AR profiil', sel('arProfile', [
        { label: 'Automaatne', value: 'auto' },
        { label: 'Telefon', value: 'phone' },
        { label: 'XREAL', value: 'xreal' },
        { label: 'Väline ekraan', value: 'external' },
      ]))}
      {row('Keepcenter overlay', (
        <button onClick={() => setPrefs({ keepCenterOverlay: !prefs.keepCenterOverlay })}
          style={{ background: prefs.keepCenterOverlay ? `${C.blue}20` : '#ffffff0a', border: `1px solid ${prefs.keepCenterOverlay ? C.blue : C.border}`, color: prefs.keepCenterOverlay ? C.blue : C.textDim, borderRadius: 4, padding: '2px 10px', fontSize: 10, cursor: 'pointer', fontFamily: font }}>
          {prefs.keepCenterOverlay ? 'SEES' : 'VÄLJAS'}
        </button>
      ))}

      <div style={{ fontSize: 9, color: C.textDim, letterSpacing: 2, margin: '12px 0 8px' }}>PRIVAATSUS</div>
      {row('Mälu', sel('memoryScope', [
        { label: 'Kõik salvestatakse', value: 'full' },
        { label: 'Ainult faktid', value: 'facts' },
        { label: 'Ei salvestata', value: 'none' },
      ]))}
      {row('Logid', (
        <button onClick={() => setPrefs({ logsEnabled: !prefs.logsEnabled })}
          style={{ background: prefs.logsEnabled ? `${C.green}20` : '#ffffff0a', border: `1px solid ${prefs.logsEnabled ? C.green : C.border}`, color: prefs.logsEnabled ? C.green : C.textDim, borderRadius: 4, padding: '2px 10px', fontSize: 10, cursor: 'pointer', fontFamily: font }}>
          {prefs.logsEnabled ? 'SEES' : 'VÄLJAS'}
        </button>
      ))}

      <div style={{ fontSize: 9, color: C.textDim, letterSpacing: 2, margin: '12px 0 8px' }}>SÜSTEEM</div>
      {row('Lemmik ws', sel('favoriteWorkspace', [
        { label: 'Kodu', value: 'home' }, { label: 'Töökoda', value: 'workshop' },
        { label: 'Kontor', value: 'office' }, { label: 'Kood', value: 'coding' },
        { label: 'Paat', value: 'boat' },
      ]))}
      {row('Häälestusviisard', (
        <button onClick={onResetWizard}
          style={{ background: `${C.orange}18`, border: `1px solid ${C.orange}50`, color: C.orange, borderRadius: 4, padding: '2px 10px', fontSize: 10, cursor: 'pointer', fontFamily: font }}>
          KORDA
        </button>
      ))}
      <div style={{ marginTop: 14, padding: '8px 0', borderTop: `1px solid ${C.border}`, fontSize: 9, color: '#333', letterSpacing: 1, textAlign: 'center' }}>
        ALBERT OS v2.0 · Railway + Vercel
      </div>
    </div>
  )
}

// ── Ilmateade (wttr.in, ei vaja API võtit) ───────────────────────────────────
function useWeather() {
  const [weather, setWeather] = useState(null)
  useEffect(() => {
    async function load() {
      try {
        const r = await fetch('https://wttr.in/?format=j1')
        const d = await r.json()
        const cur = d.current_condition?.[0]
        if (!cur) return
        setWeather({
          temp: cur.temp_C,
          desc: cur.weatherDesc?.[0]?.value || '',
          icon: ['☀', '⛅', '🌧', '❄', '⛈', '🌫'][Math.min(5, Math.floor((+cur.weatherCode - 100) / 100))] || '🌡',
        })
      } catch (_) {}
    }
    load()
    const t = setInterval(load, 10 * 60 * 1000) // uuenda iga 10 min
    return () => clearInterval(t)
  }, [])
  return weather
}

// ── Peamine HUD ───────────────────────────────────────────────────────────────
export default function GlassesHUD() {
  const { status, results, loading, audio, analyze, securityAlert, wsRef } = useJarvis(getDeviceId())
  const { notifs, visible: visibleNotifs, add: addNotif, dismiss, clearAll: clearNotifs } = useNotifications()
  const { device, adapter, layout, profile } = useDeviceManager()
  const { prefs, setPrefs, completeFirstLaunch } = useUserPrefs()
  const { unlocked, playing: audioPlaying, playBase64, stop: stopAudio } = useAudio()
  const weather = useWeather()
  const [sphereState, setSphereState] = useState('idle')
  const [listening, setListening]     = useState(false)
  const [interim, setInterim]         = useState('')
  const [ws, setWs]                   = useState('home')
  const {
    wins, focusedId,
    openWin, closeWin, minimizeWin, maximizeWin, pinWin, focus,
    setWinPos, setWinSize, setWinOpacity,
    applyWorkspace, applySafeWalking, snapWin, closeAll,
  } = useWindowManager(WIN_DEFS, { jarvis: true, clock: true })
  const [notes, setNotes]             = useState([])
  // Load persisted notes from backend facts (keys prefixed "note_")
  useEffect(() => {
    if (status !== 'online') return
    fetch(`${BACKEND}/api/v1/memory/facts`)
      .then(r => r.json())
      .then(facts => {
        const saved = Object.entries(facts)
          .filter(([k]) => k.startsWith('note_'))
          .sort(([a], [b]) => a.localeCompare(b))
          .map(([, v]) => v)
        if (saved.length) setNotes(saved)
      })
      .catch(() => {})
  }, [status])
  const [subtitles, setSubtitles]     = useState(false)
  const [lastIntent, setLastIntent]   = useState('general')
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

  // Heli (useAudio = mobiili AudioContext unlock fix)
  useEffect(() => {
    if (!audio) return
    playBase64(audio, () => setSphereState('idle'))
    setSphereState('speaking')
    return () => stopAudio()
  }, [audio])

  // Status notifid
  useEffect(() => {
    if (status === 'online')       addNotif('Albert OS ühendatud', 'info')
    if (status === 'disconnected') addNotif('Ühendus katkes — taasühendan...', 'important')
  }, [status])

  // XREAL: auto-skip wizard with glasses-optimal defaults (workshop = jarvis+camera+browser)
  useEffect(() => {
    if (!prefs.firstLaunchDone && (profile === 'xreal' || window.location.pathname === '/glasses')) {
      setPrefs({ preferredLang: prefs.preferredLang || 'ru-RU', preferredAI: prefs.preferredAI || 'gpt-4o', favoriteWorkspace: 'workshop' })
      completeFirstLaunch()
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [profile])

  // Päevakäivitus: taasta eelmine workspace eelistustest
  useEffect(() => {
    if (prefs.firstLaunchDone && prefs.favoriteWorkspace && WORKSPACES[prefs.favoriteWorkspace]) {
      applyWs(prefs.favoriteWorkspace)
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  // Kõnetuvastus
  const startRec = useCallback(() => {
    if (!activeRef.current) return
    const SR = window.SpeechRecognition || window.webkitSpeechRecognition
    if (!SR) return
    const r = new SR()
    r.lang = prefs.preferredLang || 'ru-RU'; r.interimResults = true; r.continuous = false
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
    const p = text.toLowerCase()
    const detectedIntent =
      p.includes('bmw') || p.includes('бмв') ? 'bmw_diagnostics' :
      p.includes('paat') || p.includes('лодк') ? 'boat_diagnostics' :
      p.includes('kood') || p.includes('код') || p.includes('function') ? 'coding' :
      p.includes('uuri') || p.includes('исследу') || p.includes('research') ? 'research' :
      p.includes('äri') || p.includes('бизнес') ? 'business' : 'general'
    setLastIntent(detectedIntent)
    analyze({ prompt: text, mode: 'default', model_hint: prefs.preferredAI })
  }

  function applyWs(id) {
    setWs(id)
    const cfg = WORKSPACES[id]
    applyWorkspace(cfg.wins)
    setPrefs({ favoriteWorkspace: id })
    addNotif(`Workspace: ${cfg.name}`, 'info')
    // Safe walking/driving: liiguta aknad servadesse, vähenda läbipaistvust
    if (id === 'driving' || id === 'walking') {
      setTimeout(applySafeWalking, 100) // pärast applyWorkspace'i
      addNotif('Turvaline režiim: aknad servadesse liigutatud', 'info')
    }
  }

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
        const openIds = Object.keys(wins).filter(k => wins[k]?.open && k !== 'jarvis')
        if (openIds.length) { minimizeWin(openIds[0]); showGestureFeedback(GESTURES.SWIPE_DOWN) }
      }),
      onGesture(GESTURES.OPEN_PALM, () => {
        openWin('jarvis'); showGestureFeedback(GESTURES.OPEN_PALM)
      }),
      onGesture(GESTURES.CLOSED_FIST, () => {
        const openIds = Object.keys(wins).filter(k => wins[k]?.open && k !== 'jarvis')
        if (openIds.length) { closeWin(openIds[openIds.length - 1]); showGestureFeedback(GESTURES.CLOSED_FIST) }
      }),
    ]
    return () => { detachTouchAdapter(); offs.forEach(off => off()) }
  }, [])

  // Safety context sünkroniseerimine workspace-ga
  useEffect(() => { setSafetyContext(ws) }, [ws])

  const isXREAL     = profile === 'xreal'
  const statusColor = { online: C.green, connecting: C.yellow, disconnected: C.red }[status]
  // XREAL: scale all text up 1.25× — optical see-through at ~2m needs larger glyphs
  const xrScale     = isXREAL ? 1.25 : 1

  // Aku tase (simuleeritud — päris iOS Battery API vajab native appi)
  const [battery, setBattery] = useState(null)
  useEffect(() => { navigator.getBattery?.().then(b => { setBattery(Math.round(b.level * 100)); b.onlevelchange = () => setBattery(Math.round(b.level * 100)) }) }, [])

  // XR seansi recovery + FPS
  const { fps, sessionRestored } = useXRSession({
    currentProfile: profile || 'phone',
    currentWorkspace: ws,
    wins,
    onRestore: (saved) => {
      if (saved.workspace) applyWs(saved.workspace)
      addNotif(`XR seanss taastatud: ${saved.workspace || '?'}`, 'info')
    },
  })

  // Esimene käivitus — näita nõustajat
  if (!prefs.firstLaunchDone) {
    return <FirstLaunchWizard onComplete={completeFirstLaunch} setPrefs={setPrefs} />
  }

  // XREAL: narrower side panel to give more window space
  const leftW = isXREAL ? 140 : 200

  return (
    <div style={{ width: '100vw', height: '100vh', background: '#000', overflow: 'hidden', position: 'relative', fontFamily: font, fontSize: `${xrScale}em` }}>
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
        {battery !== null && <HUDWidget icon="🔋" value={`${battery}%`} color={battery < 20 ? C.red : C.green} blink={battery < 20} />}

        {/* WiFi */}
        <HUDWidget icon={navigator.onLine ? '📶' : '📵'} value={navigator.onLine ? 'ON' : 'OFF'} color={navigator.onLine ? C.green : C.red} />

        {/* Ilm */}
        {weather && <HUDWidget icon={weather.icon} value={`${weather.temp}°C`} color={C.blue} label={weather.desc} />}

        {/* AI Provider */}
        <HUDWidget icon="🤖" value={status === 'online' ? (prefs.preferredAI || 'GPT-4o') : '—'} color={C.orange} />

        {/* XR seade */}
        {adapter && <HUDWidget icon="🥽" value={adapter.getLabel()} color={C.blue} label={`Profiil: ${profile}`} />}

        {/* Ühendus */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 5 }}>
          <StatusDot status={status} />
          <span style={{ fontSize: 10, color: C.textDim, fontFamily: font, letterSpacing: 1 }}>{status.toUpperCase()}</span>
        </div>

        <div style={{ flex: 1 }} />

        {/* Subtiitrid */}
        <TopBtn active={subtitles} onClick={() => setSubtitles(s => !s)} title="Subtiitrid">CC</TopBtn>

        {/* Kaamera staatus */}
        {wins['camera']?.open && <HUDWidget icon="📷" value="LIVE" color={C.red} blink />}

        {/* FPS monitor */}
        {fps !== null && <HUDWidget icon="⚡" value={`${fps}fps`} color={fps >= 55 ? C.green : fps >= 30 ? C.yellow : C.red} />}

        {/* Heli olek — näitab kui AudioContext on lukustatud */}
        {!unlocked && <HUDWidget icon="🔇" value="puuduta" color={C.yellow} label="Heli lubamiseks puuduta ekraani" blink />}
        {audioPlaying && <HUDWidget icon="🔊" value="RÄÄGIB" color={C.orange} blink />}
        {sessionRestored && <HUDWidget icon="🔄" value="TAASTATUD" color={C.blue} blink />}

        {/* Mikrofon */}
        <TopBtn active={listening} onClick={toggleMic} color={listening ? C.red : undefined}>
          {listening ? '🔴' : '🎤'}
        </TopBtn>
      </div>

      {/* ══ VASAKPANEEL — Notifid + Aktiivne projekt ══════════════════════════ */}
      <div style={{
        position: 'absolute', top: 44, left: 0, bottom: 52,
        width: leftW, padding: '10px 8px',
        background: C.bg, borderRight: `1px solid ${C.border}`,
        backdropFilter: 'blur(12px)', overflowY: 'auto', zIndex: 50,
      }}>
        {(visibleNotifs.length > 0 || !isXREAL) && (
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 8 }}>
            <span style={{ fontSize: 9, color: C.textDim, letterSpacing: 2 }}>NOTIFICATIONS</span>
            {visibleNotifs.length > 0 && (
              <button onClick={clearNotifs} style={{ background: 'none', border: 'none', color: C.textDim, fontSize: 9, cursor: 'pointer', letterSpacing: 1, fontFamily: font }}>PUHASTA</button>
            )}
          </div>
        )}
        {visibleNotifs.length === 0 && !isXREAL && <div style={{ fontSize: 11, color: '#333', textAlign: 'center', marginTop: 20 }}>Puhas</div>}
        {visibleNotifs.map(n => (
          <NotificationCard key={n.id} level={n.level} msg={n.msg} onDismiss={n.level !== 'critical' ? () => dismiss(n.id) : undefined} />
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
            <div key={id} onClick={() => focus(id)} style={{
              display: 'flex', alignItems: 'center', justifyContent: 'space-between',
              background: focusedId === id ? `${C.orange}18` : '#ffffff08',
              border: `1px solid ${focusedId === id ? C.orange + '60' : C.border}`,
              borderRadius: 5, padding: '4px 8px', marginBottom: 3,
              fontSize: 11, color: C.text, cursor: 'pointer',
              transition: 'background 0.15s, border-color 0.15s',
            }}>
              <span style={{ color: focusedId === id ? C.orange : C.text }}>{def.icon} {def.title}</span>
              <button onClick={e => { e.stopPropagation(); closeWin(id) }} style={{ background: 'none', border: 'none', color: C.textDim, cursor: 'pointer', fontSize: 11 }}>✕</button>
            </div>
        ))}
      </div>

      {/* ══ UJUVAD AKNAD ══════════════════════════════════════════════════════ */}
      <div style={{ position: 'absolute', top: 44, left: leftW, right: 160, bottom: 52, overflow: 'hidden' }}>
        {Object.entries(WIN_DEFS).map(([id, def]) => (
          <FloatWin key={id}
            winState={wins[id]}
            title={def.title} icon={def.icon}
            focused={focusedId === id}
            onClose={() => closeWin(id)}
            onMinimize={() => minimizeWin(id)}
            onMaximize={() => maximizeWin(id)}
            onPin={() => pinWin(id)}
            onFocus={() => focus(id)}
            onPos={pos => setWinPos(id, pos)}
            onSize={size => setWinSize(id, size)}
            onOpacity={o => setWinOpacity(id, o)}
            onSnap={to => snapWin(id, to)}>
            {id === 'jarvis'   && <JarvisPanel results={results} loading={loading} interim={subtitles ? interim : ''} sphereState={sphereState} intent={lastIntent} onFollowUp={txt => { setLastIntent(lastIntent); analyze({ prompt: txt, mode: 'default', model_hint: prefs.preferredAI }) }} />}
            {id === 'browser'  && <BrowserPanel />}
            {id === 'camera'   && <CameraPanel onAnalyze={(img, mode) => analyze({ image: img, mode, model_hint: prefs.preferredAI })} />}
            {id === 'notes'    && <NotesPanel notes={notes} onAdd={n => {
              setNotes(p => [n, ...p])
              wsRef.current?.send(JSON.stringify({ type: 'remember', key: `note_${Date.now()}`, value: n }))
            }} />}
            {id === 'youtube'  && <YouTubePanel />}
            {id === 'clock'    && <ClockPanel />}
            {id === 'plugins'  && <PluginsPanel />}
            {id === 'settings' && <SettingsPanel prefs={prefs} setPrefs={setPrefs} onResetWizard={() => setPrefs({ firstLaunchDone: false })} />}
            {id === 'projects' && <ProjectsPanel />}
          </FloatWin>
        ))}

        {/* AR keepCenterClear — näitab tsentraalse vaatevälja piiri */}
        {layout?.keepCenterClear && (
          <div style={{
            position: 'absolute', top: '30%', left: '20%', right: '20%', bottom: '25%',
            border: `1px dashed ${C.border}`,
            borderRadius: 12, pointerEvents: 'none', zIndex: 5,
          }} />
        )}

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
        position: 'absolute', bottom: 0, left: leftW, right: 160, height: 52,
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
          <button key={id} tabIndex={0} onKeyDown={e => e.key === 'Enter' && openWin(id)} onClick={() => openWin(id)} style={{
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

        {/* Projektid nupp */}
        <button onClick={() => openWin('projects')} style={{
          display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 2,
          background: wins['projects']?.open ? `${C.orange}20` : 'none',
          border: `1px solid ${wins['projects']?.open ? C.orange : C.border}`,
          borderRadius: 8, padding: '5px 10px', cursor: 'pointer',
          color: wins['projects']?.open ? C.orange : C.textDim, minWidth: 56,
        }}>
          <span style={{ fontSize: 16 }}>📁</span>
          <span style={{ fontSize: 8, letterSpacing: 1, fontFamily: font }}>PROJEKTID</span>
        </button>

        {/* Seaded nupp */}
        <button onClick={() => openWin('settings')} style={{
          display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 2,
          background: wins['settings']?.open ? `${C.textDim}20` : 'none',
          border: `1px solid ${wins['settings']?.open ? C.textDim : C.border}`,
          borderRadius: 8, padding: '5px 10px', cursor: 'pointer',
          color: wins['settings']?.open ? C.text : C.textDim, minWidth: 56,
        }}>
          <span style={{ fontSize: 16 }}>⚙</span>
          <span style={{ fontSize: 8, letterSpacing: 1, fontFamily: font }}>SEADED</span>
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
        @keyframes fadeIn    { from { opacity: 0; transform: scale(0.97); } to { opacity: 1; transform: scale(1); } }
        @keyframes winOpen   { from { opacity: 0; transform: scale(0.95) translateY(6px); } to { opacity: 1; transform: scale(1) translateY(0); } }
        @keyframes winClose  { from { opacity: 1; transform: scale(1) translateY(0); } to { opacity: 0; transform: scale(0.95) translateY(6px); } }
        @keyframes blink     { 50% { opacity: 0.2; } }
        @keyframes pulse     { 50% { opacity: 0.4; } }
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
