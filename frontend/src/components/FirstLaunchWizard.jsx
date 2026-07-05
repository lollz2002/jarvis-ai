/**
 * Albert OS — First Launch Wizard
 * Spek: 19_JARVIS_USER_EXPERIENCE.md
 *
 * 6 sammu: Tervitus → Load → Hääl → AI → Mälu → Valmis
 */
import { useState } from 'react'
import { C, FONT as font, Button } from './ui'

const STEPS = [
  {
    id: 'welcome',
    icon: '✦',
    title: 'Tere tulemast',
    subtitle: 'Albert OS',
    body: 'Isiklik AI operatsioonisüsteem telefoni, lauaarvuti ja AR-prillide jaoks.',
  },
  {
    id: 'permissions',
    icon: '🔒',
    title: 'Load',
    subtitle: 'Vajalikud load',
    body: 'Albert OS vajab mikrofoni (hääl) ja kaamera (visuaalne analüüs) juurdepääsu. Luba küsitakse kasutamisel.',
  },
  {
    id: 'voice',
    icon: '🎤',
    title: 'Hääl',
    subtitle: 'Häälseaded',
    body: 'Vaikekeel: Vene (ru-RU). Räägi loomulikult — JARVIS tuvastab eesti, vene ja inglise keele automaatselt.',
    options: [
      { label: 'Vene (ru-RU)', value: 'ru-RU' },
      { label: 'Eesti (et-EE)', value: 'et-EE' },
      { label: 'Inglise (en-US)', value: 'en-US' },
    ],
    prefKey: 'preferredLang',
  },
  {
    id: 'ai',
    icon: '🤖',
    title: 'AI mudel',
    subtitle: 'Eelistatud AI',
    body: 'JARVIS kasutab mitut mudelit samaaegselt. Vali peamine mudel:',
    options: [
      { label: 'GPT-4o (OpenAI)', value: 'gpt-4o' },
      { label: 'Claude Sonnet (Anthropic)', value: 'claude-sonnet-4-6' },
      { label: 'Gemini Flash (Google)', value: 'gemini-2.5-flash' },
    ],
    prefKey: 'preferredAI',
  },
  {
    id: 'memory',
    icon: '🧠',
    title: 'Mälu',
    subtitle: 'Mälu eelistused',
    body: 'JARVIS jätab meelde fakte, projekte, kontakte ja märkmeid. Andmed salvestatakse lokaalselt Railway serverisse.',
  },
  {
    id: 'ready',
    icon: '✦',
    title: 'Kõik valmis',
    subtitle: 'Albert OS on valmis',
    body: 'Räägi "JARVIS" et alustada. Kasuta töölaudu vasakul paneelil. AR-režiim: külasta /glasses.',
  },
]

