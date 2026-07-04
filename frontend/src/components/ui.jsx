/**
 * Albert OS — UI Component Library
 * Spek: 16_UI_COMPONENT_LIBRARY.md
 *
 * Kasutatav nii App.jsx, GlassesHUD.jsx kui tulevaste komponentide poolt.
 */
import { useState, useEffect } from 'react'

// ── Design tokens ─────────────────────────────────────────────────────────────
export const C = {
  bg:      '#00000099',
  border:  '#ffffff18',
  blue:    '#3b82f6',
  orange:  '#f97316',
  green:   '#22c55e',
  yellow:  '#eab308',
  red:     '#ef4444',
  text:    '#f1f5f9',
  textDim: '#94a3b8',
  gold:    '#ffaa00',
}

export const FONT = "'Courier New', monospace"
export const FONT_UI = 'system-ui, sans-serif'

// ── Button ────────────────────────────────────────────────────────────────────
const BTN_VARIANTS = {
  primary:   { bg: C.orange,  border: C.orange,  color: '#000' },
  secondary: { bg: '#ffffff12', border: C.border,  color: C.text },
  danger:    { bg: C.red,     border: C.red,     color: '#fff' },
  icon:      { bg: 'none',    border: 'none',    color: C.textDim },
  success:   { bg: C.green,   border: C.green,   color: '#000' },
}

/**
 * Button — kõik variandid, kõik olekud.
 *
 * @param {string}   variant   primary | secondary | danger | icon | success
 * @param {boolean}  disabled
 * @param {boolean}  loading
 * @param {boolean}  small     väiksem suurus
 * @param {string}   title     tooltip
 */
export function Button({
  variant = 'secondary',
  disabled = false,
  loading = false,
  small = false,
  onClick,
  children,
  title,
  style,
}) {
  const [pressed, setPressed] = useState(false)
  const [hovered, setHovered] = useState(false)
  const v = BTN_VARIANTS[variant] || BTN_VARIANTS.secondary

  const opacity = disabled ? 0.4 : pressed ? 0.7 : hovered ? 1 : 0.85

  return (
    <button
      title={title}
      disabled={disabled || loading}
      onClick={onClick}
      onMouseEnter={() => setHovered(true)}
      onMouseLeave={() => { setHovered(false); setPressed(false) }}
      onMouseDown={() => setPressed(true)}
      onMouseUp={() => setPressed(false)}
      style={{
        background: v.bg,
        border: `1px solid ${v.border}`,
        color: v.color,
        borderRadius: 7,
        padding: small ? '3px 8px' : '6px 14px',
        fontSize: small ? 10 : 12,
        fontFamily: FONT,
        cursor: disabled || loading ? 'not-allowed' : 'pointer',
        opacity,
        transition: 'opacity 0.12s, transform 0.1s',
        transform: pressed ? 'scale(0.97)' : 'scale(1)',
        display: 'inline-flex',
        alignItems: 'center',
        gap: 5,
        letterSpacing: 1,
        ...style,
      }}
    >
      {loading ? <LoadingDots small /> : children}
    </button>
  )
}

// ── Loading indicators ────────────────────────────────────────────────────────
export function LoadingDots({ small = false }) {
  const [dot, setDot] = useState(0)
  useEffect(() => {
    const t = setInterval(() => setDot(d => (d + 1) % 3), 380)
    return () => clearInterval(t)
  }, [])
  const dots = ['●○○', '○●○', '○○●']
  return (
    <span style={{ color: C.blue, fontSize: small ? 9 : 11, letterSpacing: 2, fontFamily: FONT }}>
      {dots[dot]}
    </span>
  )
}

export function LoadingBar({ color = C.blue, height = 2 }) {
  return (
    <div style={{ width: '100%', height, background: `${color}30`, borderRadius: 2, overflow: 'hidden' }}>
      <div style={{
        height: '100%',
        background: color,
        borderRadius: 2,
        animation: 'albertLoadBar 1.4s ease-in-out infinite',
      }} />
      <style>{`
        @keyframes albertLoadBar {
          0%   { width: 0%;   margin-left: 0% }
          50%  { width: 60%;  margin-left: 20% }
          100% { width: 0%;   margin-left: 100% }
        }
      `}</style>
    </div>
  )
}

