/**
 * Albert OS — Gesture Engine
 * Spek: 09_GESTURE_SYSTEM.md
 *
 * Arhitektuur:
 *   Physical Input (touch/mouse/SDK)
 *     → GestureAdapter
 *       → Standard GestureEvent
 *         → Window Manager / UI
 *
 * SDK-st sõltumatu — tulevikus asenda adapter XREAL/AndroidXR vastu.
 */

// ── Standard gesture types ────────────────────────────────────────────────────
export const GESTURES = {
  PINCH:          'pinch',          // select / press button
  PINCH_DRAG:     'pinch_drag',     // move window
  TWO_HAND_PINCH: 'two_hand_pinch', // resize window
  SWIPE_LEFT:     'swipe_left',     // previous workspace
  SWIPE_RIGHT:    'swipe_right',    // next workspace
  SWIPE_UP:       'swipe_up',       // open launcher
  SWIPE_DOWN:     'swipe_down',     // hide current panel
  OPEN_PALM:      'open_palm',      // show main menu
  CLOSED_FIST:    'closed_fist',    // close selected window
  POINT_HOLD:     'point_hold',     // focus / context menu
}

// Workspacid järjekorras (swipe vasakule/paremale)
export const WS_ORDER = ['home', 'workshop', 'office', 'coding', 'boat', 'driving', 'walking']

// Confidence threshold — alla selle ignoreerime
const CONFIDENCE_THRESHOLD = 0.6

// ── GestureEvent ─────────────────────────────────────────────────────────────
export class GestureEvent {
  constructor(type, payload = {}, confidence = 1.0) {
    this.type       = type
    this.payload    = payload
    this.confidence = confidence
    this.timestamp  = Date.now()
  }
}

// ── EventBus ─────────────────────────────────────────────────────────────────
const listeners = {}

export function onGesture(type, fn) {
  if (!listeners[type]) listeners[type] = []
  listeners[type].push(fn)
  return () => { listeners[type] = listeners[type].filter(f => f !== fn) }
}

export function emitGesture(event) {
  if (event.confidence < CONFIDENCE_THRESHOLD) return
  const fns = listeners[event.type] || []
  fns.forEach(fn => fn(event))
  const all = listeners['*'] || []
  all.forEach(fn => fn(event))
}

// ── Safety guard ─────────────────────────────────────────────────────────────
let _safetyContext = 'home'

export function setSafetyContext(wsId) {
  _safetyContext = wsId
}

function isSafeToAct() {
  return !['driving', 'walking'].includes(_safetyContext)
}

// ── Touch/Mouse Gesture Adapter ───────────────────────────────────────────────
// Simuleerib touch-gesture-d kuni päris SDK saadaval.
// XREAL SDK lisamisel: asenda see adapter SDK event-idega, hoia emitGesture() kutsed samaks.

const SWIPE_THRESHOLD  = 60   // px
const SWIPE_TIME_LIMIT = 400  // ms
const HOLD_DELAY       = 600  // ms
const PINCH_THRESHOLD  = 30   // px (touch distance muutus)

let touchStart = null
let holdTimer  = null
let lastTouches = null

function getTouchDist(touches) {
  if (touches.length < 2) return 0
  const dx = touches[0].clientX - touches[1].clientX
  const dy = touches[0].clientY - touches[1].clientY
  return Math.sqrt(dx * dx + dy * dy)
}

function handleTouchStart(e) {
  const t = e.touches
  lastTouches = Array.from(t).map(p => ({ x: p.clientX, y: p.clientY }))
  touchStart = { x: t[0].clientX, y: t[0].clientY, time: Date.now(), dist: getTouchDist(t) }

  if (t.length === 1) {
    holdTimer = setTimeout(() => {
      if (!isSafeToAct()) return
      emitGesture(new GestureEvent(GESTURES.POINT_HOLD, { x: t[0].clientX, y: t[0].clientY }))
    }, HOLD_DELAY)
  }
}

