"use client";

import { useMemo, useState } from "react";

import { formatKES } from "@/lib/utils";
import type { ChurnOutreachResult, ChurnRiskInsight } from "@/types/interface";

const DEFAULT_SUBJECT = "We saved your favourites";
const DEFAULT_BODY =
  "It's been a while since your last order with us. We have added a few things we think you'll like, and it costs nothing to have another look.";

/**
 * Churn-risk customers, and a way to actually reach them.
 *
 * The list used to be "every buyer whose account was older than 60 days", which
 * included people who had bought that morning -- so chasing them would have been
 * both pointless and embarrassing. It is now buyers whose last *order* predates
 * the window, sorted by how long they have been away.
 *
 * Email rather than SMS, because no SMS provider exists in this service. The
 * send is re-validated server-side against the churn query at the moment of
 * sending, so a stale screen cannot pitch a customer who just came back.
 */
export default function ChurnOutreachPanel({
  insights,
}: {
  insights: ChurnRiskInsight[] | null;
}) {
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [subject, setSubject] = useState(DEFAULT_SUBJECT);
  const [body, setBody] = useState(DEFAULT_BODY);
  const [sending, setSending] = useState(false);
  const [result, setResult] = useState<ChurnOutreachResult | null>(null);
  const [error, setError] = useState<string | null>(null);

  const rows = useMemo(() => insights ?? [], [insights]);

  // Selections are intersected with the live list at render time rather than
  // pruned in an effect: someone who has since dropped off the list cannot stay
  // in the send, without a setState inside an effect.
  const liveIds = useMemo(() => new Set(rows.map((r) => r.user_id)), [rows]);
  const effective = useMemo(
    () => [...selected].filter((id) => liveIds.has(id)),
    [selected, liveIds],
  );

  const totalValue = useMemo(
    () => rows.reduce((sum, r) => sum + parseFloat(r.lifetime_value), 0),
    [rows],
  );

  const toggle = (id: string) =>
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else if (next.size < 100) next.add(id);
      return next;
    });

  const send = async (dryRun: boolean) => {
    setSending(true);
    setError(null);
    setResult(null);
    try {
      const res = await fetch("/api/admin/churn/outreach", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          user_ids: effective,
          subject,
          body,
          dry_run: dryRun,
        }),
      });
      const json = await res.json();
      if (!res.ok) {
        setError(json?.detail ?? `Send failed (${res.status})`);
        return;
      }
      setResult(json as ChurnOutreachResult);
      if (!dryRun) setSelected(new Set());
    } catch {
      setError("Could not reach the server. Nothing was sent.");
    } finally {
      setSending(false);
    }
  };

  if (insights == null) {
    return (
      <section className="bg-card rounded-xl border border-border p-5">
        <h2 className="text-sm font-bold text-ink">Churn risk</h2>
        <p className="text-xs text-muted mt-2">Could not load churn data.</p>
      </section>
    );
  }

  return (
    <section className="bg-card rounded-xl border border-border p-5">
      <header className="flex flex-wrap items-baseline justify-between gap-2 mb-3">
        <div>
          <h2 className="text-sm font-bold text-ink">Churn risk</h2>
          <p className="text-xs text-muted mt-0.5">
            Buyers whose last order predates this period
            {rows.length > 0 && ` · ${rows.length} shown`}
          </p>
        </div>
        {rows.length > 0 && (
          <p className="text-xs text-muted">
            Combined lifetime value{" "}
            <span className="font-bold text-ink">{formatKES(totalValue)}</span>
          </p>
        )}
      </header>

      {rows.length === 0 ? (
        <p className="text-xs text-muted py-6 text-center">
          Nobody in this period has gone quiet. Either that is genuinely good
          news, or the period is too short to show it.
        </p>
      ) : (
        <>
          <div className="overflow-x-auto -mx-1 mb-4">
            <table className="w-full text-xs">
              <thead>
                <tr className="text-left text-muted border-b border-border">
                  <th className="py-2 pr-2 w-8">
                    <input
                      type="checkbox"
                      aria-label="Select all"
                      checked={selected.size === rows.length && rows.length > 0}
                      onChange={(e) =>
                        setSelected(
                          e.target.checked
                            ? new Set(rows.map((r) => r.user_id))
                            : new Set(),
                        )
                      }
                    />
                  </th>
                  <th className="font-semibold py-2 pr-3">Customer</th>
                  <th className="font-semibold py-2 pr-3">Last order</th>
                  <th className="font-semibold py-2 pr-3">Orders</th>
                  <th className="font-semibold py-2 pr-3">Lifetime value</th>
                  <th className="font-semibold py-2 pr-3">Risk</th>
                </tr>
              </thead>
              <tbody>
                {rows.map((r) => (
                  <tr
                    key={r.user_id}
                    className="border-b border-border/50 last:border-0"
                  >
                    <td className="py-2 pr-2">
                      <input
                        type="checkbox"
                        aria-label={`Select ${r.first_name} ${r.last_name}`}
                        checked={selected.has(r.user_id)}
                        onChange={() => toggle(r.user_id)}
                      />
                    </td>
                    <td className="py-2 pr-3">
                      <span className="font-semibold text-ink">
                        {r.first_name} {r.last_name}
                      </span>
                      <span className="block text-muted">{r.email}</span>
                    </td>
                    <td className="py-2 pr-3 text-muted whitespace-nowrap">
                      {r.last_order_at
                        ? `${r.days_idle} days ago`
                        : "never ordered"}
                    </td>
                    <td className="py-2 pr-3 text-muted">{r.order_count}</td>
                    <td className="py-2 pr-3 text-muted whitespace-nowrap">
                      {formatKES(parseFloat(r.lifetime_value))}
                    </td>
                    <td className="py-2 pr-3">
                      <span
                        className={
                          r.risk === "high"
                            ? "text-danger font-semibold"
                            : r.risk === "medium"
                              ? "text-warning font-semibold"
                              : "text-muted"
                        }
                      >
                        {r.risk}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <div className="border-t border-border pt-4 space-y-3">
            <label className="block">
              <span className="text-xs font-semibold text-ink">Subject</span>
              <input
                value={subject}
                onChange={(e) => setSubject(e.target.value)}
                maxLength={150}
                className="input-field w-full mt-1 text-xs"
              />
            </label>
            <label className="block">
              <span className="text-xs font-semibold text-ink">Message</span>
              <textarea
                value={body}
                onChange={(e) => setBody(e.target.value)}
                rows={4}
                maxLength={5000}
                className="input-field w-full mt-1 text-xs"
              />
            </label>

            <div className="flex flex-wrap items-center gap-2">
              <button
                onClick={() => send(true)}
                disabled={selected.size === 0 || sending}
                className="px-3 py-1.5 text-xs font-semibold rounded-md border border-border text-ink disabled:opacity-40"
              >
                Check {selected.size} recipient{selected.size === 1 ? "" : "s"}
              </button>
              <button
                onClick={() => send(false)}
                disabled={
                  selected.size === 0 || sending || subject.length < 3 || body.length < 10
                }
                className="px-3 py-1.5 text-xs font-semibold rounded-md bg-ink text-white disabled:opacity-40"
              >
                {sending
                  ? "Sending…"
                  : `Email ${selected.size} customer${selected.size === 1 ? "" : "s"}`}
              </button>
              {selected.size === 100 && (
                <span className="text-xs text-muted">
                  Batch limit reached. Send these, then select more.
                </span>
              )}
            </div>

            {error && (
              <p className="text-xs text-danger">
                {error} Nothing was sent.
              </p>
            )}

            {result && (
              <div className="text-xs border-t border-border pt-3">
                <p className="font-semibold text-ink">
                  {result.results.some((r) => r.status === "would_send")
                    ? "Would email"
                    : "Emailed"}{" "}
                  {result.sent || result.results.filter((r) => r.status === "would_send").length}{" "}
                  of {result.attempted}
                  {result.failed > 0 && ` · ${result.failed} failed`}
                  {result.skipped_not_at_risk > 0 &&
                    ` · ${result.skipped_not_at_risk} skipped`}
                </p>
                <ul className="mt-1 space-y-0.5">
                  {result.results
                    .filter((r) => r.status === "skipped" || r.status === "failed")
                    .map((r) => (
                      <li key={r.user_id} className="text-muted">
                        {r.email ?? r.user_id}: {r.reason ?? r.error ?? r.status}
                      </li>
                    ))}
                </ul>
              </div>
            )}
          </div>
        </>
      )}
    </section>
  );
}