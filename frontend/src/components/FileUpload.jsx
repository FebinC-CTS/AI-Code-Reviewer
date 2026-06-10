import { useState, useRef, useCallback } from 'react'
import { UploadCloud, FileCode, X, AlertCircle } from 'lucide-react'

const ALLOWED_EXT = new Set(['.js','.ts','.jsx','.tsx','.css','.scss','.sass','.html','.json','.py','.java','.zip'])

const fmt = (b) => b < 1024 ? `${b} B` : b < 1048576 ? `${(b/1024).toFixed(1)} KB` : `${(b/1048576).toFixed(1)} MB`
const ext = (name) => { const i = name.lastIndexOf('.'); return i >= 0 ? name.slice(i).toLowerCase() : '' }

export default function FileUpload({ onSubmit, isLoading }) {
  const [files, setFiles] = useState([])
  const [drag, setDrag] = useState(false)
  const [error, setError] = useState('')
  const inputRef = useRef(null)

  const addFiles = useCallback((incoming) => {
    setError('')
    const rejected = []
    const valid = incoming.filter(f => {
      if (!ALLOWED_EXT.has(ext(f.name))) { rejected.push(f.name); return false }
      if (f.size > 100 * 1024 * 1024) { rejected.push(`${f.name} (>100 MB)`); return false }
      return true
    })
    if (rejected.length) setError(`Skipped: ${rejected.slice(0, 3).join(', ')}${rejected.length > 3 ? '…' : ''}`)
    setFiles(prev => {
      const names = new Set(prev.map(f => f.name))
      return [...prev, ...valid.filter(f => !names.has(f.name))]
    })
  }, [])

  const onDrop = (e) => { e.preventDefault(); setDrag(false); addFiles(Array.from(e.dataTransfer.files)) }
  const onInput = (e) => { addFiles(Array.from(e.target.files)); e.target.value = '' }

  return (
    <div className="card" style={{ maxWidth: 680, margin: '0 auto' }}>
      <p style={{ fontWeight: 600, marginBottom: '1rem', color: 'var(--text)' }}>Upload Code Files</p>

      {/* Drop zone */}
      <div
        onDrop={onDrop}
        onDragOver={(e) => { e.preventDefault(); setDrag(true) }}
        onDragLeave={() => setDrag(false)}
        onClick={() => inputRef.current?.click()}
        style={{
          border: `2px dashed ${drag ? 'var(--accent)' : 'var(--border)'}`,
          borderRadius: 'var(--radius)',
          padding: '2.25rem 1rem',
          textAlign: 'center',
          cursor: 'pointer',
          background: drag ? 'var(--accent-light)' : 'var(--surface2)',
          transition: 'all 0.15s',
          marginBottom: '1rem',
        }}
      >
        <UploadCloud size={36} style={{ color: drag ? 'var(--accent)' : 'var(--text-light)', marginBottom: '0.6rem' }} />
        <p style={{ fontWeight: 600, fontSize: '14px', marginBottom: '0.3rem', color: 'var(--text)' }}>
          Drop files here or <span style={{ color: 'var(--accent)' }}>browse</span>
        </p>
        <p style={{ color: 'var(--text-muted)', fontSize: '12px' }}>
          .js .ts .jsx .tsx .css .scss .html .json .py .java .zip &nbsp;·&nbsp; Max 100 MB
        </p>
        <input ref={inputRef} type="file" multiple
          accept=".js,.ts,.jsx,.tsx,.css,.scss,.sass,.html,.json,.py,.java,.zip"
          onChange={onInput} style={{ display: 'none' }} />
      </div>

      {error && (
        <div style={{
          display: 'flex', alignItems: 'center', gap: '0.5rem', fontSize: '12px',
          color: 'var(--high)', background: 'var(--high-bg)', border: '1px solid var(--high-border)',
          borderRadius: 'var(--radius)', padding: '0.5rem 0.8rem', marginBottom: '0.75rem',
        }}>
          <AlertCircle size={14} /> {error}
        </div>
      )}

      {files.length > 0 && (
        <div style={{ marginBottom: '1rem' }}>
          <p style={{ fontSize: '12px', color: 'var(--text-muted)', marginBottom: '0.4rem' }}>
            {files.length} file{files.length !== 1 ? 's' : ''} selected
          </p>
          <div style={{ maxHeight: 180, overflowY: 'auto', border: '1px solid var(--border)', borderRadius: 'var(--radius)' }}>
            {files.map((file, i) => (
              <div key={i} style={{
                display: 'flex', alignItems: 'center', justifyContent: 'space-between',
                padding: '0.45rem 0.75rem',
                borderBottom: i < files.length - 1 ? '1px solid var(--border)' : 'none',
                fontSize: '12.5px',
              }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '0.4rem', minWidth: 0 }}>
                  <FileCode size={13} style={{ flexShrink: 0, color: 'var(--accent)' }} />
                  <span title={file.name} style={{
                    overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap',
                    maxWidth: 380, color: 'var(--text)',
                  }}>{file.name}</span>
                  <span style={{ color: 'var(--text-light)', flexShrink: 0 }}>{fmt(file.size)}</span>
                </div>
                <button className="btn-ghost" onClick={(e) => { e.stopPropagation(); setFiles(p => p.filter((_, j) => j !== i)) }}
                  style={{ padding: '0.15rem', minWidth: 0 }}>
                  <X size={13} />
                </button>
              </div>
            ))}
          </div>
        </div>
      )}

      <div style={{ display: 'flex', gap: '0.6rem' }}>
        <button className="btn-primary" onClick={() => { if (!files.length) { setError('Select at least one file.'); return } onSubmit(files) }}
          disabled={isLoading || files.length === 0}>
          {isLoading ? <><span className="spinner" /> Analyzing…</> : <><UploadCloud size={14} /> Analyze Code</>}
        </button>
        {files.length > 0 && !isLoading && (
          <button className="btn-secondary" onClick={() => setFiles([])}>Clear</button>
        )}
      </div>
    </div>
  )
}
