import { useState, useEffect } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { ArrowLeft, MousePointerClick, Globe, Smartphone, Monitor } from 'lucide-react'
import {
  AreaChart, Area, XAxis, YAxis, Tooltip, ResponsiveContainer,
  PieChart, Pie, Cell, Legend
} from 'recharts'
import api from '../api/auth'

const COLORS = ['#7c6aff', '#a78bfa', '#c4b5fd', '#34d399', '#fbbf24', '#f87171']

function BarList({ data, total }) {
  return (
    <div className="bar-list">
      {data.map((item, i) => (
        <div key={i} className="bar-item">
          <div className="bar-meta">
            <span className="name">{item.name || 'Unknown'}</span>
            <span className="count">{item.value}</span>
          </div>
          <div className="bar-track">
            <div className="bar-fill" style={{ width: `${total ? (item.value / total) * 100 : 0}%` }} />
          </div>
        </div>
      ))}
    </div>
  )
}

const CustomTooltip = ({ active, payload, label }) => {
  if (active && payload && payload.length) {
    return (
      <div style={{
        background: 'var(--surface2)',
        border: '1px solid var(--border)',
        borderRadius: 8,
        padding: '8px 14px',
        fontSize: '0.82rem',
        color: 'var(--text)'
      }}>
        <div style={{ color: 'var(--text-muted)', marginBottom: 4 }}>{label}</div>
        <div style={{ color: 'var(--accent2)', fontWeight: 600 }}>{payload[0].value} clicks</div>
      </div>
    )
  }
  return null
}

export default function Analytics() {
  const { code } = useParams()
  const navigate = useNavigate()
  const [stats, setStats] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  useEffect(() => {
    async function load() {
      try {
        const { data } = await api.get(`/stats/${code}`)
        setStats(data)
      } catch (err) {
        setError(err.response?.data?.detail || 'Failed to load analytics.')
      } finally {
        setLoading(false)
      }
    }
    load()
  }, [code])

  if (loading) return <div className="layout"><main className="main"><div className="loading">Loading analytics…</div></main></div>

  if (error) return (
    <div className="layout">
      <main className="main">
        <button className="back-btn" onClick={() => navigate('/')}><ArrowLeft size={15}/> Back</button>
        <div className="error-msg">{error}</div>
      </main>
    </div>
  )

  const deviceData = stats.device_stats.map(d => ({ name: d.device, value: d.count }))
  const browserData = stats.browser_stats.map(b => ({ name: b.browser, value: b.count }))
  const countryData = stats.country_stats.map(c => ({ name: c.country, value: c.count }))
  const timeData = stats.clicks_per_day.map(d => ({ date: d.date, clicks: d.count }))

  return (
    <div className="layout">
      <aside className="sidebar">
        <div className="sidebar-logo">🔍 <span>LinkLens</span></div>
      </aside>

      <main className="main">
        <button className="back-btn" onClick={() => navigate('/')}>
          <ArrowLeft size={15}/> Back to links
        </button>

        <div className="page-header">
          <h1>/{code}</h1>
          <p>Analytics overview for this short link</p>
        </div>

        {/* Summary cards */}
        <div className="stat-grid">
          <div className="stat-card">
            <div className="label">Total Clicks</div>
            <div className="value" style={{ color: 'var(--accent2)' }}>{stats.total_clicks}</div>
            <div className="sub">All time</div>
          </div>
          <div className="stat-card">
            <div className="label">Top Device</div>
            <div className="value" style={{ fontSize: '1.4rem', display: 'flex', alignItems: 'center', gap: 8 }}>
              {deviceData[0]?.name === 'mobile' ? <Smartphone size={24}/> : <Monitor size={24}/>}
              {deviceData[0]?.name || '—'}
            </div>
            <div className="sub">{deviceData[0]?.value ?? 0} clicks</div>
          </div>
          <div className="stat-card">
            <div className="label">Top Country</div>
            <div className="value" style={{ fontSize: '1.5rem' }}>
              <Globe size={24} style={{ marginBottom: -4 }}/> {countryData[0]?.name || '—'}
            </div>
            <div className="sub">{countryData[0]?.value ?? 0} clicks</div>
          </div>
          <div className="stat-card">
            <div className="label">Top Browser</div>
            <div className="value" style={{ fontSize: '1.2rem' }}>
              {browserData[0]?.name || '—'}
            </div>
            <div className="sub">{browserData[0]?.value ?? 0} clicks</div>
          </div>
        </div>

        {/* Charts grid */}
        <div className="analytics-grid">

          {/* Clicks over time — full width */}
          <div className="chart-card full">
            <h3>Clicks over time</h3>
            {timeData.length === 0 ? (
              <div className="empty" style={{ padding: '2rem 0' }}>No click data yet</div>
            ) : (
              <ResponsiveContainer width="100%" height={220}>
                <AreaChart data={timeData} margin={{ top: 5, right: 10, left: -20, bottom: 0 }}>
                  <defs>
                    <linearGradient id="grad" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="5%" stopColor="#7c6aff" stopOpacity={0.3}/>
                      <stop offset="95%" stopColor="#7c6aff" stopOpacity={0}/>
                    </linearGradient>
                  </defs>
                  <XAxis dataKey="date" tick={{ fill: '#64748b', fontSize: 11 }} axisLine={false} tickLine={false} />
                  <YAxis tick={{ fill: '#64748b', fontSize: 11 }} axisLine={false} tickLine={false} />
                  <Tooltip content={<CustomTooltip />} />
                  <Area type="monotone" dataKey="clicks" stroke="#7c6aff" strokeWidth={2.5} fill="url(#grad)" dot={false} />
                </AreaChart>
              </ResponsiveContainer>
            )}
          </div>

          {/* Device breakdown */}
          <div className="chart-card">
            <h3><MousePointerClick size={13} style={{marginRight:6}}/>Device</h3>
            {deviceData.length === 0
              ? <div className="empty" style={{ padding: '1rem 0' }}>No data</div>
              : (
                <PieChart width={220} height={180}>
                  <Pie data={deviceData} dataKey="value" nameKey="name" cx="50%" cy="50%" outerRadius={70} paddingAngle={3}>
                    {deviceData.map((_, i) => <Cell key={i} fill={COLORS[i % COLORS.length]} />)}
                  </Pie>
                  <Legend iconType="circle" iconSize={9} wrapperStyle={{ fontSize: '0.8rem', color: 'var(--text-muted)' }} />
                  <Tooltip contentStyle={{ background: 'var(--surface2)', border: '1px solid var(--border)', borderRadius: 8 }} />
                </PieChart>
              )
            }
          </div>

          {/* Browser */}
          <div className="chart-card">
            <h3>Browser</h3>
            <BarList data={browserData} total={stats.total_clicks} />
          </div>

          {/* Country */}
          <div className="chart-card full">
            <h3><Globe size={13} style={{marginRight:6}}/>Top Countries</h3>
            <BarList data={countryData.slice(0, 8)} total={stats.total_clicks} />
          </div>

        </div>
      </main>
    </div>
  )
}
