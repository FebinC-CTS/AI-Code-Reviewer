import { Loader2, CheckCircle2, XCircle } from 'lucide-react'

const LABELS = {
  uploading: 'Uploading files…',
  extracting: 'Extracting archive…',
  static_analysis: 'Running static analysis…',
  ai_analysis: 'AI analysis in progress…',
  analyzing: 'Preparing files…',
  complete: 'Analysis complete',
  error: 'Analysis failed',
}

export default function ProgressBar({ status, issueCount }) {
  if (!status?.status) return null

  const { status: s, progress, errors } = status
  const pct = progress?.total > 0 ? Math.round((progress.processed / progress.total) * 100) : 0
  const done = s === 'complete' || s === 'error'

  return (
    <div className="card" style={{ maxWidth: 680, margin: '1.25rem auto' }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
        {s === 'complete'
          ? <CheckCircle2 size={18} color="var(--low)" />
          : s === 'error'
          ? <XCircle size={18} color="var(--high)" />
          : <Loader2 size={18} color="var(--accent)" style={{ animation: 'spin 1s linear infinite' }} />
        }
        <div style={{ flex: 1 }}>
          <p style={{ fontWeight: 600, fontSize: '13.5px' }}>{LABELS[s] || `${s}…`}</p>
          {progress?.current && !done && (
            <p style={{ fontSize: '12px', color: 'var(--text-muted)', marginTop: '0.1rem' }}>
              {progress.current}
            </p>
          )}
        </div>
        {s === 'complete' && issueCount !== undefined && (
          <span className={`badge ${issueCount > 0 ? 'badge-high' : 'badge-low'}`}>
            {issueCount} issue{issueCount !== 1 ? 's' : ''} found
          </span>
        )}
      </div>

      {!done && progress?.total > 0 && (
        <>
          <div style={{
            height: 5, background: 'var(--border)', borderRadius: 999,
            overflow: 'hidden', margin: '0.75rem 0 0.4rem',
          }}>
            <div style={{
              height: '100%', width: `${pct}%`,
              background: 'linear-gradient(90deg, var(--accent), #818cf8)',
              borderRadius: 999, transition: 'width 0.4s ease',
            }} />
          </div>
          <p style={{ fontSize: '11px', color: 'var(--text-muted)' }}>
            {progress.processed} / {progress.total} files &nbsp;·&nbsp; {pct}%
          </p>
        </>
      )}

      {errors?.length > 0 && (
        <div style={{
          marginTop: '0.75rem', padding: '0.5rem 0.8rem',
          background: 'var(--medium-bg)', border: '1px solid var(--medium-border)',
          borderRadius: 'var(--radius)', fontSize: '12px', color: 'var(--medium)',
        }}>
          <strong>Warnings:</strong>
          <ul style={{ marginLeft: '1.1rem', marginTop: '0.25rem' }}>
            {errors.slice(0, 5).map((e, i) => <li key={i}>{e}</li>)}
            {errors.length > 5 && <li>…and {errors.length - 5} more</li>}
          </ul>
        </div>
      )}
    </div>
  )
}
