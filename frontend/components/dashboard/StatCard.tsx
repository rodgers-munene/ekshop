export default function StatCard({
  label,
  value,
  change,
}: {
  label: string;
  value: string | number;
  /** Optional comparison line, e.g. { current: 120, previous: 100, label: "last month" } → "▲ 20% vs last month". */
  change?: { current: number; previous: number; label: string };
}) {
  return (
    <div className="card p-5">
      <p className="text-xs text-muted mb-1">{label}</p>
      <p className="text-2xl font-bold text-ink">{value}</p>
      {change && <ChangeLine {...change} />}
    </div>
  );
}

function ChangeLine({ current, previous, label }: { current: number; previous: number; label: string }) {
  // No baseline to compare against — a percentage would be infinite/meaningless.
  if (previous === 0) {
    return (
      <p className="text-xs text-muted mt-1">
        {current === 0 ? `No change vs ${label}` : `Up from 0 ${label}`}
      </p>
    );
  }

  const pct = ((current - previous) / previous) * 100;
  const rounded = Math.round(pct * 10) / 10;
  const tone = rounded > 0 ? "text-success" : rounded < 0 ? "text-danger" : "text-muted";
  const arrow = rounded > 0 ? "▲" : rounded < 0 ? "▼" : "";

  return (
    <p className="text-xs mt-1">
      <span className={`font-semibold ${tone}`}>
        {arrow} {Math.abs(rounded)}%
      </span>{" "}
      <span className="text-muted">vs {label}</span>
    </p>
  );
}
