import { useState, useCallback } from 'react'
import { Scan, AlertCircle, RefreshCw, ShieldCheck } from 'lucide-react'
import FileUpload from './components/FileUpload'
import ProgressBar from './components/ProgressBar'
import ResultsTable from './components/ResultsTable'
import ExportButtons from './components/ExportButtons'
import { uploadFiles, pollUntilDone } from './services/api'

export default function App() {
  const [phase, setPhase] = useState('idle')   // idle | uploading | polling | done | error
  const [sessionId, setSessionId] = useState(null)
  const [status, setStatus] = useState(null)
  const [results, setResults] = useState(null)
  const [error, setError] = useState('')

  const reset = useCallback(() => {
    setPhase('idle')
    setSessionId(null)
    setStatus(null)
    setResults(null)
    setError('')
  }, [])

  const handleSubmit = useCallback(async (files) => {
    reset()
    setPhase('uploading')
    setStatus({ status: 'uploading', progress: { total: 0, processed: 0, current: '' }, errors: [], cached: false })

    try {
      const { session_id } = await uploadFiles(files)
      setSessionId(session_id)
      setPhase('polling')

      const finalResults = await pollUntilDone(session_id, setStatus, 1500)
      setResults(finalResults)
      setStatus(prev => ({ ...prev, cached: finalResults.cached || false }))
      setPhase('done')
    } catch (err) {
      setError(err.message || 'An unexpected error occurred.')
      setPhase('error')
    }
  }, [reset])

  const isLoading = phase === 'uploading' || phase === 'polling'

  return (
    <div style={{ minHeight: '100vh', display: 'flex', flexDirection: 'column' }}>
      {/* Header */}
      <header style={{
        background: 'var(--surface)',
        borderBottom: '1px solid var(--border)',
        padding: '0 2rem',
        height: 56,
        display: 'flex',
        alignItems: 'center',
        gap: '0.6rem',
        position: 'sticky',
        top: 0,
        zIndex: 10,
        boxShadow: 'var(--shadow-sm)',
      }}>
        <ShieldCheck size={22} color="var(--accent)" strokeWidth={2.5} />
        <span style={{ fontWeight: 700, fontSize: '1rem', color: 'var(--text)', letterSpacing: '-0.01em' }}>
          CodeInspect
        </span>
        <span style={{
          marginLeft: '0.35rem',
          fontSize: '11px',
          fontWeight: 500,
          background: 'var(--accent-light)',
          color: 'var(--accent)',
          borderRadius: '4px',
          padding: '1px 6px',
        }}>AI</span>
        <div style={{ flex: 1 }} />
        <span style={{ fontSize: '12px', color: 'var(--text-muted)' }}>
          Powered by Claude
        </span>
      </header>

      {/* Main */}
      <main style={{ flex: 1, maxWidth: 1100, width: '100%', margin: '0 auto', padding: '2rem 1.5rem' }}>
        {/* Upload panel — hide when done */}
        {phase !== 'done' && (
          <FileUpload onSubmit={handleSubmit} isLoading={isLoading} />
        )}

        {/* Progress */}
        {status && phase !== 'done' && (
          <ProgressBar status={status} issueCount={results?.issues?.length} />
        )}

        {/* Error banner */}
        {phase === 'error' && error && (
          <div style={{
            maxWidth: 680, margin: '1.5rem auto',
            display: 'flex', gap: '0.75rem',
            padding: '1rem 1.25rem',
            background: 'var(--high-bg)',
            border: '1px solid var(--high-border)',
            borderRadius: 'var(--radius)',
            color: 'var(--high)',
          }}>
            <AlertCircle size={18} style={{ flexShrink: 0, marginTop: 2 }} />
            <div>
              <p style={{ fontWeight: 600, marginBottom: '0.2rem' }}>Analysis failed</p>
              <p style={{ fontSize: '13px', color: '#b91c1c' }}>{error}</p>
              <button className="btn-secondary" onClick={reset}
                style={{ marginTop: '0.75rem', fontSize: '12px' }}>
                <RefreshCw size={13} /> Try Again
              </button>
            </div>
          </div>
        )}

        {/* Results */}
        {phase === 'done' && results && (
          <>
            {status?.cached && (
              <div style={{
                maxWidth: 680, margin: '0 auto 1rem',
                display: 'flex', alignItems: 'center', gap: '0.5rem',
                padding: '0.6rem 1rem',
                background: 'var(--low-bg)',
                border: '1px solid var(--low-border)',
                borderRadius: 'var(--radius)',
                fontSize: '13px',
                color: 'var(--low)',
              }}>
                <span style={{ fontSize: '15px' }}>⚡</span>
                <span><strong>Instant result</strong> — loaded from cache (same files detected)</span>
              </div>
            )}
            <ExportButtons sessionId={sessionId} onReset={reset} />
            {results.issues?.length === 0 ? (
              <div className="card" style={{ marginTop: '1rem', textAlign: 'center', padding: '3rem' }}>
                <p style={{ fontSize: '2rem', marginBottom: '0.5rem' }}>✅</p>
                <p style={{ fontSize: '1rem', fontWeight: 600, color: 'var(--low)' }}>No issues found</p>
                <p style={{ color: 'var(--text-muted)', marginTop: '0.4rem', fontSize: '13px' }}>
                  Your code looks clean. Great work!
                </p>
                <button className="btn-secondary" onClick={reset} style={{ marginTop: '1.25rem' }}>
                  Analyze Another Codebase
                </button>
              </div>
            ) : (
              <ResultsTable issues={results.issues} />
            )}
          </>
        )}
      </main>

      <footer style={{
        borderTop: '1px solid var(--border)',
        padding: '0.9rem 2rem',
        textAlign: 'center',
        fontSize: '12px',
        color: 'var(--text-light)',
        background: 'var(--surface)',
      }}>
        CodeInspect — AI-powered code analysis
      </footer>
    </div>
  )
}
