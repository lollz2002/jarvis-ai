/**
 * Albert OS — XR Adapter Layer v2
 * Spek: 18_ANDROID_XR_AND_XREAL.md, 37_ANDROID_XR_IMPLEMENTATION_BIBLE.md
 *
 * Hierarhia:
 *   Application → DeviceManager → XRAdapter → Hardware SDK
 *
 * Uue seadme lisamine = uus adapter klass, ei muuda rakenduse koodi.
 * Äriloogika EI kutsu kunagi vendor SDK-d otse.
 */

// ── AR Profiilid ──────────────────────────────────────────────────────────────
export const AR_PROFILES = {
  PHONE:            'phone',
  EXTERNAL_DISPLAY: 'external_display',
  XREAL:            'xreal',
  ANDROID_XR:       'android_xr',
  DESKTOP:          'desktop',
}

// ── XR Session Lifecycle (37_ANDROID_XR_IMPLEMENTATION_BIBLE.md) ─────────────
export const XR_SESSION_STATE = {
  IDLE:          'idle',
  INITIALIZING:  'initializing',
  READY:         'ready',
  RUNNING:       'running',
  SUSPENDED:     'suspended',
  DISCONNECTING: 'disconnecting',
}

// Lubatud üleminekud olekumasinast
const _VALID_TRANSITIONS = {
  idle:          ['initializing'],
  initializing:  ['ready', 'idle'],
  ready:         ['running', 'idle'],
  running:       ['suspended', 'disconnecting'],
  suspended:     ['running', 'disconnecting'],
  disconnecting: ['idle'],
}

export class XRSessionLifecycle {
  constructor(adapter) {
    this.adapter   = adapter
    this.state     = XR_SESSION_STATE.IDLE
    this._listeners = []
  }

  /** Üleminek uude olekusse — vigast üleminekut ignoreeritakse. */
  transition(newState) {
    const allowed = _VALID_TRANSITIONS[this.state] || []
    if (!allowed.includes(newState)) return false
    const prev = this.state
    this.state = newState
    this._listeners.forEach(fn => fn(newState, prev))
    return true
  }

  onStateChange(fn) { this._listeners.push(fn) }

  async initialize() {
    this.transition(XR_SESSION_STATE.INITIALIZING)
    await this.adapter.initialize()
    this.transition(XR_SESSION_STATE.READY)
  }

  async start() {
    if (this.state !== XR_SESSION_STATE.READY) return
    this.transition(XR_SESSION_STATE.RUNNING)
  }

  async suspend() {
    this.transition(XR_SESSION_STATE.SUSPENDED)
  }

  async resume() {
    this.transition(XR_SESSION_STATE.RUNNING)
  }

  async disconnect() {
    this.transition(XR_SESSION_STATE.DISCONNECTING)
    await this.adapter.shutdown()
    this.transition(XR_SESSION_STATE.IDLE)
  }
}

// ── Spatial Window Contract (37_ANDROID_XR_IMPLEMENTATION_BIBLE.md) ──────────
export function createSpatialWindowContract(id, workspace = 'Home', overrides = {}) {
  return {
    id,
    workspace,
    position: { x: 0, y: 0, z: -2, ...overrides.position },
    rotation: { x: 0, y: 0, z: 0,  ...overrides.rotation },
    scale:    overrides.scale   ?? 1.0,
    opacity:  overrides.opacity ?? 0.9,
    pinned:   overrides.pinned  ?? false,
  }
}

