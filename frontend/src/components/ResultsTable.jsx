import { useState, useMemo } from 'react'
import { ChevronDown, ChevronRight, ChevronUp, Search, SlidersHorizontal } from 'lucide-react'

const SEV_ORDER = { High: 0, Medium: 1, Low: 2 }

function SevBadge({ s }) {
  const cls = { High: 'badge-high', Medium: 'badge-medium', Low: 'badge-low' }[s] || 'badge-low'
  return <span className={`badge ${cls}`}>{s}</span>
}

function StatCard({ label, value, color }) {
  return (
    <div style={{
      flex: '1', minWidth: 100,
      background: 'var(--surface2)',
      border: '1px solid var(--border)',
      borderRadius: 'var(--radius)',
      padding: '0.85rem 1rem',
      textAlign: 'center',
    }}>
      <p style={{ fontSize: '1.6rem', fontWeight: 700, color, lineHeight: 1.2 }}>{value}</p>
      <p style={{ fontSize: '11px', color: 'var(--text-muted)', marginTop: '0.2rem' }}>{label}</p>
    </div>
  )
}

function ExpandRow({ issue }) {
  return (
    <tr>
      <td colSpan={5} style={{ padding: '1rem 1.5rem', background: '#fafbfc', borderBottom: '1px solid var(--border)' }}>
        <div style={{ display: 'grid', gap: '0.9rem', maxWidth: 900 }}>
          {issue.explanation && <Field label="Explanation" text={issue.explanation} />}
          {issue.fix        && <Field label="Fix"         text={issue.fix}         isCode />}
          {issue.recommendation && <Field label="Recommendation" text={issue.recommendation} />}
          {issue.insights   && <Field label="Insights"    text={issue.insights} />}
        </div>
      </td>
    </tr>
  )
}

function Field({ label, text, isCode }) {
  const asCode = isCode && (text.includes('\n') || /^\s*(def |function |const |let |var |class |import |from )/.test(text.trim()))
  return (
    <div>
      <p style={{ fontSize: '11px', fontWeight: 700, color: 'var(--accent)', textTransform: 'uppercase', letterSpacing: '0.05em', marginBottom: '0.3rem' }}>
        {label}
      </p>
      {asCode
        ? <pre>{text}</pre>
        : <p style={{ fontSize: '13px', color: 'var(--text)', lineHeight: 1.65 }}>{text}</p>
      }
    </div>
  )
}

