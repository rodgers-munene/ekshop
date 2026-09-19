import Link from "next/link";
import { ArrowUpRight } from "lucide-react";

export default function StatCard({
  label,
  value,
  change,
  hint,
  onClick,
  href,
}: {
  label: string;
  value: string | number;
  /** Optional comparison line: { current, previous, label } → "▲ 20% vs label". */
  change?: { current: number; previous: number; label: string };
  /** Short "what you'll see if you click" helper, shown on hover. */
  hint?: string;
  /** Opens an inline drill-down panel with the rows behind this number. */
  onClick?: (() => void) | null;
  /** Navigates to a full list page instead of the inline panel. */
  href?: string;
}) {
  const interactive = Boolean(onClick || href);
  const cls =
    "card p-5 relative group h-full text-left" +
    (interactive ? " cursor-pointer hover:ring-1 hover:ring-amber hover:shadow-sm" : "");

  const inner = (
    <>
      <p className="text-xs text-muted mb-1 pr-5 truncate">{label}</p>
      <p className="text-2xl font-bold text-ink truncate">{value}</p>
      <div className="min-h-[18px]">{change && <ChangeLine {...change} />}</div>
      {interactive && (
        <span className="absolute right-3 top-3 text-muted opacity-0 transition-opacity group-hover:opacity-100">
          <ArrowUpRight size={14} />
        </span>
      )}
      {hint && (
        <p className="absolute inset-x-0 -bottom-1 px-5 text-xs text-muted truncate opacity-0 transition-opacity group-hover:opacity-100 pointer-events-none">
          {hint}
        </p>
      )}
    </>
  );

  if (href) {
    return (
      <Link href={href} className={cls}>
        {inner}
      </Link>
    );
  }
  if (onClick) {
    return (
      <button type="button" onClick={onClick} className={cls} aria-haspopup="dialog">
        {inner}
      </button>
    );
  }
  return <div className="card p-5 relative group h-full">{inner}</div>;
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