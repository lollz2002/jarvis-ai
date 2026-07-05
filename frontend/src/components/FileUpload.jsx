import { useRef } from 'react'

export default function FileUpload({ onFile, disabled }) {
  const inputRef = useRef(null)

  async function handleFile(file) {
    if (!file) return
    const reader = new FileReader()
    reader.onload = (e) => {
      const content = e.target.result
      // Teksti failid loe otse, pildid base64-na
      if (file.type.startsWith('image/')) {
        const b64 = content.split(',')[1]
        onFile({ type: 'image', data: b64, mime: file.type, name: file.name })
      } else {
        // PDF, txt, doc jne — saada tekst
        onFile({ type: 'text', data: content, name: file.name })
      }
    }
    if (file.type.startsWith('image/')) {
      reader.readAsDataURL(file)
    } else {
      reader.readAsText(file, 'utf-8')
    }
  }

  function handleDrop(e) {
    e.preventDefault()
    const file = e.dataTransfer.files[0]
    if (file) handleFile(file)
  }

  return (
    <div
      className="file-upload"
      onDrop={handleDrop}
      onDragOver={e => e.preventDefault()}
      onClick={() => !disabled && inputRef.current?.click()}
      title="Lohista fail siia või kliki"
    >
      📎
      <input
        ref={inputRef}
        type="file"
        style={{ display: 'none' }}
        accept="image/*,.pdf,.txt,.md,.doc,.docx,.csv"
        onChange={e => handleFile(e.target.files[0])}
        disabled={disabled}
      />
    </div>
  )
}
