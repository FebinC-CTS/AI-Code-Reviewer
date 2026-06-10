import { useState } from 'react'
import { FileSpreadsheet, FileText, Plus } from 'lucide-react'
import { getExportUrl, deleteSession } from '../services/api'

export default function ExportButtons({ sessionId, onReset }) {
  const [downloading, setDownloading] = useState(null)

  const handleExport = async (format) => {
    setDownloading(format)
    try {
      const a = document.createElement('a')
      a.href = getExportUrl(sessionId, format)
      a.download = `code-review.${format === 'excel' ? 'xlsx' : 'md'}`
      document.body.appendChild(a)
      a.click()
      document.body.removeChild(a)
    } catch (err) {
      alert(`Export failed: ${err.message}`)
    } finally {
      setDownloading(null)
    }
  }

  const handleNew = async () => {
    try { await deleteSession(sessionId) } catch (_) {}
    onReset?.()
  }

  return (
    <div style={{
      display: 'flex', gap: '0.6rem', flexWrap: 'wrap', alignItems: 'center',
      marginBottom: '0.75rem',
    }}>
      <span style={{ fontSize: '12px', color: 'var(--text-muted)', fontWeight: 500 }}>Export:</span>

      <button className="btn-secondary" onClick={() => handleExport('excel')} disabled={!!downloading}>
        {downloading === 'excel' ? <span className="spinner spinner-dark" /> : <FileSpreadsheet size={14} />}
        Excel (.xlsx)
      </button>

      <button className="btn-secondary" onClick={() => handleExport('markdown')} disabled={!!downloading}>
        {downloading === 'markdown' ? <span className="spinner spinner-dark" /> : <FileText size={14} />}
        Markdown (.md)
      </button>

      <div style={{ flex: 1 }} />

      <button className="btn-primary" onClick={handleNew}>
        <Plus size={14} /> New Analysis
      </button>
    </div>
  )
}
