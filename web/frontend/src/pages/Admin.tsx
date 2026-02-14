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

  if (!stats) return <p>Loading...</p>;

  return (
    <div className="space-y-8">
      <h2 className="text-2xl font-bold">Admin Panel</h2>

      {/* Overview Cards */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <StatCard label="Users" value={stats.users} />
        <StatCard label="Channels" value={stats.channels} />
        <StatCard label="Messages today" value={stats.messages_today} />
        <StatCard label="Digests today" value={stats.recommendations_today} />
      </div>

      {/* Cost Chart */}
      <section className="bg-white rounded-lg shadow p-6">
        <div className="flex justify-between items-center mb-4">
          <h3 className="font-semibold text-lg">LLM Costs</h3>
          <div className="space-x-2">
            {['7d', '30d', '90d'].map((p) => (
              <button
                key={p}
                onClick={() => setPeriod(p)}
                className={`px-3 py-1 rounded text-sm ${period === p ? 'bg-blue-600 text-white' : 'bg-gray-100'}`}
              >
                {p}
              </button>
            ))}
          </div>
        </div>
        <p className="text-sm text-gray-500 mb-4">
          Today: ${stats.cost_today.toFixed(4)} | Tokens: {stats.tokens_today.toLocaleString()}
        </p>
        <CostChart data={costs} />
      </section>

      {/* Token Budget */}
      {health && (
        <section className="bg-white rounded-lg shadow p-6">
          <h3 className="font-semibold text-lg mb-4">Token Budget</h3>
          <div className="w-full bg-gray-200 rounded-full h-4">
            <div
              className={`h-4 rounded-full ${health.token_budget.percent > 80 ? 'bg-red-500' : 'bg-green-500'}`}
              style={{ width: `${Math.min(health.token_budget.percent, 100)}%` }}
            />
          </div>
          <p className="text-sm text-gray-500 mt-2">
            {health.token_budget.used.toLocaleString()} / {health.token_budget.limit.toLocaleString()} ({health.token_budget.percent}%)
          </p>
        </section>
      )}

      {/* System Health */}
      {health && (
        <section className="bg-white rounded-lg shadow p-6">
          <h3 className="font-semibold text-lg mb-4">System Health</h3>
          <p className="text-sm text-gray-500 mb-3">Embedding coverage: {health.embedding_coverage}%</p>
          <table className="w-full text-sm">
            <thead>
              <tr className="text-left text-gray-500 border-b">
                <th className="py-2">Channel</th>
                <th>Status</th>
                <th>Last Fetch</th>
              </tr>
            </thead>
            <tbody>
              {health.channels.map((ch: any) => (
                <tr key={ch.id} className="border-b">
                  <td className="py-2">{ch.title}</td>
                  <td>
                    <span className={`inline-block w-3 h-3 rounded-full ${
                      ch.status === 'green' ? 'bg-green-500' : ch.status === 'yellow' ? 'bg-yellow-400' : 'bg-red-500'
                    }`} />
                  </td>
                  <td>{ch.last_fetched_hours_ago != null ? `${ch.last_fetched_hours_ago}h ago` : 'Never'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </section>
      )}

      {/* Users Table */}
      <section className="bg-white rounded-lg shadow p-6">
        <h3 className="font-semibold text-lg mb-4">Users ({users.length})</h3>
        <table className="w-full text-sm">
          <thead>
            <tr className="text-left text-gray-500 border-b">
              <th className="py-2">Telegram ID</th>
              <th>Interests</th>
              <th>Channels</th>
              <th>Digests today</th>
              <th>Schedule</th>
            </tr>
          </thead>
          <tbody>
            {users.map((u: any) => (
              <tr key={u.telegram_id} className="border-b">
                <td className="py-2 font-mono">{u.telegram_id}</td>
                <td className="max-w-xs truncate">{u.interests || '—'}</td>
                <td>{u.channels}</td>
                <td>{u.digests_today}</td>
                <td className="font-mono text-xs">{u.digest_cron || 'off'}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>
    </div>
  );
}
