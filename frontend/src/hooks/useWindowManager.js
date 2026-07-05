/**
 * Albert OS — Window Manager Hook
 * Spek: 17_WINDOW_MANAGER.md
 *
 * Haldab kõiki ujuvaid aknaid:
 *   - Olek: open/minimized/maximized/focused
 *   - Z-order / focus
 *   - Pin (alati peal)
 *   - Opacity
 *   - Workspace persistence (localStorage)
 */
import { useState, useCallback, useRef } from 'react'

const STORAGE_KEY = 'albert_os_windows'

function loadSaved() {
  try { return JSON.parse(localStorage.getItem(STORAGE_KEY) || '{}') }
  catch { return {} }
}

function buildInitial(defs, workspaceWins) {
  const saved = loadSaved()
  return Object.fromEntries(
    Object.entries(defs).map(([id, def]) => {
      const s = saved[id] || {}
      return [id, {
        id,
        open:      workspaceWins[id] ?? false,
        minimized: false,
        maximized: false,
        pinned:    s.pinned    ?? false,
        opacity:   s.opacity   ?? 0.95,
        pos:       s.pos       ?? def.defaultPos,
        size:      s.size      ?? { w: def.w, h: def.h },
        zIndex:    20,
      }]
    })
  )
}

let _zTop = 30

