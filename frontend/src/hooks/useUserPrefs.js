/**
 * Albert OS — User Preferences
 * Spek: 19_JARVIS_USER_EXPERIENCE.md
 *
 * Salvestab ja taastab kasutaja eelistused:
 *   favoriteWorkspace, preferredAI, preferredLang,
 *   voiceEnabled, firstLaunchDone, notifPrefs
 */
import { useState, useCallback, useEffect } from 'react'

const KEY = 'albert_os_prefs'

const DEFAULTS = {
  firstLaunchDone:   false,
  favoriteWorkspace: 'home',
  preferredAI:       'gpt-4o',
  preferredLang:     'ru-RU',
  voiceEnabled:      true,
  subtitlesEnabled:  false,
  notifLevel:        'info',  // silent | info | important | critical
  theme:             'dark',
}

function load() {
  try { return { ...DEFAULTS, ...JSON.parse(localStorage.getItem(KEY) || '{}') } }
  catch { return { ...DEFAULTS } }
}

export function useUserPrefs() {
  const [prefs, setPrefsState] = useState(load)

  const setPrefs = useCallback((patch) => {
    setPrefsState(prev => {
      const next = { ...prev, ...patch }
      localStorage.setItem(KEY, JSON.stringify(next))
      return next
    })
  }, [])

  const completeFirstLaunch = useCallback(() => setPrefs({ firstLaunchDone: true }), [setPrefs])
  const resetFirstLaunch    = useCallback(() => setPrefs({ firstLaunchDone: false }), [setPrefs])

  return { prefs, setPrefs, completeFirstLaunch, resetFirstLaunch }
}
