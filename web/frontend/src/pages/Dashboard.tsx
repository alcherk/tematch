import { useCallback, useEffect, useState } from 'react';
import { apiFetch } from '../api';
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

  if (!profile) return <p>Loading...</p>;

  return (
    <div className="max-w-3xl space-y-8">
      <h2 className="text-2xl font-bold">My Dashboard</h2>

      {/* Settings */}
      <section className="bg-white rounded-lg shadow p-6 space-y-4">
        <h3 className="font-semibold text-lg">Settings</h3>
        <div>
          <label className="block text-sm text-gray-600 mb-1">Interests</label>
          <textarea
            value={interests}
            onChange={(e) => setInterests(e.target.value)}
            className="w-full border rounded p-2 text-sm"
            rows={2}
          />
        </div>
        <div>
          <label className="block text-sm text-gray-600 mb-1">Digest Schedule</label>
          <select
            value={SCHEDULE_PRESETS.find((p) => p.value === cron) ? cron : '__custom__'}
            onChange={(e) => setCron(e.target.value === '__custom__' ? cron : e.target.value)}
            className="border rounded p-2 text-sm"
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
              className="ml-2 border rounded p-2 text-sm"
              placeholder="0 9 * * *"
            />
          )}
        </div>
        <button
          onClick={save}
          disabled={saving}
          className="bg-blue-600 text-white px-4 py-2 rounded text-sm hover:bg-blue-700 disabled:opacity-50"
        >
          {saving ? 'Saving...' : 'Save'}
        </button>
      </section>

      {/* Channels */}
      <section className="bg-white rounded-lg shadow p-6">
        <h3 className="font-semibold text-lg mb-4">My Channels ({channels.length})</h3>
        {channels.length ? <ChannelList channels={channels} onRefresh={loadData} /> : <p className="text-gray-500">No channels yet. Forward a message to the bot to subscribe.</p>}
      </section>

      {/* Digest History */}
      <section className="bg-white rounded-lg shadow p-6">
        <h3 className="font-semibold text-lg mb-4">Recent Digests</h3>
        {digests.length ? (
          <div className="space-y-3">
            {digests.map((d) => (
              <div key={d.id} className="border-b pb-3">
                <div className="flex justify-between text-sm">
                  <span className="font-medium">Score: {d.score.toFixed(2)}</span>
                  <span className="text-gray-500">{new Date(d.created_at).toLocaleString()}</span>
                  {d.feedback && <span className={d.feedback === 'like' ? 'text-green-600' : 'text-red-500'}>{d.feedback}</span>}
                </div>
                <p className="text-sm text-gray-700 mt-1">{d.text_preview}</p>
              </div>
            ))}
          </div>
        ) : <p className="text-gray-500">No digests yet. Send /digest in the bot.</p>}
      </section>
    </div>
  );
}
