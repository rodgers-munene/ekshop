"use client";

import { useState } from "react";

export type PeriodKey = "today" | "yesterday" | "week" | "month" | "custom";

const PERIODS: { key: PeriodKey; label: string }[] = [
  { key: "today", label: "Today" },
  // Present but previously unreachable: the dashboard's own filter omitted it
  // even though the backend computed a correct full EAT calendar day for it.
  { key: "yesterday", label: "Yesterday" },
  { key: "week", label: "Last 7 days" },
  { key: "month", label: "Last 30 days" },
  { key: "custom", label: "Custom" },
];

/** Inclusive bounds the backend expects, as YYYY-MM-DD. */
export interface CustomRange {
  from: string;
  to: string;
}

function isoDay(offsetDays = 0): string {
  const d = new Date();
  d.setDate(d.getDate() + offsetDays);
  // toISOString is UTC, which can be a day out either side of EAT. Build the
  // string from local parts instead so "today" means today where the user is.
  const m = String(d.getMonth() + 1).padStart(2, "0");
  const day = String(d.getDate()).padStart(2, "0");
  return `${d.getFullYear()}-${m}-${day}`;
}

export default function PeriodFilter({
  value,
  onChange,
  onCustomChange,
  custom,
}: {
  value: PeriodKey;
  onChange: (p: PeriodKey) => void;
  onCustomChange?: (range: CustomRange) => void;
  custom?: CustomRange;
}) {
  const [draft, setDraft] = useState<CustomRange>(
    custom ?? { from: isoDay(-13), to: isoDay() },
  );

  const commit = (next: CustomRange) => {
    setDraft(next);
    onCustomChange?.(next);
  };

  const invalid =
    value === "custom" &&
    (!draft.from || !draft.to || draft.from > draft.to);

  return (
    <div className="flex flex-wrap items-center gap-3">
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

      {value === "custom" && (
        <div className="flex items-center gap-2">
          <input
            type="date"
            value={draft.from}
            max={draft.to || undefined}
            onChange={(e) => commit({ ...draft, from: e.target.value })}
            className="input-field text-xs py-1.5"
            aria-label="From date"
          />
          <span className="text-xs text-muted">to</span>
          <input
            type="date"
            value={draft.to}
            min={draft.from || undefined}
            onChange={(e) => commit({ ...draft, to: e.target.value })}
            className="input-field text-xs py-1.5"
            aria-label="To date"
          />
          {invalid && (
            <span className="text-xs text-danger">
              End date must be on or after the start
            </span>
          )}
        </div>
      )}
    </div>
  );
}

export { isoDay };