import { useEffect, useState } from 'react';
import { apiFetch } from '../api';
import CostChart from '../components/CostChart';
import StatCard from '../components/StatCard';

export default function Admin() {
  const [stats, setStats] = useState<any>(null);
  const [costs, setCosts] = useState<any[]>([]);
  const [health, setHealth] = useState<any>(null);
  const [users, setUsers] = useState<any[]>([]);
  const [period, setPeriod] = useState('7d');

  useEffect(() => {
    apiFetch<any>('/api/admin/stats').then(setStats);
    apiFetch<any>('/api/admin/health').then(setHealth);
    apiFetch<any[]>('/api/admin/users').then(setUsers);
  }, []);

  useEffect(() => {
    apiFetch<any[]>(`/api/admin/costs?period=${period}`).then(setCosts);
  }, [period]);

  if (!stats) return (
    <p className="cyber-mono" style={{ color: 'var(--text-muted)' }}>Loading...</p>
  );

  return (
    <div className="space-y-8">
      <h2 className="cyber-heading-lg animate-in">Admin Panel</h2>

      {/* Overview Cards */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <StatCard label="Users" value={stats.users} />
        <StatCard label="Channels" value={stats.channels} />
        <StatCard label="Messages today" value={stats.messages_today} />
        <StatCard label="Digests today" value={stats.recommendations_today} />
      </div>

      {/* Cost Chart */}
      <section className="cyber-card animate-in animate-in-2" style={{ padding: '1.75rem' }}>
        <div className="flex justify-between items-center" style={{ marginBottom: '1rem' }}>
          <h3 className="cyber-heading">
            <span style={{ color: 'var(--cyan)', marginRight: '0.5rem', opacity: 0.5 }}>▸</span>
            LLM Costs
          </h3>
          <div className="flex gap-1">
            {['7d', '30d', '90d'].map((p) => (
              <button
                key={p}
                onClick={() => setPeriod(p)}
                className={`cyber-btn ${period === p ? 'cyber-btn-solid' : ''}`}
                style={{ fontSize: '0.65rem', padding: '0.3rem 0.75rem' }}
              >
                {p}
              </button>
            ))}
          </div>
        </div>
        <p className="cyber-mono" style={{ fontSize: '0.8rem', color: 'var(--text-muted)', marginBottom: '1rem' }}>
          Today: <span style={{ color: 'var(--neon-green)' }}>${stats.cost_today.toFixed(4)}</span>
          <span style={{ margin: '0 0.75rem', opacity: 0.3 }}>│</span>
          Tokens: <span style={{ color: 'var(--cyan)' }}>{stats.tokens_today.toLocaleString()}</span>
        </p>
        <CostChart data={costs} />
      </section>

      {/* Token Budget */}
      {health && (
        <section className="cyber-card animate-in animate-in-3" style={{ padding: '1.75rem' }}>
          <h3 className="cyber-heading" style={{ marginBottom: '1rem' }}>
            <span style={{ color: 'var(--cyan)', marginRight: '0.5rem', opacity: 0.5 }}>▸</span>
            Token Budget
          </h3>
          <div className="cyber-progress" style={{ marginBottom: '0.5rem' }}>
            <div
              className="cyber-progress-fill"
              style={{
                width: `${Math.min(health.token_budget.percent, 100)}%`,
                background: health.token_budget.percent > 80
                  ? 'var(--neon-red)'
                  : health.token_budget.percent > 50
                  ? 'var(--neon-amber)'
                  : 'var(--neon-green)',
                boxShadow: `0 0 8px ${
                  health.token_budget.percent > 80 ? 'var(--neon-red)' : health.token_budget.percent > 50 ? 'var(--neon-amber)' : 'var(--neon-green)'
                }`,
              }}
            />
          </div>
          <p className="cyber-mono" style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>
            {health.token_budget.used.toLocaleString()} / {health.token_budget.limit.toLocaleString()}
            <span style={{ marginLeft: '0.5rem', color: health.token_budget.percent > 80 ? 'var(--neon-red)' : 'var(--text-secondary)' }}>
              ({health.token_budget.percent}%)
            </span>
          </p>
        </section>
      )}

      {/* System Health */}
      {health && (
        <section className="cyber-card animate-in animate-in-4" style={{ padding: '1.75rem' }}>
          <h3 className="cyber-heading" style={{ marginBottom: '1rem' }}>
            <span style={{ color: 'var(--cyan)', marginRight: '0.5rem', opacity: 0.5 }}>▸</span>
            System Health
          </h3>
          <p className="cyber-mono" style={{ fontSize: '0.8rem', color: 'var(--text-muted)', marginBottom: '0.75rem' }}>
            Embedding coverage: <span style={{ color: 'var(--cyan)' }}>{health.embedding_coverage}%</span>
          </p>
          <table className="cyber-table">
            <thead>
              <tr>
                <th>Channel</th>
                <th>Status</th>
                <th>Last Fetch</th>
              </tr>
            </thead>
            <tbody>
              {health.channels.map((ch: any) => (
                <tr key={ch.id}>
                  <td style={{ color: 'var(--text-primary)' }}>{ch.title}</td>
                  <td>
                    <span className={`status-dot ${
                      ch.status === 'green' ? 'status-green' : ch.status === 'yellow' ? 'status-yellow' : 'status-red'
                    }`} />
                  </td>
                  <td className="cyber-mono">
                    {ch.last_fetched_hours_ago != null ? `${ch.last_fetched_hours_ago}h ago` : 'Never'}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </section>
      )}

      {/* Users Table */}
      <section className="cyber-card animate-in animate-in-5" style={{ padding: '1.75rem' }}>
        <h3 className="cyber-heading" style={{ marginBottom: '1rem' }}>
          <span style={{ color: 'var(--cyan)', marginRight: '0.5rem', opacity: 0.5 }}>▸</span>
          Users
          <span className="cyber-mono" style={{ color: 'var(--text-muted)', fontSize: '0.8rem', marginLeft: '0.75rem' }}>
            [{users.length}]
          </span>
        </h3>
        <table className="cyber-table">
          <thead>
            <tr>
              <th>Telegram ID</th>
              <th>Interests</th>
              <th>Channels</th>
              <th>Digests today</th>
              <th>Schedule</th>
            </tr>
          </thead>
          <tbody>
            {users.map((u: any) => (
              <tr key={u.telegram_id}>
                <td className="cyber-mono" style={{ color: 'var(--cyan)' }}>{u.telegram_id}</td>
                <td style={{ maxWidth: '200px', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                  {u.interests || '—'}
                </td>
                <td className="cyber-mono">{u.channels}</td>
                <td className="cyber-mono">{u.digests_today}</td>
                <td className="cyber-mono" style={{ fontSize: '0.75rem' }}>{u.digest_cron || 'off'}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>
    </div>
  );
}