export default function ResultsTable({ issues }) {
  const [expanded, setExpanded] = useState(new Set())
  const [sort, setSort] = useState({ field: 'severity', dir: 'asc' })
  const [sev, setSev] = useState('All')
  const [src, setSrc] = useState('All')
  const [q, setQ] = useState('')

  const toggle = (i) => setExpanded(p => { const n = new Set(p); n.has(i) ? n.delete(i) : n.add(i); return n })
  const sortBy = (f) => setSort(s => ({ field: f, dir: s.field === f && s.dir === 'asc' ? 'desc' : 'asc' }))

  const rows = useMemo(() => {
    let r = [...issues]
    if (sev !== 'All') r = r.filter(i => i.severity === sev)
    if (src === 'AI') r = r.filter(i => !i.source || i.source === 'ai')
    if (src === 'Static') r = r.filter(i => i.source === 'static')
    if (q.trim()) {
      const lq = q.toLowerCase()
      r = r.filter(i => i.file.toLowerCase().includes(lq) || i.issue.toLowerCase().includes(lq) || i.explanation?.toLowerCase().includes(lq))
    }
    r.sort((a, b) => {
      const av = sort.field === 'severity' ? SEV_ORDER[a.severity] ?? 3 : a[sort.field] ?? ''
      const bv = sort.field === 'severity' ? SEV_ORDER[b.severity] ?? 3 : b[sort.field] ?? ''
      if (av < bv) return sort.dir === 'asc' ? -1 : 1
      if (av > bv) return sort.dir === 'asc' ? 1 : -1
      return 0
    })
    return r
  }, [issues, sev, src, q, sort])

  const counts = useMemo(() => ({
    High:   issues.filter(i => i.severity === 'High').length,
    Medium: issues.filter(i => i.severity === 'Medium').length,
    Low:    issues.filter(i => i.severity === 'Low').length,
  }), [issues])

  if (!issues?.length) return null

  const SortIcon = ({ f }) => sort.field !== f
    ? <ChevronDown size={11} style={{ opacity: 0.3 }} />
    : sort.dir === 'asc' ? <ChevronUp size={11} color="var(--accent)" /> : <ChevronDown size={11} color="var(--accent)" />

  const hasFilters = sev !== 'All' || src !== 'All' || q

  return (
    <div style={{ marginTop: '1rem' }}>
      {/* Summary stats */}
      <div style={{ display: 'flex', gap: '0.75rem', marginBottom: '1rem', flexWrap: 'wrap' }}>
        <StatCard label="Total Issues"   value={issues.length} color="var(--text)" />
        <StatCard label="High Severity"  value={counts.High}   color="var(--high)" />
        <StatCard label="Medium Severity" value={counts.Medium} color="var(--medium)" />
        <StatCard label="Low Severity"   value={counts.Low}    color="var(--low)" />
        <StatCard label="Files Affected" value={new Set(issues.map(i => i.file)).size} color="var(--accent)" />
      </div>

      <div className="card" style={{ padding: 0, overflow: 'hidden' }}>
        {/* Toolbar */}
        <div style={{
          display: 'flex', gap: '0.6rem', flexWrap: 'wrap', alignItems: 'center',
          padding: '0.9rem 1rem', borderBottom: '1px solid var(--border)',
        }}>
          <div style={{ position: 'relative', flex: '1', minWidth: 180 }}>
            <Search size={13} style={{ position: 'absolute', left: 9, top: '50%', transform: 'translateY(-50%)', color: 'var(--text-muted)' }} />
            <input type="text" placeholder="Search issues, files…" value={q} onChange={e => setQ(e.target.value)}
              style={{ paddingLeft: '1.8rem', width: '100%' }} />
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
            <SlidersHorizontal size={13} style={{ color: 'var(--text-muted)' }} />
            <select value={sev} onChange={e => setSev(e.target.value)}>
              <option value="All">All Severities</option>
              <option value="High">High</option>
              <option value="Medium">Medium</option>
              <option value="Low">Low</option>
            </select>
          </div>
          <select value={src} onChange={e => setSrc(e.target.value)}>
            <option value="All">All Sources</option>
            <option value="AI">AI Analysis</option>
            <option value="Static">Static Analysis</option>
          </select>
          {hasFilters && (
            <button className="btn-ghost" style={{ fontSize: '12px' }}
              onClick={() => { setSev('All'); setSrc('All'); setQ('') }}>
              Clear filters
            </button>
          )}
          <span style={{ marginLeft: 'auto', fontSize: '12px', color: 'var(--text-muted)' }}>
            {rows.length} of {issues.length}
          </span>
        </div>

        {/* Table */}
        <div style={{ overflowX: 'auto' }}>
          <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '13px' }}>
            <thead>
              <tr style={{ background: 'var(--surface2)', borderBottom: '1px solid var(--border)' }}>
                <th style={{ width: 28, padding: '0.55rem' }} />
                {[['file', 'File'], ['issue', 'Issue'], ['severity', 'Severity']].map(([f, label]) => (
                  <th key={f} onClick={() => sortBy(f)} style={{
                    padding: '0.55rem 0.75rem', textAlign: 'left', cursor: 'pointer',
                    userSelect: 'none', fontWeight: 600, color: 'var(--text-muted)',
                    fontSize: '11px', textTransform: 'uppercase', letterSpacing: '0.05em',
                    whiteSpace: 'nowrap',
                  }}>
                    {label} <SortIcon f={f} />
                  </th>
                ))}
                <th style={{ padding: '0.55rem 0.75rem', fontWeight: 600, color: 'var(--text-muted)', fontSize: '11px', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
                  Source
                </th>
              </tr>
            </thead>
            <tbody>
              {rows.length === 0 ? (
                <tr>
                  <td colSpan={5} style={{ padding: '2.5rem', textAlign: 'center', color: 'var(--text-muted)', fontSize: '13px' }}>
                    No issues match your filters.
                  </td>
                </tr>
              ) : rows.map((issue, i) => (
                <>
                  <tr key={`r-${i}`} onClick={() => toggle(i)} style={{
                    cursor: 'pointer',
                    borderBottom: '1px solid var(--border)',
                    background: expanded.has(i) ? 'var(--accent-light)' : 'var(--surface)',
                    transition: 'background 0.1s',
                  }}
                    onMouseEnter={e => { if (!expanded.has(i)) e.currentTarget.style.background = 'var(--surface2)' }}
                    onMouseLeave={e => { if (!expanded.has(i)) e.currentTarget.style.background = 'var(--surface)' }}
                  >
                    <td style={{ padding: '0.55rem 0.4rem 0.55rem 0.75rem', color: 'var(--text-muted)' }}>
                      {expanded.has(i)
                        ? <ChevronDown size={13} color="var(--accent)" />
                        : <ChevronRight size={13} />}
                    </td>
                    <td style={{ padding: '0.55rem 0.75rem', maxWidth: 220 }}>
                      <span title={issue.file} style={{
                        display: 'block', overflow: 'hidden', textOverflow: 'ellipsis',
                        whiteSpace: 'nowrap', fontSize: '12px', color: 'var(--text-muted)',
                        fontFamily: 'monospace',
                      }}>{issue.file}</span>
                    </td>
                    <td style={{ padding: '0.55rem 0.75rem' }}>{issue.issue}</td>
                    <td style={{ padding: '0.55rem 0.75rem' }}><SevBadge s={issue.severity} /></td>
                    <td style={{ padding: '0.55rem 0.75rem' }}>
                      {issue.source === 'static'
                        ? <span className="badge badge-static">Static</span>
                        : issue.source === 'error'
                        ? <span className="badge" style={{ background: 'var(--high-bg)', color: 'var(--high)', borderColor: 'var(--high-border)' }}>Error</span>
                        : null}
                    </td>
                  </tr>
                  {expanded.has(i) && <ExpandRow key={`e-${i}`} issue={issue} />}
                </>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  )
}
