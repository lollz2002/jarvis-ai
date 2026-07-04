/**
 * Albert OS — XR Adapter Layer
 * Spek: 18_ANDROID_XR_AND_XREAL.md
 *
 * Hierarhia:
 *   Application → DeviceManager → XRAdapter → Hardware SDK
 *
 * Uue seadme lisamine = uus adapter klass, ei muuda rakenduse koodi.
 */

// ── AR Profiilid ──────────────────────────────────────────────────────────────
export const AR_PROFILES = {
  PHONE:            'phone',           // puuteekraan, portree
  EXTERNAL_DISPLAY: 'external_display',// suur ujuv desktop
  XREAL:            'xreal',           // läbipaistev AR, hääl-esik
  ANDROID_XR:       'android_xr',     // tulevane natiiv spatial
  DESKTOP:          'desktop',         // lauaarvuti simulaator
}

// ── Baasadapter ───────────────────────────────────────────────────────────────
class BaseXRAdapter {
  get name()    { return 'base' }
  get profile() { return AR_PROFILES.PHONE }

  /** Tagastab true kui seade on selle adapteri jaoks. */
  static detect() { return false }

  /** Sensor-andmed mis on selle seadme jaoks saadaval. */
  async getSensors() {
    return {
      headOrientation: false,
      handTracking:    false,
      eyeTracking:     false,
      spatialAnchors:  false,
      depthSensor:     false,
    }
  }

  /** Kuhu suunata audio väljund. */
  getAudioRouting() {
    return 'phone_speaker' // phone_speaker | glasses_speaker | bluetooth
  }

  /** Milliseid kaamerate allikaid toetab. */
  getCameraSources() {
    return ['phone_back', 'phone_front']
  }

  /** Akendepaigutuse reeglid selle profiiliga. */
  getLayoutRules() {
    return {
      keepCenterClear:    false,
      pinHUDToTop:        false,
      windowsAtEyeLevel:  false,
      notifAvoidCenter:   false,
      safeWalkingReduced: false,
    }
  }

  /** Seadme inim-loetav nimi. */
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

  static detect(info) {
    return info.isXREAL
  }

  async getSensors() {
    return {
      headOrientation: true,   // XREAL SDK pakub IMU andmeid
      handTracking:    false,  // Air 2 Ultra ei toeta käejälgimist
      eyeTracking:     false,
      spatialAnchors:  false,
      depthSensor:     false,
    }
  }

  getAudioRouting() { return 'glasses_speaker' }
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

// ── Android XR (tulevane) ─────────────────────────────────────────────────────
class AndroidXRAdapter extends BaseXRAdapter {
  get name()    { return 'android_xr' }
  get profile() { return AR_PROFILES.ANDROID_XR }

  static detect(info) {
    // Tulevane: navigator.xr?.isSessionSupported('immersive-ar')
    return info.hasWebXR && info.isAndroidXR
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
