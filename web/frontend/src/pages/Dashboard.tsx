import { useCallback, useEffect, useState } from 'react';
import { apiFetch, voteFeedback } from '../api';
import ChannelList from '../components/ChannelList';

const SCHEDULE_PRESETS = [
  { label: 'Every morning (9:00)', value: '0 9 * * *' },
  { label: 'Twice daily (9:00 + 18:00)', value: '0 9,18 * * *' },
  { label: 'Weekdays morning', value: '0 9 * * 1-5' },
  { label: 'Off', value: 'off' },
];

export default function Dashboard() {
  const [profile, setProfile] = useState<any>(null);
  const [channels, setChannels] = useState<any[]>([]);
  const [digests, setDigests] = useState<any[]>([]);
  const [interests, setInterests] = useState('');
  const [cron, setCron] = useState('');
  const [saving, setSaving] = useState(false);

  const loadData = useCallback(async () => {
    const [p, ch, d] = await Promise.all([
      apiFetch<any>('/api/users/me'),
      apiFetch<any[]>('/api/users/me/channels'),
      apiFetch<any[]>('/api/users/me/digests'),
    ]);
    setProfile(p);
    setChannels(ch);
    setDigests(d);
    setInterests(p.interests || '');
    setCron(p.digest_cron || 'off');
  }, []);

  useEffect(() => { loadData(); }, [loadData]);

  const save = async () => {
    setSaving(true);
    await apiFetch('/api/users/me', {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ interests, digest_cron: cron }),
    });
    setSaving(false);
    await loadData();
  };

  const handleVote = async (recId: number, feedback: 'like' | 'dislike') => {
    setDigests((prev) =>
      prev.map((d) => (d.id === recId ? { ...d, feedback } : d))
    );
    await voteFeedback(recId, feedback);
  };

  if (!profile) return (
    <p className="cyber-mono" style={{ color: 'var(--text-muted)' }}>Loading...</p>
  );

  return (
    <div className="max-w-3xl space-y-8">
      <h2 className="cyber-heading-lg animate-in">Dashboard</h2>

      {/* Settings */}
      <section className="cyber-card animate-in animate-in-1" style={{ padding: '1.75rem' }}>
        <h3 className="cyber-heading" style={{ marginBottom: '1.25rem' }}>
          <span style={{ color: 'var(--cyan)', marginRight: '0.5rem', opacity: 0.5 }}>▸</span>
          Settings
        </h3>
        <div style={{ marginBottom: '1rem' }}>
          <label className="cyber-label" style={{ display: 'block', marginBottom: '0.5rem' }}>Interests</label>
          <textarea
            value={interests}
            onChange={(e) => setInterests(e.target.value)}
            className="cyber-input"
            style={{ width: '100%', resize: 'vertical', minHeight: '3.5rem' }}
            rows={2}
          />
        </div>
        <div style={{ marginBottom: '1.25rem' }}>
          <label className="cyber-label" style={{ display: 'block', marginBottom: '0.5rem' }}>Digest Schedule</label>
          <div className="flex items-center gap-2 flex-wrap">
            <select
              value={SCHEDULE_PRESETS.find((p) => p.value === cron) ? cron : '__custom__'}
              onChange={(e) => setCron(e.target.value === '__custom__' ? cron : e.target.value)}
              className="cyber-select"
            >
              {SCHEDULE_PRESETS.map((p) => (
                <option key={p.value} value={p.value}>{p.label}</option>
              ))}
              <option value="__custom__">Custom</option>
            </select>
            {!SCHEDULE_PRESETS.find((p) => p.value === cron) && (
              <input
                value={cron}
                onChange={(e) => setCron(e.target.value)}
                className="cyber-input"
                placeholder="0 9 * * *"
                style={{ width: '140px' }}
              />
            )}
          </div>
        </div>
        <button onClick={save} disabled={saving} className="cyber-btn cyber-btn-solid">
          {saving ? 'Saving...' : 'Save'}
        </button>
      </section>

      {/* Channels */}
      <section className="cyber-card animate-in animate-in-2" style={{ padding: '1.75rem' }}>
        <h3 className="cyber-heading" style={{ marginBottom: '1rem' }}>
          <span style={{ color: 'var(--cyan)', marginRight: '0.5rem', opacity: 0.5 }}>▸</span>
          My Channels
          <span className="cyber-mono" style={{ color: 'var(--text-muted)', fontSize: '0.8rem', marginLeft: '0.75rem' }}>
            [{channels.length}]
          </span>
        </h3>
        {channels.length ? (
          <ChannelList channels={channels} onRefresh={loadData} />
        ) : (
          <p style={{ color: 'var(--text-muted)', fontFamily: 'var(--font-mono)', fontSize: '0.85rem' }}>
            No channels yet. Forward a message to the bot to subscribe.
          </p>
        )}
      </section>

      {/* Digest History */}
      <section className="cyber-card animate-in animate-in-3" style={{ padding: '1.75rem' }}>
        <h3 className="cyber-heading" style={{ marginBottom: '1rem' }}>
          <span style={{ color: 'var(--cyan)', marginRight: '0.5rem', opacity: 0.5 }}>▸</span>
          Recent Digests
        </h3>
        {digests.length ? (
          <div className="space-y-3">
            {digests.map((d) => (
              <div key={d.id} style={{ borderBottom: '1px solid var(--border-dim)', paddingBottom: '0.75rem' }}>
                <div className="flex justify-between items-center" style={{ fontSize: '0.8rem' }}>
                  <span className="cyber-mono" style={{ color: 'var(--cyan)' }}>
                    Score: {d.score.toFixed(2)}
                  </span>
                  <span className="cyber-mono" style={{ color: 'var(--text-muted)' }}>
                    {new Date(d.created_at).toLocaleString()}
                  </span>
                  <span className="flex gap-1" style={{ fontSize: '1rem' }}>
                    <button
                      onClick={() => handleVote(d.id, 'like')}
                      style={{
                        background: 'none', border: 'none', cursor: 'pointer', padding: '0 0.15rem',
                        opacity: d.feedback === 'like' ? 1 : d.feedback ? 0.25 : 0.4,
                        filter: d.feedback === 'like' ? 'drop-shadow(0 0 4px var(--neon-green))' : 'none',
                        transition: 'opacity 0.15s, filter 0.15s',
                      }}
                    >
                      👍
                    </button>
                    <button
                      onClick={() => handleVote(d.id, 'dislike')}
                      style={{
                        background: 'none', border: 'none', cursor: 'pointer', padding: '0 0.15rem',
                        opacity: d.feedback === 'dislike' ? 1 : d.feedback ? 0.25 : 0.4,
                        filter: d.feedback === 'dislike' ? 'drop-shadow(0 0 4px var(--neon-red))' : 'none',
                        transition: 'opacity 0.15s, filter 0.15s',
                      }}
                    >
                      👎
                    </button>
                  </span>
                </div>
                <p style={{ fontSize: '0.85rem', color: 'var(--text-secondary)', marginTop: '0.4rem' }}>
                  {d.text_preview}
                </p>
              </div>
            ))}
          </div>
        ) : (
          <p style={{ color: 'var(--text-muted)', fontFamily: 'var(--font-mono)', fontSize: '0.85rem' }}>
            No digests yet. Send /digest in the bot.
          </p>
        )}
      </section>
    </div>
  );
}