// ── Notification Card ─────────────────────────────────────────────────────────
const NOTIF_CLR = {
  info:      C.blue,
  warning:   C.yellow,
  error:     C.red,
  critical:  C.red,
  success:   C.green,
  important: C.orange,
}

const NOTIF_ICON = {
  info: 'ℹ', warning: '⚠', error: '✖', critical: '🔴', success: '✔', important: '!',
}

/**
 * NotificationCard — üks teavitus.
 *
 * @param {'info'|'warning'|'error'|'critical'|'success'|'important'} level
 * @param {string} msg
 * @param {function} onDismiss
 */
export function NotificationCard({ level = 'info', msg, onDismiss }) {
  const clr = NOTIF_CLR[level] || C.blue
  return (
    <div
      onClick={onDismiss}
      style={{
        background: `${clr}12`,
        border: `1px solid ${clr}40`,
        borderLeft: `3px solid ${clr}`,
        borderRadius: 5,
        padding: '6px 10px',
        marginBottom: 4,
        cursor: onDismiss ? 'pointer' : 'default',
        fontSize: 11,
        color: C.text,
        fontFamily: FONT_UI,
        display: 'flex',
        gap: 6,
        alignItems: 'flex-start',
        animation: 'fadeIn 0.2s ease',
      }}
    >
      <span style={{ color: clr, flexShrink: 0, fontSize: 11 }}>{NOTIF_ICON[level]}</span>
      <span>{msg}</span>
    </div>
  )
}

// ── HUD Widget ────────────────────────────────────────────────────────────────
/**
 * HUDWidget — väike süsteemiinfo element ülemises ribas.
 * Kasutus: <HUDWidget icon="🔋" value="87%" color={C.green} />
 */
export function HUDWidget({ icon, value, label, color, blink = false, onClick }) {
  return (
    <div
      onClick={onClick}
      title={label}
      style={{
        display: 'flex', alignItems: 'center', gap: 4,
        padding: '2px 7px',
        background: '#ffffff08',
        border: `1px solid ${color ? color + '40' : C.border}`,
        borderRadius: 5,
        cursor: onClick ? 'pointer' : 'default',
        animation: blink ? 'hudBlink 1s step-start infinite' : undefined,
      }}
    >
      {icon && <span style={{ fontSize: 11 }}>{icon}</span>}
      <span style={{ fontSize: 10, color: color || C.text, fontFamily: FONT, letterSpacing: 1 }}>{value}</span>
      <style>{`
        @keyframes hudBlink { 0%,100%{opacity:1} 50%{opacity:0.2} }
        @keyframes fadeIn { from{opacity:0;transform:translateY(-4px)} to{opacity:1;transform:none} }
      `}</style>
    </div>
  )
}

// ── Badge ─────────────────────────────────────────────────────────────────────
export function Badge({ text, color = C.blue }) {
  return (
    <span style={{
      background: `${color}20`,
      border: `1px solid ${color}60`,
      color,
      borderRadius: 4,
      padding: '1px 6px',
      fontSize: 9,
      fontFamily: FONT,
      letterSpacing: 1,
    }}>{text}</span>
  )
}

// ── Divider ───────────────────────────────────────────────────────────────────
export function Divider({ label }) {
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 8, margin: '8px 0' }}>
      <div style={{ flex: 1, height: 1, background: C.border }} />
      {label && <span style={{ fontSize: 8, color: C.textDim, fontFamily: FONT, letterSpacing: 2 }}>{label}</span>}
      <div style={{ flex: 1, height: 1, background: C.border }} />
    </div>
  )
}

// ── StatusDot ─────────────────────────────────────────────────────────────────
export function StatusDot({ status }) {
  const color = { online: C.green, connecting: C.yellow, disconnected: C.red }[status] || C.textDim
  return (
    <span style={{
      display: 'inline-block', width: 7, height: 7,
      borderRadius: '50%', background: color,
      boxShadow: `0 0 5px ${color}`,
      animation: status === 'online' ? 'hudBlink 2.5s ease infinite' : undefined,
    }} />
  )
}
