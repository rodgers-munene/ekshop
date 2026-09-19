"use client";

import { useEffect, useState, type ReactNode, type Key } from "react";
import Link from "next/link";
import { X, ArrowUpRight, Inbox } from "lucide-react";

export interface DrillColumn {
  key: string;
  label: string;
  align?: "right";
  render: (row: any) => ReactNode;
}

/**
 * Right-hand slide-over that shows the rows behind a stat card. Works in two
 * modes: "fetch" (queryUrl) or "rows" (pre-loaded data, e.g. the analytics
 * matrix tables the cards describe). Built to stay inside the admin session —
 * no navigation away from the dashboard.
 */
export default function StatDrillDown({
  open,
  onClose,
  title,
  subtitle,
  queryUrl,
  rows,
  columns,
  rowKey,
  emptyText = "Nothing to show for this window.",
  href,
  hrefLabel,
}: {
  open: boolean;
  onClose: () => void;
  title?: string;
  subtitle?: string;
  queryUrl?: string;
  rows?: any[];
  columns: DrillColumn[];
  rowKey: (row: any, index: number) => Key;
  emptyText?: string;
  href?: string;
  hrefLabel?: string;
}) {
  const [data, setData] = useState<{ results: any[]; total: number } | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!open) return;
    if (!queryUrl) return;

    setLoading(true);
    setError(null);
    fetch(queryUrl)
      .then((r) => r.json().catch(() => ({})))
      .then((json) => {
        if (!json || !Array.isArray(json.results)) throw new Error("Invalid response");
        setData({ results: json.results, total: json.total ?? json.results.length });
      })
      .catch(() => setError("Could not load the detail list."))
      .finally(() => setLoading(false));
  }, [queryUrl, open]);

  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open, onClose]);

  if (!open) return null;

  const list: any[] | null = queryUrl ? data?.results ?? null : rows ?? null;
  const total: number | null = queryUrl ? data?.total ?? null : (rows?.length ?? null);

  return (
    <div className="fixed inset-0 z-[900] flex justify-end" role="dialog" aria-modal="true">
      <button
        aria-label="Close detail panel"
        className="absolute inset-0 bg-ink/40 backdrop-blur-[2px]"
        onClick={onClose}
      />
      <div className="relative w-full max-w-2xl h-full bg-surface shadow-2xl flex flex-col animate-[slide-in_.18s_ease]">
        <div className="flex items-start justify-between gap-4 border-b border-border px-5 py-4 bg-bg">
          <div className="min-w-0">
            <h2 className="font-bold text-lg truncate">{title}</h2>
            {subtitle && <p className="text-xs text-muted truncate mt-0.5">{subtitle}</p>}
          </div>
          <button
            onClick={onClose}
            className="rounded-md p-1.5 text-muted hover:text-ink hover:bg-surface"
            aria-label="Close"
          >
            <X size={18} />
          </button>
        </div>

        <div className="flex-1 overflow-y-auto px-5 py-4">
          {loading ? (
            <div className="space-y-2">
              {[0, 1, 2, 3, 4, 5].map((i) => (
                <div key={i} className="h-11 rounded-md bg-muted/30 animate-pulse" />
              ))}
            </div>
          ) : error ? (
            <p className="text-sm text-danger">{error}</p>
          ) : list === null ? (
            <p className="text-sm text-muted">Nothing to show for this window.</p>
          ) : list.length === 0 ? (
            <div className="py-10 text-center text-muted">
              <Inbox size={28} className="mx-auto mb-2 opacity-60" />
              <p className="text-sm">{emptyText}</p>
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead className="text-xs text-muted border-b bg-surface">
                  <tr>
                    {columns.map((c) => (
                      <th
                        key={c.key}
                        className={`py-2 px-3 ${c.align === "right" ? "text-right" : "text-left"} whitespace-nowrap`}
                      >
                        {c.label}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {list.map((row, idx) => (
                    <tr key={rowKey(row, idx)} className="border-b last:border-0">
                      {columns.map((c) => (
                        <td key={c.key} className={`py-2 px-3 ${c.align === "right" ? "text-right tabular-nums" : ""}`}>
                          {c.render(row)}
                        </td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
              {total !== null && (
                <p className="text-xs text-muted mt-3">
                  {total} total{total === 1 ? "" : "s"} matched.
                </p>
              )}
            </div>
          )}
        </div>

        {(href || hrefLabel) && (
          <div className="border-t border-border px-5 py-3 bg-bg">
            <Link
              href={href ?? "/admin"}
              className="inline-flex items-center gap-1 text-sm font-semibold text-amber hover:underline"
            >
              {hrefLabel ?? "Open full page"}
              <ArrowUpRight size={14} />
            </Link>
          </div>
        )}
      </div>
    </div>
  );
}