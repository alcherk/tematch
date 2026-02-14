import { useCallback, useEffect, useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import { apiFetch } from '../api';

interface MsgRow {
  id: number;
  text: string;
  date: string | null;
  has_embedding: boolean;
  relevance: number | null;
  has_media: boolean;
}

interface ChannelMessagesResponse {
  channel: { id: number; title: string; username: string | null };
  messages: MsgRow[];
  total: number;
  page: number;
  per_page: number;
}

export default function ChannelMessages() {
  const { id } = useParams<{ id: string }>();
  const [data, setData] = useState<ChannelMessagesResponse | null>(null);
  const [page, setPage] = useState(1);
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    setLoading(true);
    const resp = await apiFetch<ChannelMessagesResponse>(
      `/api/users/me/channels/${id}/messages?page=${page}&per_page=50`
    );
    setData(resp);
    setLoading(false);
  }, [id, page]);

  useEffect(() => { load(); }, [load]);

  if (loading && !data) return (
    <p className="cyber-mono" style={{ color: 'var(--text-muted)' }}>Loading...</p>
  );

  if (!data) return null;

  const totalPages = Math.ceil(data.total / data.per_page);

  return (
    <div className="max-w-5xl space-y-6">
      <div className="flex items-center gap-4 animate-in">
        <Link to="/dashboard" className="cyber-btn" style={{ fontSize: '0.7rem', padding: '0.3rem 0.75rem' }}>
          &larr; Back
        </Link>
        <h2 className="cyber-heading-lg" style={{ fontSize: '1.2rem' }}>
          {data.channel.title}
          {data.channel.username && (
            <span className="cyber-mono" style={{ color: 'var(--text-muted)', fontSize: '0.8rem', marginLeft: '0.75rem' }}>
              @{data.channel.username}
            </span>
          )}
        </h2>
        <span className="cyber-mono" style={{ color: 'var(--text-muted)', fontSize: '0.75rem', marginLeft: 'auto' }}>
          {data.total} messages
        </span>
      </div>

      <section className="cyber-card animate-in animate-in-1" style={{ padding: '1.5rem' }}>
        <table className="cyber-table">
          <thead>
            <tr>
              <th style={{ width: '50%' }}>Message</th>
              <th>Date</th>
              <th style={{ textAlign: 'center' }}>Emb</th>
              <th style={{ textAlign: 'center' }}>Relevance</th>
              <th style={{ textAlign: 'center' }}>Media</th>
            </tr>
          </thead>
          <tbody>
            {data.messages.map((m) => (
              <tr key={m.id}>
                <td style={{ color: 'var(--text-primary)', fontSize: '0.8rem', lineHeight: 1.4, maxWidth: 0, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                  {m.text}
                </td>
                <td className="cyber-mono" style={{ fontSize: '0.75rem', whiteSpace: 'nowrap' }}>
                  {m.date ? new Date(m.date).toLocaleString() : '\u2014'}
                </td>
                <td style={{ textAlign: 'center' }}>
                  <span className={`status-dot ${m.has_embedding ? 'status-green' : 'status-red'}`} />
                </td>
                <td className="cyber-mono" style={{ textAlign: 'center', color: m.relevance != null && m.relevance > 0.3 ? 'var(--neon-green)' : 'var(--text-muted)' }}>
                  {m.relevance != null ? `${Math.round(m.relevance * 100)}%` : '\u2014'}
                </td>
                <td style={{ textAlign: 'center', opacity: m.has_media ? 1 : 0.2 }}>
                  {'\uD83D\uDCCE'}
                </td>
              </tr>
            ))}
          </tbody>
        </table>

        {totalPages > 1 && (
          <div className="flex items-center justify-center gap-4" style={{ marginTop: '1.25rem' }}>
            <button
              className="cyber-btn"
              style={{ fontSize: '0.7rem', padding: '0.3rem 0.75rem' }}
              disabled={page <= 1}
              onClick={() => setPage((p) => p - 1)}
            >
              &larr; Prev
            </button>
            <span className="cyber-mono" style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>
              {page} / {totalPages}
            </span>
            <button
              className="cyber-btn"
              style={{ fontSize: '0.7rem', padding: '0.3rem 0.75rem' }}
              disabled={page >= totalPages}
              onClick={() => setPage((p) => p + 1)}
            >
              Next &rarr;
            </button>
          </div>
        )}
      </section>
    </div>
  );
}
