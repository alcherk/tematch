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
    <table className="w-full text-sm">
      <thead>
        <tr className="text-left text-gray-500 border-b">
          <th className="py-2">Channel</th>
          <th>Messages</th>
          <th>Added</th>
          <th></th>
        </tr>
      </thead>
      <tbody>
        {channels.map((ch) => (
          <tr key={ch.id} className="border-b hover:bg-gray-50">
            <td className="py-2 font-medium">{ch.title}{ch.username && ` (@${ch.username})`}</td>
            <td>{ch.message_count}</td>
            <td>{ch.added_at ? new Date(ch.added_at).toLocaleDateString() : '—'}</td>
            <td>
              <button onClick={() => unsubscribe(ch.id)} className="text-red-500 hover:underline text-xs">
                Remove
              </button>
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}
