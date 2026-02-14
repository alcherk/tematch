import { Link } from 'react-router-dom';
import { apiFetch } from '../api';

interface Channel {
  id: number;
  title: string;
  username: string | null;
  message_count: number;
  added_at: string | null;
}

export default function ChannelList({ channels, onRefresh }: { channels: Channel[]; onRefresh: () => void }) {
  const unsubscribe = async (id: number) => {
    if (!confirm('Unsubscribe from this channel?')) return;
    await apiFetch(`/api/users/me/channels/${id}`, { method: 'DELETE' });
    onRefresh();
  };

  return (
    <table className="cyber-table">
      <thead>
        <tr>
          <th>Channel</th>
          <th>Messages</th>
          <th>Added</th>
          <th></th>
        </tr>
      </thead>
      <tbody>
        {channels.map((ch) => (
          <tr key={ch.id}>
            <td style={{ color: 'var(--text-primary)' }}>
              <Link
                to={`/channels/${ch.id}`}
                style={{
                  color: 'var(--text-primary)',
                  textDecoration: 'none',
                  borderBottom: '1px solid var(--border-dim)',
                  transition: 'border-color 0.2s'
                }}
                onMouseEnter={(e) => (e.currentTarget.style.borderBottomColor = 'var(--cyan)')}
                onMouseLeave={(e) => (e.currentTarget.style.borderBottomColor = 'var(--border-dim)')}
              >
                {ch.title}
              </Link>
              {ch.username && <span className="cyber-mono" style={{ color: 'var(--text-muted)', marginLeft: '0.5rem', fontSize: '0.8rem' }}>@{ch.username}</span>}
            </td>
            <td className="cyber-mono">{ch.message_count}</td>
            <td>{ch.added_at ? new Date(ch.added_at).toLocaleDateString() : '—'}</td>
            <td>
              <button onClick={() => unsubscribe(ch.id)} className="cyber-btn cyber-btn-danger" style={{ fontSize: '0.65rem', padding: '0.25rem 0.75rem' }}>
                Remove
              </button>
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}
