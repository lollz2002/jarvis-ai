/**
 * Albert OS — Device Manager
 * Spek: 18_ANDROID_XR_AND_XREAL.md
 *
 * Application → DeviceManager → XRAdapter → Hardware SDK
 *
 * Eksponeerib:
 *   device     — seadme info (type, isAR, screenW/H jne)
 *   adapter    — aktiivne XR adapter eksemplar
 *   profile    — AR_PROFILES konstant
 *   sensors    — seadme sensorid
 *   layout     — akendepaigutuse reeglid
 *   switchToAR / switchToPhone
 */
import { useState, useEffect, useCallback, useRef } from 'react'
import { resolveAdapter, AR_PROFILES } from '../adapters/XRAdapter'

export { AR_PROFILES }

export function useDeviceManager() {
  const [device, setDevice] = useState({
    type:        'unknown',
    isAR:        false,
    orientation: 'portrait',
    screenW:     window.innerWidth,
    screenH:     window.innerHeight,
    hasCamera:   false,
    hasMic:      false,
    pixelRatio:  window.devicePixelRatio || 1,
    platform:    navigator.platform || '',
    userAgent:   navigator.userAgent,
  })
  const [adapter, setAdapter]   = useState(null)
  const [sensors, setSensors]   = useState(null)
  const adapterRef = useRef(null)

  const detect = useCallback(async () => {
    const w  = window.innerWidth
    const h  = window.innerHeight
    const ua = navigator.userAgent.toLowerCase()
    const isLandscape = w > h
    const ratio       = w / h
    const isMobile    = /iphone|android|ipad/.test(ua)
    const isTablet    = /ipad/.test(ua) || (isMobile && w > 768)

    const urlAR  = new URLSearchParams(window.location.search).get('ar') === '1'
    const isGlassesRoute = window.location.pathname === '/glasses'
    // XREAL Air 2 Ultra: 1920×1080 on a non-mobile host (PC/Mac via USB-C)
    const isXREAL_screen = !isMobile && window.screen.width === 1920 && window.screen.height === 1080
    const isXREAL = urlAR || isGlassesRoute || isXREAL_screen || (isLandscape && ratio > 1.6 && isMobile)

    // Väline monitor: window.screen vs window.innerWidth erinevus
    const hasExternalDisplay = typeof window.screen !== 'undefined' &&
      window.screen.width > window.innerWidth * 1.3

    // WebXR tugi (tulevane Android XR)
    const hasWebXR   = !!navigator.xr
    const isAndroidXR = false // tulevane: navigator.xr?.isSessionSupported('immersive-ar')

    const info = { isMobile, isTablet, isXREAL, hasExternalDisplay, hasWebXR, isAndroidXR }
    const resolvedAdapter = resolveAdapter(info)
    adapterRef.current = resolvedAdapter

    let type = 'desktop'
    if (isXREAL || isGlassesRoute) type = 'glasses'
    else if (isTablet)   type = 'tablet'
    else if (isMobile)   type = 'phone'

    setAdapter(resolvedAdapter)
    setDevice(prev => ({
      ...prev,
      type,
      isAR:        type === 'glasses',
      orientation: isLandscape ? 'landscape' : 'portrait',
      screenW:     w,
      screenH:     h,
      pixelRatio:  window.devicePixelRatio || 1,
      adapterName: resolvedAdapter.name,
      adapterLabel: resolvedAdapter.getLabel(),
    }))

    // Laadi sensorid async
    const s = await resolvedAdapter.getSensors()
    setSensors(s)

    if (isXREAL && !isGlassesRoute) {
      console.info('[DeviceManager] XREAL tuvastatud → AR-režiim saadaval')
    }
  }, [])

  const detectCapabilities = useCallback(async () => {
    const caps = { hasCamera: false, hasMic: false }
    try {
      const devices = await navigator.mediaDevices.enumerateDevices()
      caps.hasCamera = devices.some(d => d.kind === 'videoinput')
      caps.hasMic    = devices.some(d => d.kind === 'audioinput')
    } catch (_) {}
    setDevice(prev => ({ ...prev, ...caps }))
  }, [])

  useEffect(() => {
    detect()
    detectCapabilities()
    window.addEventListener('resize', detect)
    window.addEventListener('orientationchange', () => setTimeout(detect, 300))
    return () => {
      window.removeEventListener('resize', detect)
      window.removeEventListener('orientationchange', detect)
    }
  }, [detect, detectCapabilities])

  const switchToAR    = useCallback(() => { window.location.href = '/glasses' }, [])
  const switchToPhone = useCallback(() => { window.location.href = '/' }, [])

  const layout  = adapter?.getLayoutRules()  ?? {}
  const profile = adapter?.profile ?? AR_PROFILES.PHONE
  const audioRouting   = adapter?.getAudioRouting()   ?? 'phone_speaker'
  const cameraSources  = adapter?.getCameraSources()  ?? ['phone_back']

  return {
    device,
    adapter,
    profile,
    sensors,
    layout,
    audioRouting,
    cameraSources,
    switchToAR,
    switchToPhone,
  }
}
