import { BarChart, Bar, XAxis, YAxis, Tooltip, Legend, ResponsiveContainer } from 'recharts';

interface CostEntry {
  date: string;
  provider: string;
  tokens_in: number;
  tokens_out: number;
  cost: number;
}

export default function CostChart({ data }: { data: CostEntry[] }) {
  const byDate = new Map<string, Record<string, string | number>>();
  for (const d of data) {
    const existing = byDate.get(d.date) || { date: d.date };
    existing[`${d.provider}_cost`] = ((existing[`${d.provider}_cost`] as number) || 0) + d.cost;
    existing[`${d.provider}_tokens`] = ((existing[`${d.provider}_tokens`] as number) || 0) + d.tokens_in + d.tokens_out;
    byDate.set(d.date, existing);
  }
  const chartData = Array.from(byDate.values());

  return (
    <ResponsiveContainer width="100%" height={280}>
      <BarChart data={chartData}>
        <XAxis
          dataKey="date"
          tick={{ fontSize: 11, fill: '#4a4e62', fontFamily: 'Share Tech Mono' }}
          axisLine={{ stroke: 'rgba(0, 240, 255, 0.08)' }}
          tickLine={false}
        />
        <YAxis
          tick={{ fontSize: 11, fill: '#4a4e62', fontFamily: 'Share Tech Mono' }}
          axisLine={{ stroke: 'rgba(0, 240, 255, 0.08)' }}
          tickLine={false}
        />
        <Tooltip
          contentStyle={{
            background: '#10101f',
            border: '1px solid rgba(0, 240, 255, 0.2)',
            borderRadius: 0,
            fontFamily: 'Share Tech Mono',
            fontSize: '0.8rem',
            color: '#e0e4ec',
          }}
        />
        <Legend
          wrapperStyle={{ fontFamily: 'Chakra Petch', fontSize: '0.75rem', letterSpacing: '0.05em' }}
        />
        <Bar dataKey="openai_cost" name="OpenAI" fill="#00ff88" stackId="cost" radius={[1, 1, 0, 0]} />
        <Bar dataKey="claude_cost" name="Claude" fill="#ff0080" stackId="cost" radius={[1, 1, 0, 0]} />
      </BarChart>
    </ResponsiveContainer>
  );
}