export default function FirstLaunchWizard({ onComplete, setPrefs }) {
  const [step, setStep] = useState(0)
  const [selections, setSelections] = useState({})

  const current = STEPS[step]
  const isLast  = step === STEPS.length - 1
  const isFirst = step === 0

  function choose(key, value) {
    setSelections(s => ({ ...s, [key]: value }))
    setPrefs({ [key]: value })
  }

  function next() {
    if (isLast) {
      onComplete()
    } else {
      setStep(s => s + 1)
    }
  }

  function back() {
    if (!isFirst) setStep(s => s - 1)
  }

  return (
    <div style={{
      position: 'fixed', inset: 0,
      background: '#000000ee',
      display: 'flex', alignItems: 'center', justifyContent: 'center',
      zIndex: 1000, fontFamily: font,
      backdropFilter: 'blur(20px)',
    }}>
      {/* Taustamuster */}
      <svg style={{ position: 'absolute', inset: 0, width: '100%', height: '100%', pointerEvents: 'none', opacity: 0.25 }}>
        <defs><pattern id="wg" width="60" height="60" patternUnits="userSpaceOnUse"><path d="M60 0L0 0 0 60" fill="none" stroke="#ffffff08" strokeWidth="0.5"/></pattern></defs>
        <rect width="100%" height="100%" fill="url(#wg)"/>
      </svg>

      <div style={{
        position: 'relative',
        width: 480, maxWidth: '92vw',
        background: '#000000cc',
        border: `1px solid ${C.border}`,
        borderRadius: 16,
        padding: '40px 36px 32px',
        animation: 'fadeIn 0.3s ease',
      }}>
        {/* Sammude indikaator */}
        <div style={{ display: 'flex', gap: 6, marginBottom: 32, justifyContent: 'center' }}>
          {STEPS.map((_, i) => (
            <div key={i} style={{
              width: i === step ? 24 : 8, height: 4,
              borderRadius: 2,
              background: i === step ? C.orange : i < step ? C.green : C.border,
              transition: 'all 0.3s ease',
            }} />
          ))}
        </div>

        {/* Ikoon */}
        <div style={{ textAlign: 'center', fontSize: 36, marginBottom: 16, color: C.orange }}>
          {current.icon}
        </div>

        {/* Pealkiri */}
        <div style={{ textAlign: 'center', marginBottom: 20 }}>
          <div style={{ fontSize: 11, color: C.textDim, letterSpacing: 4, marginBottom: 6 }}>{current.subtitle.toUpperCase()}</div>
          <div style={{ fontSize: 22, color: C.text, fontWeight: 700 }}>{current.title}</div>
        </div>

        {/* Kirjeldus */}
        <div style={{
          fontSize: 13, color: C.textDim, lineHeight: 1.7,
          textAlign: 'center', marginBottom: 24, fontFamily: 'system-ui',
        }}>
          {current.body}
        </div>

        {/* Valikud (kui olemas) */}
        {current.options && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 8, marginBottom: 24 }}>
            {current.options.map(opt => {
              const selected = (selections[current.prefKey] || (current.prefKey === 'preferredLang' ? 'ru-RU' : 'gpt-4o')) === opt.value
              return (
                <button key={opt.value} onClick={() => choose(current.prefKey, opt.value)} style={{
                  background:   selected ? `${C.orange}20` : '#ffffff08',
                  border:       `1px solid ${selected ? C.orange : C.border}`,
                  borderRadius: 8,
                  padding:      '10px 16px',
                  color:        selected ? C.orange : C.text,
                  fontSize:     13,
                  fontFamily:   font,
                  cursor:       'pointer',
                  textAlign:    'left',
                  transition:   'all 0.15s',
                }}>
                  {selected ? '◉ ' : '○ '}{opt.label}
                </button>
              )
            })}
          </div>
        )}

        {/* Nupud */}
        <div style={{ display: 'flex', gap: 10, justifyContent: 'space-between', alignItems: 'center' }}>
          <button
            onClick={back}
            disabled={isFirst}
            style={{
              background: 'none', border: `1px solid ${C.border}`,
              color: isFirst ? '#333' : C.textDim,
              borderRadius: 7, padding: '8px 18px',
              fontSize: 12, fontFamily: font,
              cursor: isFirst ? 'not-allowed' : 'pointer',
            }}
          >← Tagasi</button>

          <button
            onClick={next}
            style={{
              background: isLast ? C.green : C.orange,
              border: 'none',
              color: '#000',
              borderRadius: 7, padding: '10px 28px',
              fontSize: 13, fontFamily: font, fontWeight: 700,
              cursor: 'pointer',
              letterSpacing: 1,
              transition: 'opacity 0.15s',
            }}
          >{isLast ? '✓ Alusta' : 'Edasi →'}</button>
        </div>

        {/* Versioon */}
        <div style={{ textAlign: 'center', marginTop: 20, fontSize: 9, color: '#333', letterSpacing: 2 }}>
          ALBERT OS v2.0
        </div>
      </div>

      <style>{`
        @keyframes fadeIn { from{opacity:0;transform:scale(0.97)} to{opacity:1;transform:scale(1)} }
      `}</style>
    </div>
  )
}
