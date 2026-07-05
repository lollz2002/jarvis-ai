import { useEffect, useRef, useState, useCallback } from 'react'

const BACKEND_URL = import.meta.env.VITE_BACKEND_URL || 'https://carefree-gentleness-production-6657.up.railway.app'
const WS_URL = `${BACKEND_URL.replace(/^http/, 'ws')}/ws`

export function useJarvis(deviceId) {
  const ws = useRef(null)
  const [status, setStatus] = useState('disconnected') // disconnected | connecting | online
  const [devices, setDevices] = useState([])
  const [agents, setAgents] = useState([])
  const [results, setResults] = useState([])
  const [loading, setLoading] = useState(false)
  const [audio, setAudio] = useState(null)
  const [lastMsg, setLastMsg] = useState(null)
  const [securityAlert, setSecurityAlert] = useState(null) // { type, msg }

  const connect = useCallback(() => {
    if (ws.current?.readyState === WebSocket.OPEN) return
    setStatus('connecting')
    const socket = new WebSocket(`${WS_URL}/${deviceId}`)

    socket.onopen = () => setStatus('online')
    socket.onclose = () => {
      setStatus('disconnected')
      setTimeout(connect, 3000) // uuesti ühenda
    }
    socket.onerror = () => setStatus('disconnected')
    socket.onmessage = (e) => {
      const data = JSON.parse(e.data)
      if (data.type === 'welcome') {
        setAgents(data.agents || [])
        setDevices(data.online || [])
      } else if (data.type === 'device_joined' || data.type === 'device_left') {
        setDevices(d => data.type === 'device_joined' ? [...new Set([...d, data.device])] : d.filter(x => x !== data.device))
      } else if (data.type === 'analysis_result') {
        setResults(data.results || [])
        setLoading(false)
        if (data.audio) setAudio(data.audio)
      } else if (data.type === 'broadcast_msg' || data.type === 'direct_msg') {
        setLastMsg(data)
      } else if (data.type === 'error' || data.type === 'warning' || data.type === 'confirm_required') {
        setSecurityAlert({ type: data.type, msg: data.msg })
        setLoading(false)
        setTimeout(() => setSecurityAlert(null), 8000)
      } else if (data.type === 'browser_open') {
        window.open(data.url, '_blank')
      } else if (data.type === 'browser_search') {
        window.open(`https://www.google.com/search?q=${encodeURIComponent(data.query)}`, '_blank')
      } else if (data.type === 'browser_navigate') {
        window.location.href = data.url
      } else if (data.type === 'phone_call') {
        window.location.href = `tel:${data.number}`
      } else if (data.type === 'phone_sms') {
        window.location.href = `sms:${data.number}${data.body ? `?body=${encodeURIComponent(data.body)}` : ''}`
      } else if (data.type === 'phone_email') {
        window.location.href = `mailto:${data.to}?subject=${encodeURIComponent(data.subject||'')}&body=${encodeURIComponent(data.body||'')}`
      }
    }
    ws.current = socket
  }, [deviceId])

  useEffect(() => { connect(); return () => ws.current?.close() }, [connect])

  const analyze = useCallback((payload) => {
    if (ws.current?.readyState !== WebSocket.OPEN) return
    setLoading(true)
    setResults([])
    setAudio(null)
    ws.current.send(JSON.stringify({ type: 'analyze', ...payload }))
  }, [])

  const sendTo = useCallback((target, text) => {
    ws.current?.send(JSON.stringify({ type: 'send_to', target, text }))
  }, [])

  const broadcast = useCallback((text) => {
    ws.current?.send(JSON.stringify({ type: 'broadcast', text }))
  }, [])

  return { status, devices, agents, results, loading, audio, lastMsg, securityAlert, analyze, sendTo, broadcast, wsRef: ws }
}
