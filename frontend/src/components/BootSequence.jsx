/**
 * Albert OS — Boot Sequence
 * ~2s animated overlay. Skippable by any touch/click/key.
 * Renders once per session (sessionStorage flag).
 */
import { useState, useEffect, useRef } from 'react'

const C = {
  orange: '#ffaa00',
  blue:   '#00aaff',
  green:  '#00cc66',
  text:   '#c8d8e8',
  dim:    '#446688',
  bg:     '#040810',
}

const STATUS_ITEMS = [
  { label: 'MEMORIA',  delay: 400 },
  { label: 'NEXUS',    delay: 700 },
  { label: 'DIRECTOR', delay: 1000 },
]

export default function BootSequence({ workspace = 'KODU', onDone }) {
  const [phase, setPhase]   = useState(0)   // 0=logo 1=scan 2=status 3=ws 4=fading
  const [statusIdx, setStatusIdx] = useState(-1)
  const [done, setDone]     = useState(false)
  const doneRef = useRef(false)

  function skip() {
    if (doneRef.current) return
    doneRef.current = true
    setDone(true)
    setTimeout(onDone, 350)
  }

  useEffect(() => {
    const timers = []
    timers.push(setTimeout(() => setPhase(1), 300))   // scan line starts
    timers.push(setTimeout(() => setPhase(2), 700))   // status items
    STATUS_ITEMS.forEach((s, i) => {
      timers.push(setTimeout(() => setStatusIdx(i), s.delay))
    })
    timers.push(setTimeout(() => setPhase(3), 1300))  // workspace name
    timers.push(setTimeout(() => setPhase(4), 1700))  // begin fade
    timers.push(setTimeout(() => {
      if (!doneRef.current) { doneRef.current = true; setDone(true); onDone() }
    }, 2100))
    return () => timers.forEach(clearTimeout)
  }, [])

  if (done) return null

  return (
    <div
      onClick={skip}
      onTouchStart={skip}
      onKeyDown={skip}
      tabIndex={0}
      style={{
        position: 'fixed', inset: 0, zIndex: 9999,
        background: C.bg,
        display: 'flex', flexDirection: 'column',
        alignItems: 'center', justifyContent: 'center',
        cursor: 'pointer',
        opacity: phase === 4 ? 0 : 1,
        transition: phase === 4 ? 'opacity 0.4s ease' : 'none',
      }}
    >
      {/* Scan line */}
      {phase >= 1 && (
        <div style={{
          position: 'absolute', left: 0, right: 0, height: 1,
          background: `linear-gradient(90deg, transparent, ${C.blue}80, ${C.blue}, ${C.blue}80, transparent)`,
          animation: 'bootScan 0.9s ease-in-out forwards',
          pointerEvents: 'none',
        }} />
      )}

      {/* Logo */}
      <div style={{
        fontSize: 36, letterSpacing: 16, color: C.orange, fontFamily: 'monospace',
        fontWeight: 700, marginBottom: 12,
        animation: 'bootLogo 0.5s ease forwards',
      }}>
        ALBERT OS
      </div>

      <div style={{
        fontSize: 10, letterSpacing: 5, color: C.dim, fontFamily: 'monospace',
        marginBottom: 40,
        opacity: phase >= 1 ? 1 : 0, transition: 'opacity 0.4s',
      }}>
        GLASSES RUNTIME v3
      </div>

      {/* Status checks */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: 8, minHeight: 80 }}>
        {STATUS_ITEMS.map((s, i) => (
          <div key={s.label} style={{
            display: 'flex', gap: 16, alignItems: 'center',
            opacity: statusIdx >= i ? 1 : 0,
            transform: statusIdx >= i ? 'translateX(0)' : 'translateX(-12px)',
            transition: 'all 0.25s ease',
            fontFamily: 'monospace',
          }}>
            <span style={{ fontSize: 9, letterSpacing: 3, color: C.dim, width: 80 }}>{s.label}</span>
            <span style={{ fontSize: 9, letterSpacing: 2, color: C.green }}>OK</span>
            <div style={{ width: 40, height: 1, background: `${C.green}60` }} />
          </div>
        ))}
      </div>

      {/* Workspace label */}
      {phase >= 3 && (
        <div style={{
          marginTop: 40, fontSize: 11, letterSpacing: 4, color: C.blue,
          fontFamily: 'monospace',
          animation: 'bootWs 0.4s ease forwards',
        }}>
          LAADIN: {workspace.toUpperCase()}
        </div>
      )}

      {/* Skip hint */}
      <div style={{
        position: 'absolute', bottom: 32,
        fontSize: 9, letterSpacing: 2, color: C.dim, fontFamily: 'monospace',
        opacity: phase >= 1 ? 0.6 : 0, transition: 'opacity 0.5s',
      }}>
        PUUDUTA JÄTKAMISEKS
      </div>

      <style>{`
        @keyframes bootLogo {
          from { opacity: 0; letter-spacing: 24px; }
          to   { opacity: 1; letter-spacing: 16px; }
        }
        @keyframes bootScan {
          from { top: 0%; }
          to   { top: 100%; }
        }
        @keyframes bootWs {
          from { opacity: 0; transform: translateY(8px); }
          to   { opacity: 1; transform: translateY(0); }
        }
      `}</style>
    </div>
  )
}
