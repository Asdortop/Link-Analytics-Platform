import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { Link2, BarChart2, LogOut, Copy, ExternalLink, Plus, ChevronRight } from 'lucide-react'
import api, { logout } from '../api/auth'

export default function Dashboard() {
  const navigate = useNavigate()
  const [urls, setUrls] = useState([])
  const [loading, setLoading] = useState(true)

  // Shorten form state
  const [originalUrl, setOriginalUrl] = useState('')
  const [customCode, setCustomCode] = useState('')
  const [shortening, setShortening] = useState(false)
  const [newLink, setNewLink] = useState(null)
  const [formError, setFormError] = useState('')
  const [copied, setCopied] = useState(false)

  // We call /stats per link to get click counts — cache them
  const [stats, setStats] = useState({}) // { [code]: totalClicks }

  useEffect(() => { fetchUrls() }, [])

  async function fetchUrls() {
    // There's no GET /links endpoint yet — we'll track links in localStorage
    // to simulate a "my links" list until the API endpoint is added
    const saved = JSON.parse(localStorage.getItem('my_links') || '[]')
    setUrls(saved)
    setLoading(false)

    // Fetch click counts for each saved link
    for (const link of saved) {
      try {
        const { data } = await api.get(`/stats/${link.short_code}`)
        setStats(prev => ({ ...prev, [link.short_code]: data.total_clicks }))
      } catch {}
    }
  }

  async function handleShorten(e) {
    e.preventDefault()
    setFormError('')
    setNewLink(null)
    setShortening(true)
    try {
      const body = { original_url: originalUrl }
      if (customCode.trim()) body.custom_code = customCode.trim()
      const { data } = await api.post('/shorten/', body)

      // Save to localStorage
      const saved = JSON.parse(localStorage.getItem('my_links') || '[]')
      const entry = {
        short_code: data.short_url.split('/').pop(),
        original_url: data.original_url,
        short_url: data.short_url,
        created_at: new Date().toISOString(),
      }
      const updated = [entry, ...saved]
      localStorage.setItem('my_links', JSON.stringify(updated))
      setUrls(updated)
      setNewLink(data)
      setOriginalUrl('')
      setCustomCode('')
    } catch (err) {
      setFormError(err.response?.data?.detail || 'Failed to shorten URL.')
    } finally {
      setShortening(false)
    }
  }

  function copyLink(url) {
    navigator.clipboard.writeText(url)
    setCopied(url)
    setTimeout(() => setCopied(false), 2000)
  }

  function formatDate(iso) {
    return new Date(iso).toLocaleDateString('en-IN', { day: 'numeric', month: 'short', year: 'numeric' })
  }

  return (
    <div className="layout">
      {/* Sidebar */}
      <aside className="sidebar">
        <div className="sidebar-logo">🔍 <span>LinkLens</span></div>
        <nav className="sidebar-nav">
          <button className="nav-item active">
            <Link2 size={16} /> My Links
          </button>
          <button className="nav-item" onClick={() => navigate('/analytics/' + (urls[0]?.short_code || ''))}>
            <BarChart2 size={16} /> Analytics
          </button>
        </nav>
        <div className="sidebar-bottom">
          <button className="nav-item" onClick={logout}>
            <LogOut size={16} /> Sign out
          </button>
        </div>
      </aside>

      {/* Main */}
      <main className="main">
        <div className="page-header">
          <h1>My Links</h1>
          <p>Create and manage your shortened URLs</p>
        </div>

        {/* Shorten form */}
        <form className="shorten-form" onSubmit={handleShorten}>
          <div className="shorten-row">
            <div className="field">
              <label>Destination URL</label>
              <input
                type="url"
                placeholder="https://example.com/very/long/path"
                value={originalUrl}
                onChange={e => setOriginalUrl(e.target.value)}
                required
              />
            </div>
            <div className="field" style={{ maxWidth: 200 }}>
              <label>Custom code <span style={{color:'var(--text-muted)',fontSize:'0.75rem'}}>(optional)</span></label>
              <input
                type="text"
                placeholder="my-link"
                value={customCode}
                onChange={e => setCustomCode(e.target.value)}
                maxLength={30}
              />
            </div>
            <button className="btn-accent" type="submit" disabled={shortening}>
              <Plus size={16} /> {shortening ? 'Shortening…' : 'Shorten'}
            </button>
          </div>

          {formError && <div className="error-msg" style={{ margin: 0 }}>{formError}</div>}

          {newLink && (
            <div className="success-banner">
              <div>
                ✅ Created: <span className="short-url">{newLink.short_url}</span>
              </div>
              <div style={{ display: 'flex', gap: 8 }}>
                <button onClick={() => copyLink(newLink.short_url)} type="button">
                  {copied === newLink.short_url ? '✓ Copied!' : 'Copy'}
                </button>
                <button onClick={() => window.open(newLink.short_url, '_blank')} type="button">Open ↗</button>
              </div>
            </div>
          )}
        </form>

        {/* Links table */}
        <div className="card">
          <div className="card-header">
            <h2>All links ({urls.length})</h2>
          </div>
          {loading ? (
            <div className="loading">Loading…</div>
          ) : urls.length === 0 ? (
            <div className="empty">
              <div>No links yet</div>
              <p>Shorten your first URL above to get started</p>
            </div>
          ) : (
            <table>
              <thead>
                <tr>
                  <th>Short code</th>
                  <th>Destination</th>
                  <th>Clicks</th>
                  <th>Created</th>
                  <th></th>
                </tr>
              </thead>
              <tbody>
                {urls.map(link => (
                  <tr key={link.short_code}>
                    <td><span className="code-badge">/{link.short_code}</span></td>
                    <td>
                      <div className="url-truncate" title={link.original_url}>
                        {link.original_url}
                      </div>
                    </td>
                    <td style={{ fontVariantNumeric: 'tabular-nums', fontWeight: 600 }}>
                      {stats[link.short_code] ?? '—'}
                    </td>
                    <td style={{ color: 'var(--text-muted)', fontSize: '0.82rem' }}>
                      {formatDate(link.created_at)}
                    </td>
                    <td>
                      <div style={{ display: 'flex', gap: 6 }}>
                        <button className="btn-icon" onClick={() => copyLink(link.short_url)} title="Copy">
                          {copied === link.short_url ? '✓' : <Copy size={14} />}
                        </button>
                        <button className="btn-icon" onClick={() => window.open(link.short_url, '_blank')} title="Open">
                          <ExternalLink size={14} />
                        </button>
                        <button className="btn-sm" onClick={() => navigate(`/analytics/${link.short_code}`)}>
                          Stats <ChevronRight size={13} />
                        </button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      </main>
    </div>
  )
}
