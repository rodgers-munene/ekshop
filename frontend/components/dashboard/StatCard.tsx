export default function StatCard({ label, value }: { label: string; value: string | number }) {
  return (
    <div className="card p-5">
      <p className="text-xs text-muted mb-1">{label}</p>
      <p className="text-2xl font-bold text-ink">{value}</p>
    </div>
  );
}
