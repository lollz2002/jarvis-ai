import { useRef, useEffect, useImperativeHandle, forwardRef, useState } from 'react'

const Camera = forwardRef(function Camera(_, ref) {
  const videoRef = useRef(null)
  const canvasRef = useRef(null)
  const [active, setActive] = useState(false)

  useEffect(() => {
    navigator.mediaDevices?.getUserMedia({ video: { facingMode: 'environment' }, audio: false })
      .then(stream => { if (videoRef.current) { videoRef.current.srcObject = stream; setActive(true) } })
      .catch(() => {})
    return () => videoRef.current?.srcObject?.getTracks().forEach(t => t.stop())
  }, [])

  useImperativeHandle(ref, () => ({
    capture() {
      if (!videoRef.current || !canvasRef.current) return null
      const v = videoRef.current, c = canvasRef.current
      c.width = v.videoWidth; c.height = v.videoHeight
      c.getContext('2d').drawImage(v, 0, 0)
      return c.toDataURL('image/jpeg', 0.85).split(',')[1]
    }
  }))

  return (
    <div className="camera-wrap">
      <video ref={videoRef} autoPlay playsInline muted className="camera-video" />
      <canvas ref={canvasRef} style={{ display: 'none' }} />
      {active && <span className="cam-live">● REC</span>}
      {!active && <div className="cam-off">Kaamera puudub</div>}
    </div>
  )
})

export default Camera