function handleTouchEnd(e) {
  clearTimeout(holdTimer)
  if (!touchStart) return
  const t = e.changedTouches[0]
  const dx = t.clientX - touchStart.x
  const dy = t.clientY - touchStart.y
  const dt = Date.now() - touchStart.time
  const dist = Math.sqrt(dx * dx + dy * dy)

  if (!isSafeToAct()) { touchStart = null; return }

  if (dt < SWIPE_TIME_LIMIT && dist > SWIPE_THRESHOLD) {
    const absDx = Math.abs(dx), absDy = Math.abs(dy)
    if (absDx > absDy) {
      emitGesture(new GestureEvent(dx < 0 ? GESTURES.SWIPE_LEFT : GESTURES.SWIPE_RIGHT, { dx, dy }))
    } else {
      emitGesture(new GestureEvent(dy < 0 ? GESTURES.SWIPE_UP : GESTURES.SWIPE_DOWN, { dx, dy }))
    }
  } else if (dist < 10 && dt < 200) {
    emitGesture(new GestureEvent(GESTURES.PINCH, { x: t.clientX, y: t.clientY }))
  }
  touchStart = null
}

function handleTouchMove(e) {
  if (!touchStart || e.touches.length < 2) return
  const newDist = getTouchDist(e.touches)
  const delta = newDist - touchStart.dist
  if (Math.abs(delta) > PINCH_THRESHOLD) {
    if (!isSafeToAct()) return
    emitGesture(new GestureEvent(GESTURES.TWO_HAND_PINCH, { delta, expand: delta > 0 }, 0.8))
    touchStart.dist = newDist
  }
}

// Klaviatuur shortcutid arendajale (simuleerib gesteid)
function handleKeyboard(e) {
  if (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA') return
  if (!isSafeToAct() && !['driving', 'walking'].includes(_safetyContext)) return
  const map = {
    ArrowLeft:  GESTURES.SWIPE_LEFT,
    ArrowRight: GESTURES.SWIPE_RIGHT,
    ArrowUp:    GESTURES.SWIPE_UP,
    ArrowDown:  GESTURES.SWIPE_DOWN,
    KeyO:       GESTURES.OPEN_PALM,
    KeyX:       GESTURES.CLOSED_FIST,
  }
  if (map[e.code]) {
    e.preventDefault()
    emitGesture(new GestureEvent(map[e.code], { source: 'keyboard' }))
  }
}

// ── Adapter init / destroy ────────────────────────────────────────────────────
let _attached = false

export function attachTouchAdapter(element = document) {
  if (_attached) return
  _attached = true
  element.addEventListener('touchstart', handleTouchStart, { passive: true })
  element.addEventListener('touchend',   handleTouchEnd,   { passive: true })
  element.addEventListener('touchmove',  handleTouchMove,  { passive: true })
  window.addEventListener('keydown', handleKeyboard)
}

export function detachTouchAdapter(element = document) {
  _attached = false
  element.removeEventListener('touchstart', handleTouchStart)
  element.removeEventListener('touchend',   handleTouchEnd)
  element.removeEventListener('touchmove',  handleTouchMove)
  window.removeEventListener('keydown', handleKeyboard)
}

// ── Visuaalne tagasiside ──────────────────────────────────────────────────────
// Kutsutakse väljastpoolt (GlassesHUD) gestureEvent põhjal
export function getGestureFeedback(type) {
  const map = {
    [GESTURES.PINCH]:          '🤏 Vali',
    [GESTURES.PINCH_DRAG]:     '✊ Liiguta',
    [GESTURES.TWO_HAND_PINCH]: '↔ Muuda suurust',
    [GESTURES.SWIPE_LEFT]:     '← Eelmine',
    [GESTURES.SWIPE_RIGHT]:    '→ Järgmine',
    [GESTURES.SWIPE_UP]:       '↑ Käivita',
    [GESTURES.SWIPE_DOWN]:     '↓ Peida',
    [GESTURES.OPEN_PALM]:      '✋ Menüü',
    [GESTURES.CLOSED_FIST]:    '✊ Sulge',
    [GESTURES.POINT_HOLD]:     '👆 Kontekstimenüü',
  }
  return map[type] || type
}