// ── Feature Detection (37_ANDROID_XR_IMPLEMENTATION_BIBLE.md) ─────────────────
export async function detectXRFeatures() {
  const features = {
    handTracking:    false,
    eyeTracking:     false,
    spatialAnchors:  false,
    depthSensing:    false,
    passthroughVideo: false,
    cameraAvailable: false,
    webXR:           false,
    headOrientation: false,
  }
  // WebXR API
  if (typeof navigator !== 'undefined' && navigator.xr) {
    features.webXR = true
    try {
      features.handTracking = await navigator.xr.isSessionSupported('immersive-ar')
    } catch { /* not supported */ }
  }
  // Kaamerate kontroll
  if (typeof navigator !== 'undefined' && navigator.mediaDevices) {
    try {
      const devices = await navigator.mediaDevices.enumerateDevices()
      features.cameraAvailable = devices.some(d => d.kind === 'videoinput')
    } catch { /* permission denied */ }
  }
  // DeviceOrientation (pea suund)
  features.headOrientation = typeof DeviceOrientationEvent !== 'undefined'
  return features
}

// ── Baasadapter (täielik XR Adapter Interface) ────────────────────────────────
class BaseXRAdapter {
  get name()    { return 'base' }
  get profile() { return AR_PROFILES.PHONE }

  static detect() { return false }

  // ── Lifecycle (37_ANDROID_XR_IMPLEMENTATION_BIBLE.md) ──────────────────────
  async initialize() { /* vendor SDK init */ }
  async shutdown()   { /* vendor SDK cleanup */ }

  // ── Capability queries ──────────────────────────────────────────────────────
  supportsHandTracking() { return false }
  supportsEyeTracking()  { return false }

  getDisplayInfo() {
    return {
      width:       window.innerWidth,
      height:      window.innerHeight,
      pixelRatio:  window.devicePixelRatio ?? 1,
      refreshRate: 60,
      type:        'flat',
    }
  }

  getTrackingState() {
    return { quality: 'none', confidence: 0.0 }
  }

  // ── Spatial Windows ─────────────────────────────────────────────────────────
  createSpatialWindow(id, workspace = 'Home', opts = {}) {
    return createSpatialWindowContract(id, workspace, opts)
  }

  destroySpatialWindow(id) { /* vendor SDK cleanup per id */ }

  // ── Sensor-andmed ───────────────────────────────────────────────────────────
  async getSensors() {
    return {
      headOrientation: false,
      handTracking:    false,
      eyeTracking:     false,
      spatialAnchors:  false,
      depthSensor:     false,
    }
  }

  getAudioRouting() { return 'phone_speaker' }
  getCameraSources() { return ['phone_back', 'phone_front'] }

  getLayoutRules() {
    return {
      keepCenterClear:    false,
      pinHUDToTop:        false,
      windowsAtEyeLevel:  false,
      notifAvoidCenter:   false,
      safeWalkingReduced: false,
    }
  }

  getLabel() { return 'Telefon' }
}

// ── Telefon (vaikimisi) ───────────────────────────────────────────────────────
class PhoneAdapter extends BaseXRAdapter {
  get name()    { return 'phone' }
  get profile() { return AR_PROFILES.PHONE }
  static detect(info) {
    return info.isMobile && !info.isXREAL && !info.hasExternalDisplay
  }
  getLabel() { return 'Android telefon' }
}

// ── XREAL Air (praegune) ──────────────────────────────────────────────────────
class XREALAdapter extends BaseXRAdapter {
  get name()    { return 'xreal' }
  get profile() { return AR_PROFILES.XREAL }

  static detect(info) { return info.isXREAL }

  async initialize() {
    // Tulevane: XREAL Nebula SDK init
    // window.xreal?.initialize?.()
  }

  supportsHandTracking() { return false }  // Air 2 Ultra: IMU ainult
  supportsEyeTracking()  { return false }

  getDisplayInfo() {
    return {
      width: 1920, height: 1080,
      pixelRatio: window.devicePixelRatio ?? 2,
      refreshRate: 90,
      type: 'optical_see_through',
    }
  }

  getTrackingState() {
    return { quality: 'orientation_only', confidence: 0.85 }
  }

  async getSensors() {
    return {
      headOrientation: true,
      handTracking:    false,
      eyeTracking:     false,
      spatialAnchors:  false,
      depthSensor:     false,
    }
  }

