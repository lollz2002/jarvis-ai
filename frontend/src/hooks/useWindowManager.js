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
    closeAll,
  }
}
