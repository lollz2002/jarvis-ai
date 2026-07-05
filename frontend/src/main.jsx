import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './index.css'
import App from './App.jsx'
import GlassesHUD from './GlassesHUD.jsx'

function shouldShowGlasses() {
  if (window.location.pathname === '/glasses') return true
  try {
    const p = JSON.parse(localStorage.getItem('albert_os_prefs') || '{}')
    return p.glassesMode === true
  } catch { return false }
}

createRoot(document.getElementById('root')).render(
  <StrictMode>{shouldShowGlasses() ? <GlassesHUD /> : <App />}</StrictMode>
)