  getAudioRouting()  { return 'glasses_speaker' }
  getCameraSources() { return ['phone_back', 'phone_front'] }

  getLayoutRules() {
    return {
      keepCenterClear:    true,
      pinHUDToTop:        true,
      windowsAtEyeLevel:  true,
      notifAvoidCenter:   true,
      safeWalkingReduced: true,
    }
  }

  getLabel() { return 'XREAL Air 2 Ultra' }
}

// ── Väline monitor (telefon + HDMI/DisplayPort) ───────────────────────────────
class ExternalDisplayAdapter extends BaseXRAdapter {
  get name()    { return 'external_display' }
  get profile() { return AR_PROFILES.EXTERNAL_DISPLAY }

  static detect(info) {
    return info.hasExternalDisplay && !info.isXREAL
  }

  getLayoutRules() {
    return {
      keepCenterClear:    false,
      pinHUDToTop:        true,
      windowsAtEyeLevel:  false,
      notifAvoidCenter:   false,
      safeWalkingReduced: false,
    }
  }

  getLabel() { return 'Väline monitor' }
}

// ── Android XR (tulevane natiiv spatial) ─────────────────────────────────────
class AndroidXRAdapter extends BaseXRAdapter {
  get name()    { return 'android_xr' }
  get profile() { return AR_PROFILES.ANDROID_XR }

  static detect(info) {
    return info.hasWebXR && info.isAndroidXR
  }

  async initialize() {
    // Tulevane: WebXR immersive-ar session
    if (navigator.xr) {
      try {
        const supported = await navigator.xr.isSessionSupported('immersive-ar')
        if (supported) {
          // session init reserved for future native binding
        }
      } catch { /* fallback gracefully */ }
    }
  }

  supportsHandTracking() { return true }
  supportsEyeTracking()  { return true }

  getDisplayInfo() {
    return {
      width: 2560, height: 1440,
      pixelRatio: window.devicePixelRatio ?? 2,
      refreshRate: 90,
      type: 'optical_see_through',
    }
  }

  getTrackingState() {
    return { quality: 'full_6dof', confidence: 0.95 }
  }

  async getSensors() {
    return {
      headOrientation: true,
      handTracking:    true,
      eyeTracking:     true,
      spatialAnchors:  true,
      depthSensor:     true,
    }
  }

  getAudioRouting() { return 'glasses_speaker' }

  getLayoutRules() {
    return {
      keepCenterClear:    true,
      pinHUDToTop:        true,
      windowsAtEyeLevel:  true,
      notifAvoidCenter:   true,
      safeWalkingReduced: true,
    }
  }

  getLabel() { return 'Android XR' }
}

// ── Lauaarvuti ────────────────────────────────────────────────────────────────
class DesktopAdapter extends BaseXRAdapter {
  get name()    { return 'desktop' }
  get profile() { return AR_PROFILES.DESKTOP }
  static detect(info) { return !info.isMobile }
  getLabel() { return 'Lauaarvuti' }
}

// ── Adapter registry ──────────────────────────────────────────────────────────
const ADAPTERS = [
  AndroidXRAdapter,   // kontrolli enne XREAL-i (täpsem)
  XREALAdapter,
  ExternalDisplayAdapter,
  PhoneAdapter,
  DesktopAdapter,     // vaikimisi viimane
]

/**
 * Tuvastab seadme ja tagastab vastava adapteri eksemplari.
 * @param {object} info — detect() väljund useDeviceManager-ist
 * @returns {BaseXRAdapter}
 */
export function resolveAdapter(info) {
  for (const Cls of ADAPTERS) {
    if (Cls.detect(info)) return new Cls()
  }
  return new DesktopAdapter()
}

export { PhoneAdapter, XREALAdapter, ExternalDisplayAdapter, AndroidXRAdapter, DesktopAdapter }
