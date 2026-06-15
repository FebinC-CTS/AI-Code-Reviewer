import { useState, useRef, useEffect, useMemo, useCallback } from 'react'
import { MessageSquare, Send, Sparkles, User, Bot, X } from 'lucide-react'
import { sendChat } from '../services/api'

// Minimal markdown rendering: split out ``` fenced code blocks, keep the rest
// as whitespace-preserving text. Avoids pulling in a markdown dependency.
function renderContent(text) {
  const segments = text.split(/```/)
  return segments.map((seg, i) => {
    if (i % 2 === 1) {
      // Code block — drop an optional leading language tag line.
      const body = seg.replace(/^[a-zA-Z0-9_+-]*\n/, '')
      return <pre key={i} style={{ margin: '0.5rem 0' }}>{body.replace(/\n$/, '')}</pre>
    }
    if (!seg.trim()) return null
    return (
      <p key={i} style={{ whiteSpace: 'pre-wrap', margin: '0.25rem 0', lineHeight: 1.6 }}>
        {seg.trim()}
      </p>
    )
  })
}

function buildSuggestions(issues) {
  const list = ['Give me an executive summary of this review.']

  const high = issues.filter((i) => i.severity === 'High')
  if (high.length) {
    list.push(`What are the ${high.length} high-severity issue${high.length > 1 ? 's' : ''} and how do I fix them?`)
  } else {
    list.push('Which issues should I fix first, and why?')
  }

  list.push('Are there any security vulnerabilities in this code?')

  // Dynamic: the file with the most issues.
  const counts = {}
  issues.forEach((i) => { counts[i.file] = (counts[i.file] || 0) + 1 })
  const topFile = Object.entries(counts).sort((a, b) => b[1] - a[1])[0]?.[0]
  if (topFile) list.push(`Why does ${topFile} have the most issues?`)

  list.push('How can I improve the overall code quality?')
  return list.slice(0, 5)
}

export default function ChatPanel({ sessionId, issues = [] }) {
  const [open, setOpen] = useState(false)
  const [messages, setMessages] = useState([])
  const [input, setInput] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const scrollRef = useRef(null)

  const suggestions = useMemo(() => buildSuggestions(issues), [issues])

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: 'smooth' })
  }, [messages, busy, open])

  const send = useCallback(async (raw) => {
    const question = raw.trim()
    if (!question || busy) return
    setError('')
    setInput('')

    const history = messages.map((m) => ({ role: m.role, content: m.content }))
    const next = [...messages, { role: 'user', content: question }]
    setMessages(next)
    setBusy(true)

    try {
      const { answer } = await sendChat(sessionId, question, history)
      setMessages([...next, { role: 'assistant', content: answer || '(no response)' }])
    } catch (err) {
      const detail = err?.response?.data?.detail || err.message || 'Request failed.'
      setError(detail)
      setMessages(next) // keep the user's question; let them retry
    } finally {
      setBusy(false)
    }
  }, [busy, messages, sessionId])

  return (
    <div style={{
      position: 'fixed', right: 24, bottom: 24, zIndex: 1000,
      display: 'flex', flexDirection: 'column', alignItems: 'flex-end', gap: 12,
    }}>
      {/* Chat window */}
      {open && (
        <div
          style={{
            width: 'min(384px, calc(100vw - 48px))',
            height: 'min(560px, 70vh)',
            display: 'flex', flexDirection: 'column',
            background: 'var(--surface)',
            border: '1px solid var(--border)',
            borderRadius: 14,
            boxShadow: '0 12px 32px rgba(15,23,42,0.18), 0 4px 8px rgba(15,23,42,0.08)',
            overflow: 'hidden',
            animation: 'chatPop 0.18s ease-out',
          }}
        >
          {/* Header */}
          <div style={{
            display: 'flex', alignItems: 'center', gap: '0.6rem',
            padding: '0.85rem 1rem', borderBottom: '1px solid var(--border)',
            background: 'var(--surface2)', flexShrink: 0,
          }}>
            <div style={{
              display: 'grid', placeItems: 'center', width: 30, height: 30,
              borderRadius: 8, background: 'var(--accent-light)', color: 'var(--accent)',
            }}>
              <MessageSquare size={16} strokeWidth={2.5} />
            </div>
            <div style={{ flex: 1, minWidth: 0 }}>
              <p style={{ fontWeight: 700, fontSize: '14px', color: 'var(--text)' }}>Ask about this code</p>
              <p style={{ fontSize: '11.5px', color: 'var(--text-muted)' }}>
                Knows your files &amp; this review
              </p>
            </div>
            <button
              className="btn-ghost"
              onClick={() => setOpen(false)}
              aria-label="Close chat"
              style={{ padding: '0.3rem' }}
            >
              <X size={16} />
            </button>
          </div>

          {/* Messages */}
          <div ref={scrollRef} style={{ flex: 1, overflowY: 'auto', padding: '1rem' }}>
            {messages.length === 0 && (
              <div style={{ textAlign: 'center', padding: '0.5rem 0 1rem' }}>
                <Sparkles size={22} color="var(--accent)" style={{ marginBottom: '0.5rem' }} />
                <p style={{ fontSize: '12.5px', color: 'var(--text-muted)' }}>
                  I&apos;ve read every uploaded file and the {issues.length} issue{issues.length === 1 ? '' : 's'} found.
                  Ask me anything — or start with a question below.
                </p>
              </div>
            )}

            {messages.map((m, i) => (
              <div key={i} style={{
                display: 'flex', gap: '0.55rem', marginBottom: '0.9rem',
                flexDirection: m.role === 'user' ? 'row-reverse' : 'row',
              }}>
                <div style={{
                  flexShrink: 0, display: 'grid', placeItems: 'center', width: 26, height: 26, borderRadius: 7,
                  background: m.role === 'user' ? 'var(--accent)' : 'var(--accent-light)',
                  color: m.role === 'user' ? '#fff' : 'var(--accent)',
                }}>
                  {m.role === 'user' ? <User size={14} /> : <Bot size={14} />}
                </div>
                <div style={{
                  maxWidth: '85%',
                  background: m.role === 'user' ? 'var(--accent)' : 'var(--surface2)',
                  color: m.role === 'user' ? '#fff' : 'var(--text)',
                  border: m.role === 'user' ? 'none' : '1px solid var(--border)',
                  borderRadius: 10, padding: '0.55rem 0.8rem', fontSize: '13px',
                }}>
                  {m.role === 'user'
                    ? <span style={{ whiteSpace: 'pre-wrap' }}>{m.content}</span>
                    : renderContent(m.content)}
                </div>
              </div>
            ))}

            {busy && (
              <div style={{ display: 'flex', gap: '0.55rem', marginBottom: '0.9rem', alignItems: 'center' }}>
                <div style={{
                  flexShrink: 0, display: 'grid', placeItems: 'center', width: 26, height: 26, borderRadius: 7,
                  background: 'var(--accent-light)', color: 'var(--accent)',
                }}>
                  <Bot size={14} />
                </div>
                <span className="spinner spinner-dark" />
                <span style={{ fontSize: '12px', color: 'var(--text-muted)' }}>Thinking…</span>
              </div>
            )}

            {error && (
              <p style={{ fontSize: '12px', color: 'var(--high)', marginTop: '0.25rem' }}>{error}</p>
            )}
          </div>

          {/* Suggested questions (before the conversation starts) */}
          {messages.length === 0 && (
            <div style={{ padding: '0 1rem 0.6rem', display: 'flex', flexWrap: 'wrap', gap: '0.4rem', flexShrink: 0 }}>
              {suggestions.map((s) => (
                <button
                  key={s}
                  className="btn-secondary"
                  onClick={() => send(s)}
                  disabled={busy}
                  style={{ fontSize: '11.5px', borderRadius: 999, padding: '0.3rem 0.65rem', textAlign: 'left' }}
                >
                  {s}
                </button>
              ))}
            </div>
          )}

          {/* Composer */}
          <form
            onSubmit={(e) => { e.preventDefault(); send(input) }}
            style={{ display: 'flex', gap: '0.5rem', padding: '0.75rem 1rem', borderTop: '1px solid var(--border)', flexShrink: 0 }}
          >
            <input
              value={input}
              onChange={(e) => setInput(e.target.value)}
              placeholder="Ask a question about your code…"
              disabled={busy}
              style={{ flex: 1 }}
              autoFocus
            />
            <button type="submit" className="btn-primary" disabled={busy || !input.trim()} aria-label="Send">
              <Send size={14} />
            </button>
          </form>
        </div>
      )}

      {/* Discoverability label (only before first open) */}
      {!open && messages.length === 0 && (
        <div style={{
          display: 'flex', alignItems: 'center', gap: '0.5rem',
          background: 'var(--surface)', border: '1px solid var(--border)',
          borderRadius: 999, padding: '0.4rem 0.85rem',
          boxShadow: 'var(--shadow-sm)', fontSize: '12.5px', color: 'var(--text)',
          cursor: 'pointer', animation: 'chatPop 0.2s ease-out',
        }} onClick={() => setOpen(true)}>
          <Sparkles size={14} color="var(--accent)" />
          Ask AI about your code
        </div>
      )}

      {/* Floating toggle button */}
      <button
        onClick={() => setOpen((o) => !o)}
        aria-label={open ? 'Close chat' : 'Open chat assistant'}
        style={{
          width: 56, height: 56, borderRadius: '50%',
          background: 'var(--accent)', color: '#fff',
          display: 'grid', placeItems: 'center',
          boxShadow: '0 6px 20px rgba(79,70,229,0.4)',
          padding: 0,
        }}
      >
        {open ? <X size={24} /> : <MessageSquare size={24} />}
      </button>
    </div>
  )
}
