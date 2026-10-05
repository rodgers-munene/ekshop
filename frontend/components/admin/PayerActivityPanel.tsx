"use client";

import { useEffect, useState } from "react";

import { formatKES } from "@/lib/utils";
import type { PayerActivityRead } from "@/types/interface";

/**
 * Who actually paid, transaction by transaction.
 *
 * Every money figure elsewhere on the dashboard is an aggregate, so there was no
 * way to answer "who paid?" or to reconcile a total against the payments behind
 * it. This lists the payments themselves, with the provider reference so a
 * figure can be checked against a Safaricom or Paystack statement.
 */
export default function PayerActivityPanel({
  rangeQuery,
}: {
  /** Same query string the rest of the dashboard is filtered by. */
  rangeQuery: string;
}) {
  // Results are stored against the query that produced them, so `loading` is
  // derived rather than flipped in the effect body. That way changing the filter
  // does not blank out a table the admin is already reading, and there is no
  // synchronous setState inside the effect.
  const [loaded, setLoaded] = useState<{
    key: string;
    data: PayerActivityRead | null;
  } | null>(null);
  const [failedKey, setFailedKey] = useState<string | null>(null);

  const loading = loaded?.key !== rangeQuery && failedKey !== rangeQuery;
  const data = loaded?.key === rangeQuery ? loaded.data : null;

  useEffect(() => {
    let cancelled = false;
    fetch(`/api/admin/stats/payers?${rangeQuery}`)
      .then((r) => (r.ok ? r.json() : Promise.reject(r.status)))
      .then((json) => {
        if (!cancelled) {
          setLoaded({ key: rangeQuery, data: json as PayerActivityRead });
        }
      })
      .catch(() => {
        // Stated rather than left blank: an empty table is indistinguishable
        // from "nobody paid", which is the exact question being asked here.
        if (!cancelled) {
          setLoaded({ key: rangeQuery, data: null });
          setFailedKey(rangeQuery);
        }
      });
    return () => {
      cancelled = true;
    };
  }, [rangeQuery]);

  const failed = failedKey === rangeQuery;

  return (
    <section className="bg-card rounded-xl border border-border p-5">
      <header className="flex flex-wrap items-baseline justify-between gap-2 mb-4">
        <div>
          <h2 className="text-sm font-bold text-ink">Who paid</h2>
          <p className="text-xs text-muted mt-0.5">
            Individual payments in the selected period
            {data ? ` · ${data.period}` : ""}
          </p>
        </div>
        {data && (
          <div className="flex items-center gap-4 text-xs">
            <span className="text-muted">
              <span className="font-bold text-ink">{data.payer_count}</span>{" "}
              {data.payer_count === 1 ? "customer" : "customers"}
            </span>
            <span className="text-muted">
              <span className="font-bold text-ink">{data.payment_count}</span>{" "}
              {data.payment_count === 1 ? "payment" : "payments"}
            </span>
            <span className="text-muted">
              received{" "}
              <span className="font-bold text-ink">
                {formatKES(parseFloat(data.total_cash_received))}
              </span>
            </span>
          </div>
        )}
      </header>

      {loading && (
        <p className="text-xs text-muted py-6 text-center">Loading payments…</p>
      )}

      {!loading && failed && (
        <p className="text-xs text-danger py-6 text-center">
          Could not load payments. The figures below this panel are unaffected.
        </p>
      )}

      {!loading && !failed && data && data.results.length === 0 && (
        <p className="text-xs text-muted py-6 text-center">
          No payments recorded in this period.
        </p>
      )}

      {!loading && !failed && data && data.results.length > 0 && (
        <div className="overflow-x-auto -mx-1">
          <table className="w-full text-xs">
            <thead>
              <tr className="text-left text-muted border-b border-border">
                <th className="font-semibold py-2 pr-3">Customer</th>
                <th className="font-semibold py-2 pr-3">Paid at</th>
                <th className="font-semibold py-2 pr-3">Provider</th>
                <th className="font-semibold py-2 pr-3">Reference</th>
                <th className="font-semibold py-2 pr-3 text-right">Amount</th>
              </tr>
            </thead>
            <tbody>
              {data.results.map((p) => (
                <tr
                  key={p.payment_id}
                  className="border-b border-border/50 last:border-0"
                >
                  <td className="py-2 pr-3">
                    <span className="font-semibold text-ink">
                      {p.first_name} {p.last_name}
                    </span>
                    <span className="block text-muted">{p.email}</span>
                  </td>
                  <td className="py-2 pr-3 text-muted whitespace-nowrap">
                    {new Date(p.paid_at).toLocaleString("en-KE", {
                      dateStyle: "medium",
                      timeStyle: "short",
                      timeZone: "Africa/Nairobi",
                    })}
                  </td>
                  <td className="py-2 pr-3 text-muted capitalize">
                    {p.provider}
                    {p.channel ? ` · ${p.channel}` : ""}
                  </td>
                  <td className="py-2 pr-3 font-mono text-[10px] text-muted">
                    {p.provider_ref ?? "—"}
                  </td>
                  <td className="py-2 pr-3 text-right font-semibold text-ink whitespace-nowrap">
                    {formatKES(parseFloat(p.amount))}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}