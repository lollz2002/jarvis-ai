import { useState, useRef, useEffect } from 'react'

export default function RemoteDesktop({ ws, onCommand }) {
  const [active, setActive] = useState(false)
  const [frame, setFrame] = useState(null)
  const imgRef = useRef(null)
  const canvasRef = useRef(null)

  // Kuula ekraanikaadrid
  useEffect(() => {
    if (!ws) return
    const orig = ws.onmessage
    ws.onmessage = (e) => {
      const data = JSON.parse(e.data)
      if (data.type === 'screen_frame') {
        setFrame(`data:image/jpeg;base64,${data.frame}`)
      } else {
        orig?.(e)
      }
    }
  }, [ws])

  function startStream() {
    setActive(true)
    onCommand({ type: 'analyze', prompt: 'запусти трансляцию экрана', mode: 'default' })
    ws?.send(JSON.stringify({ type: 'computer_command_direct', command: 'start_stream', args: {} }))
  }

  function stopStream() {
    setActive(false)
    setFrame(null)
    ws?.send(JSON.stringify({ type: 'computer_command_direct', command: 'stop_stream', args: {} }))
  }

  function handleClick(e) {
    if (!imgRef.current) return
    const rect = imgRef.current.getBoundingClientRect()
    const relX = (e.clientX - rect.left) / rect.width
    const relY = (e.clientY - rect.top) / rect.height
    ws?.send(JSON.stringify({
      type: 'computer_command_direct',
      command: 'mouse_click',
      args: { x: relX, y: relY, relative: true }
    }))
  }

  function handleDblClick(e) {
    if (!imgRef.current) return
    const rect = imgRef.current.getBoundingClientRect()
    ws?.send(JSON.stringify({
      type: 'computer_command_direct',
      command: 'mouse_click',
      args: {
        x: (e.clientX - rect.left) / rect.width,
        y: (e.clientY - rect.top) / rect.height,
        relative: true, double: true
      }
    }))
  }

  function handleScroll(e) {
    ws?.send(JSON.stringify({
      type: 'computer_command_direct',
      command: 'scroll',
      args: { direction: e.deltaY > 0 ? 'down' : 'up', amount: 3 }
    }))
  }

  if (!active) {
    return (
      <button className="btn-remote" onClick={startStream} title="Kaugjuhtimine">
        🖥️ ЭКРАН
      </button>
    )
  }

  return (
    <div className="remote-desktop">
      <div className="remote-header">
        <span>🖥️ Kaugjuhtimine</span>
        <button onClick={stopStream} className="remote-close">✕ Sulge</button>
      </div>
      {frame ? (
        <img
          ref={imgRef}
          src={frame}
          className="remote-frame"
          onClick={handleClick}
          onDoubleClick={handleDblClick}
          onWheel={handleScroll}
          alt="Remote desktop"
          draggable={false}
        />
      ) : (
        <div className="remote-loading">⏳ Ühendun arvutiga...</div>
      )}
      <div className="remote-hint">Kliki = hiireklõps · Topeltklõps = avab · Keri = scroll</div>
    </div>
  )
}
