import { BarChart, Bar, XAxis, YAxis, Tooltip, Legend, ResponsiveContainer } from 'recharts';

interface CostEntry {
  date: string;
  provider: string;
  tokens_in: number;
  tokens_out: number;
  cost: number;
}

export default function CostChart({ data }: { data: CostEntry[] }) {
  // Group by date, aggregate per provider
  const byDate = new Map<string, Record<string, string | number>>();
  for (const d of data) {
    const existing = byDate.get(d.date) || { date: d.date };
    existing[`${d.provider}_cost`] = ((existing[`${d.provider}_cost`] as number) || 0) + d.cost;
    existing[`${d.provider}_tokens`] = ((existing[`${d.provider}_tokens`] as number) || 0) + d.tokens_in + d.tokens_out;
    byDate.set(d.date, existing);
  }
  const chartData = Array.from(byDate.values());

  return (
    <ResponsiveContainer width="100%" height={300}>
      <BarChart data={chartData}>
        <XAxis dataKey="date" tick={{ fontSize: 12 }} />
        <YAxis tick={{ fontSize: 12 }} />
        <Tooltip />
        <Legend />
        <Bar dataKey="openai_cost" name="OpenAI ($)" fill="#10b981" stackId="cost" />
        <Bar dataKey="claude_cost" name="Claude ($)" fill="#6366f1" stackId="cost" />
      </BarChart>
    </ResponsiveContainer>
  );
}
