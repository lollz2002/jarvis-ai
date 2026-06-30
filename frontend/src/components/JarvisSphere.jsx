import { useEffect, useRef } from 'react'
import * as THREE from 'three'

export default function JarvisSphere({ state = 'idle' }) {
  const mountRef = useRef(null)
  const stateRef = useRef(state)
  useEffect(() => { stateRef.current = state }, [state])

  useEffect(() => {
    const el = mountRef.current
    if (!el) return
    const W = el.clientWidth || 400
    const H = el.clientHeight || 400

    const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true })
    renderer.setSize(W, H)
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2))
    el.appendChild(renderer.domElement)

    const scene = new THREE.Scene()
    const camera = new THREE.PerspectiveCamera(60, W / H, 0.1, 100)
    camera.position.z = 2.8

    // ── Osakeste sfäär ──
    const COUNT = 1600
    const pos = new Float32Array(COUNT * 3)
    const col = new Float32Array(COUNT * 3)
    const golden = Math.PI * (3 - Math.sqrt(5))
    for (let i = 0; i < COUNT; i++) {
      const y = 1 - (i / (COUNT - 1)) * 2
      const r = Math.sqrt(Math.max(0, 1 - y * y))
      const theta = golden * i
      pos[i * 3]     = Math.cos(theta) * r
      pos[i * 3 + 1] = y
      pos[i * 3 + 2] = Math.sin(theta) * r
      col[i * 3]     = 1.0
      col[i * 3 + 1] = 0.6 + Math.random() * 0.4
      col[i * 3 + 2] = 0.0
    }
    const ptGeo = new THREE.BufferGeometry()
    ptGeo.setAttribute('position', new THREE.BufferAttribute(pos, 3))
    ptGeo.setAttribute('color',    new THREE.BufferAttribute(col, 3))
    const ptMat = new THREE.PointsMaterial({ size: 0.022, vertexColors: true, transparent: true, opacity: 0.9 })
    const points = new THREE.Points(ptGeo, ptMat)
    scene.add(points)

    // ── Jooned ──
    const MAX_LINES = 200
    const lp = new Float32Array(MAX_LINES * 6)
    const lineGeo = new THREE.BufferGeometry()
    lineGeo.setAttribute('position', new THREE.BufferAttribute(lp, 3))
    const lineMat = new THREE.LineBasicMaterial({ color: 0xffaa00, transparent: true, opacity: 0.2 })
    const lines = new THREE.LineSegments(lineGeo, lineMat)
    scene.add(lines)

    function buildLines() {
      let li = 0, count = 0
      for (let i = 0; i < COUNT && count < MAX_LINES; i += 3) {
        for (let j = i + 1; j < COUNT && count < MAX_LINES; j += 5) {
          const dx = pos[i*3]-pos[j*3], dy = pos[i*3+1]-pos[j*3+1], dz = pos[i*3+2]-pos[j*3+2]
          if (dx*dx+dy*dy+dz*dz < 0.12) {
            lp[li++]=pos[i*3]; lp[li++]=pos[i*3+1]; lp[li++]=pos[i*3+2]
            lp[li++]=pos[j*3]; lp[li++]=pos[j*3+1]; lp[li++]=pos[j*3+2]
            count++
          }
        }
      }
      lineGeo.attributes.position.needsUpdate = true
      lineGeo.setDrawRange(0, count * 2)
    }
    buildLines()

    // ── Ringid ──
    function addRing(tiltX, tiltZ) {
      const pts = []
      for (let i = 0; i <= 128; i++) {
        const a = (i / 128) * Math.PI * 2
        pts.push(new THREE.Vector3(Math.cos(a), 0, Math.sin(a)))
      }
      const g = new THREE.BufferGeometry().setFromPoints(pts)
      const m = new THREE.LineBasicMaterial({ color: 0xffaa00, transparent: true, opacity: 0.22 })
      const ring = new THREE.Line(g, m)
      ring.rotation.x = tiltX
      ring.rotation.z = tiltZ
      scene.add(ring)
      return ring
    }
    const ring1 = addRing(0, 0)
    const ring2 = addRing(Math.PI / 4, 0.3)
    const ring3 = addRing(-Math.PI / 5, -0.2)

    // ── Tuum ──
    const coreGeo = new THREE.SphereGeometry(0.10, 16, 16)
    const coreMat = new THREE.MeshBasicMaterial({ color: 0xffe066, transparent: true, opacity: 0.85 })
    const core = new THREE.Mesh(coreGeo, coreMat)
    scene.add(core)

    // ── Kuma ──
    const glowGeo = new THREE.SphereGeometry(1.08, 24, 24)
    const glowMat = new THREE.MeshBasicMaterial({ color: 0xffaa00, transparent: true, opacity: 0.035, side: THREE.BackSide })
    scene.add(new THREE.Mesh(glowGeo, glowMat))

    // ── Animatsioon ──
    let frame = 0, animId
    function animate() {
      animId = requestAnimationFrame(animate)
      frame++
      const t = frame * 0.01
      const s = stateRef.current

      const spd = { speaking: 0.007, thinking: 0.009, listening: 0.004, idle: 0.002 }[s] || 0.002

      points.rotation.y += spd
      points.rotation.x += spd * 0.35
      lines.rotation.copy(points.rotation)
      ring1.rotation.y += spd * 0.6
      ring2.rotation.z += spd * 0.8
      ring3.rotation.x += spd * 0.5

      if (s === 'speaking') {
        const sc = 1 + Math.sin(t * 9) * 0.07 + Math.sin(t * 14) * 0.03
        points.scale.setScalar(sc)
        ptMat.opacity = 0.95
        lineMat.opacity = 0.38
        glowMat.opacity = 0.09 + Math.sin(t * 5) * 0.04
        coreMat.opacity = 1.0
        core.scale.setScalar(1.2 + Math.sin(t * 8) * 0.5)
      } else if (s === 'thinking') {
        ptMat.opacity = 0.6 + Math.sin(t * 4) * 0.3
        lineMat.opacity = 0.3 + Math.sin(t * 7) * 0.15
        core.scale.setScalar(0.8 + Math.sin(t * 6) * 0.4)
      } else if (s === 'listening') {
        const sc = 1 + Math.sin(t * 3) * 0.04
        points.scale.setScalar(sc)
        ptMat.opacity = 0.85
        lineMat.opacity = 0.28
        core.scale.setScalar(1 + Math.sin(t * 4) * 0.3)
      } else {
        const sc = 1 + Math.sin(t * 1.5) * 0.012
        points.scale.setScalar(sc)
        ptMat.opacity = 0.75
        lineMat.opacity = 0.18
        core.scale.setScalar(0.7 + Math.sin(t * 2) * 0.2)
      }

      renderer.render(scene, camera)
    }
    animate()

    const onResize = () => {
      if (!el) return
      const w = el.clientWidth, h = el.clientHeight
      camera.aspect = w / h
      camera.updateProjectionMatrix()
      renderer.setSize(w, h)
    }
    window.addEventListener('resize', onResize)

    return () => {
      cancelAnimationFrame(animId)
      window.removeEventListener('resize', onResize)
      renderer.dispose()
      if (el.contains(renderer.domElement)) el.removeChild(renderer.domElement)
    }
  }, [])

  return <div ref={mountRef} style={{ width: '100%', height: '100%' }} />
}
