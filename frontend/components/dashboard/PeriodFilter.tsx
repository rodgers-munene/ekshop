"use client";

export type PeriodKey = "today" | "yesterday" | "week" | "month";

const PERIODS: { key: PeriodKey; label: string }[] = [
  { key: "today", label: "Today" },
  { key: "yesterday", label: "Yesterday" },
  { key: "week", label: "Last 7 days" },
  { key: "month", label: "Last 30 days" },
];

export default function PeriodFilter({
  value,
  onChange,
}: {
  value: PeriodKey;
  onChange: (p: PeriodKey) => void;
}) {
  return (
    <div className="flex items-center gap-1 rounded-lg bg-muted/50 p-1">
      {PERIODS.map(({ key, label }) => (
        <button
          key={key}
          onClick={() => onChange(key)}
          className={`px-3 py-1.5 text-xs font-semibold rounded-md transition-colors ${
            value === key
              ? "bg-ink text-white shadow-sm"
              : "text-muted hover:text-ink"
          }`}
        >
          {label}
        </button>
      ))}
    </div>
  );
}