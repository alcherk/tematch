export default function StatCard({ label, value }: { label: string; value: string | number }) {
  return (
    <div className="cyber-card animate-in">
      <p className="cyber-label">{label}</p>
      <p className="cyber-mono" style={{ fontSize: '1.75rem', fontWeight: 400, color: 'var(--cyan)', marginTop: '0.5rem' }}>
        {value}
      </p>
    </div>
  );
}