export function useWindowManager(WIN_DEFS, initialWorkspaceWins = {}) {
  const [wins, setWins] = useState(() => buildInitial(WIN_DEFS, initialWorkspaceWins))
  const [focusedId, setFocusedId] = useState(null)

  // Persist position/size/opacity/pinned changes (not open state — that's workspace driven)
  const persist = useCallback((id, patch) => {
    setWins(prev => {
      const next = { ...prev, [id]: { ...prev[id], ...patch } }
      const toSave = {}
      Object.entries(next).forEach(([k, v]) => {
        toSave[k] = { pos: v.pos, size: v.size, opacity: v.opacity, pinned: v.pinned }
      })
      localStorage.setItem(STORAGE_KEY, JSON.stringify(toSave))
      return next
    })
  }, [])

  // Focus = bring to front
  const focus = useCallback((id) => {
    _zTop += 1
    setFocusedId(id)
    setWins(prev => ({
      ...prev,
      [id]: { ...prev[id], zIndex: _zTop },
    }))
  }, [])

  const openWin = useCallback((id) => {
    _zTop += 1
    setFocusedId(id)
    setWins(prev => ({
      ...prev,
      [id]: { ...prev[id], open: true, minimized: false, maximized: false, zIndex: _zTop },
    }))
  }, [])

  const closeWin = useCallback((id) => {
    setWins(prev => ({ ...prev, [id]: { ...prev[id], open: false, minimized: false, maximized: false } }))
    setFocusedId(f => f === id ? null : f)
  }, [])

  const minimizeWin = useCallback((id) => {
    setWins(prev => ({ ...prev, [id]: { ...prev[id], minimized: !prev[id].minimized, maximized: false } }))
  }, [])

  const maximizeWin = useCallback((id) => {
    setWins(prev => ({ ...prev, [id]: { ...prev[id], maximized: !prev[id].maximized, minimized: false } }))
  }, [])

  const pinWin = useCallback((id) => {
    persist(id, { pinned: !wins[id].pinned })
  }, [wins, persist])

  const setWinPos = useCallback((id, pos) => persist(id, { pos }), [persist])
  const setWinSize = useCallback((id, size) => persist(id, { size }), [persist])
  const setWinOpacity = useCallback((id, opacity) => persist(id, { opacity }), [persist])

  // Apply workspace: set which windows are open, reset layout to defaults
  const applyWorkspace = useCallback((workspaceWins) => {
    setWins(prev => {
      const saved = loadSaved()
      return Object.fromEntries(
        Object.entries(prev).map(([id, w]) => {
          const s = saved[id] || {}
          const def = WIN_DEFS[id]
          return [id, {
            ...w,
            open:      workspaceWins[id] ?? false,
            minimized: false,
            maximized: false,
            pos:       s.pos  ?? def.defaultPos,
            size:      s.size ?? { w: def.w, h: def.h },
          }]
        })
      )
    })
  }, [WIN_DEFS])

  // Close all except jarvis
  const closeAll = useCallback(() => {
    setWins(prev => Object.fromEntries(
      Object.entries(prev).map(([id, w]) => [id, { ...w, open: id === 'jarvis', minimized: false, maximized: false }])
    ))
  }, [])

  /**
   * Snap window to a named position.
   * Spek: 31_UI_BIBLE.md — Floating Window actions: Snap
   * @param {string} id  — window id
   * @param {string} to  — 'tl'|'tr'|'bl'|'br'|'left'|'right'|'center'|'top'
   */
  const snapWin = useCallback((id, to) => {
    const vw = window.innerWidth
    const vh = window.innerHeight
    const w  = wins[id]?.size?.w || WIN_DEFS[id]?.w || 320
    const h  = wins[id]?.size?.h || WIN_DEFS[id]?.h || 280
    const GAP = 8
    const positions = {
      tl:     { x: GAP,              y: GAP },
      tr:     { x: vw - w - GAP,     y: GAP },
      bl:     { x: GAP,              y: vh - h - GAP - 52 },
      br:     { x: vw - w - GAP,     y: vh - h - GAP - 52 },
      left:   { x: GAP,              y: Math.round((vh - h) / 2) },
      right:  { x: vw - w - GAP,     y: Math.round((vh - h) / 2) },
      center: { x: Math.round((vw - w) / 2), y: Math.round((vh - h) / 2) },
      top:    { x: Math.round((vw - w) / 2), y: GAP },
    }
    const pos = positions[to]
    if (pos) persist(id, { pos })
  }, [wins, WIN_DEFS, persist])

  /**
   * Safe Walking Mode — liiguta aknad servadesse, vähenda läbipaistvust.
   * Spek: 26_AR_RUNTIME_AND_RENDER_ENGINE.md
   * Avab ainult jarvis + clock, paneb teised minimiseerituks + opacity 0.5.
   */
  const applySafeWalking = useCallback(() => {
    setWins(prev => {
      const entries = Object.entries(prev)
      // Leia avatud aknad, jaota: osa vasakule servale, osa paremale
      const open = entries.filter(([, w]) => w.open).map(([id]) => id)
      const leftIds  = open.filter(id => id !== 'jarvis').slice(0, 2)
      const rightIds = open.filter(id => id !== 'jarvis').slice(2, 4)

      return Object.fromEntries(
        entries.map(([id, w]) => {
          if (!w.open) return [id, w]
          // jarvis: jää nähtavaks, väike opacity
          if (id === 'jarvis') return [id, { ...w, opacity: 0.7, minimized: false }]
          // Vasakul serval
          const li = leftIds.indexOf(id)
          if (li >= 0) return [id, { ...w, minimized: false, opacity: 0.5, pos: { x: 4, y: 60 + li * 180 } }]
          // Paremal serval
          const ri = rightIds.indexOf(id)
          if (ri >= 0) return [id, { ...w, minimized: false, opacity: 0.5,
            pos: { x: window.innerWidth - (WIN_DEFS[id]?.w || 260) - 4, y: 60 + ri * 180 } }]
          // Muud: minimeeri
          return [id, { ...w, minimized: true }]
        })
      )
    })
  }, [WIN_DEFS])

  return {
    wins,
    focusedId,
    openWin,
    closeWin,
    minimizeWin,
    maximizeWin,
    pinWin,
    focus,
    setWinPos,
    setWinSize,
    setWinOpacity,
    applyWorkspace,
    applySafeWalking,
    snapWin,
    closeAll,
  }
}
