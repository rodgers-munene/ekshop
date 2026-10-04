"use client";

import Link from "next/link";
import { useState } from "react";
import { formatKES } from "@/lib/utils";
import {
  RevenueBreakdown,
  RevenueBucket,
  StatusCount,
  TopAccounts,
  TopBuyerRow,
  TopMerchantRow,
  WeekdayAverageRow,
} from "@/types/interface";

const WEEKDAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"];

function statusLabel(status: string) {
  const text = status.replace(/_/g, " ");
  return text.charAt(0).toUpperCase() + text.slice(1);
}

function Section({ title, note, children }: { title: string; note?: string; children: React.ReactNode }) {
  return (
    <div className="card overflow-hidden">
      <div className="px-4 py-3 border-b border-border">
        <h3 className="font-bold">{title}</h3>
        {note && <p className="text-xs text-muted mt-0.5">{note}</p>}
      </div>
      <div className="overflow-x-auto">{children}</div>
    </div>
  );
}

function RevenueTable({ rows, periodLabel }: { rows: RevenueBucket[]; periodLabel: string }) {
  const totals = rows.reduce(
    (acc, r) => ({
      orders: acc.orders + r.orders,
      gmv: acc.gmv + Number(r.gmv),
      fee: acc.fee + Number(r.delivery_fee),
      total: acc.total + Number(r.total),
    }),
    { orders: 0, gmv: 0, fee: 0, total: 0 },
  );
  return (
    <table className="w-full text-sm">
      <thead className="text-xs text-muted border-b bg-surface">
        <tr>
          <th className="text-left py-2 px-3">{periodLabel}</th>
          <th className="text-right py-2 px-3">Orders</th>
          <th className="text-right py-2 px-3">GMV</th>
          <th className="text-right py-2 px-3">Delivery fees</th>
          <th className="text-right py-2 px-3">Total collected</th>
        </tr>
      </thead>
      <tbody>
        {rows.map((r) => (
          <tr key={r.label} className={`border-b last:border-0 ${r.orders === 0 ? "text-muted" : ""}`}>
            <td className="py-2 px-3 tabular-nums">{r.label}</td>
            <td className="py-2 px-3 text-right tabular-nums">{r.orders}</td>
            <td className="py-2 px-3 text-right tabular-nums">{formatKES(r.gmv)}</td>
            <td className="py-2 px-3 text-right tabular-nums">{formatKES(r.delivery_fee)}</td>
            <td className="py-2 px-3 text-right tabular-nums font-medium">{formatKES(r.total)}</td>
          </tr>
        ))}
      </tbody>
      <tfoot className="border-t bg-surface font-bold">
        <tr>
          <td className="py-2 px-3">Total</td>
          <td className="py-2 px-3 text-right tabular-nums">{totals.orders}</td>
          <td className="py-2 px-3 text-right tabular-nums">{formatKES(totals.gmv)}</td>
          <td className="py-2 px-3 text-right tabular-nums">{formatKES(totals.fee)}</td>
          <td className="py-2 px-3 text-right tabular-nums">{formatKES(totals.total)}</td>
        </tr>
      </tfoot>
    </table>
  );
}

function StatusTable({ rows, empty }: { rows: StatusCount[]; empty: string }) {
  if (rows.length === 0) return <p className="text-sm text-muted p-4">{empty}</p>;
  return (
    <table className="w-full text-sm">
      <thead className="text-xs text-muted border-b bg-surface">
        <tr>
          <th className="text-left py-2 px-3">Status</th>
          <th className="text-right py-2 px-3">Count</th>
        </tr>
      </thead>
      <tbody>
        {rows.map((r) => (
          <tr key={r.status} className="border-b last:border-0">
            <td className="py-2 px-3">{statusLabel(r.status)}</td>
            <td className="py-2 px-3 text-right tabular-nums">{r.count}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

function WeekdayTable({ rows, periodLabel }: { rows: WeekdayAverageRow[]; periodLabel: string }) {
  if (rows.length === 0) return <p className="text-sm text-muted p-4">No paid orders yet.</p>;
  return (
    <table className="w-full text-sm">
      <thead className="text-xs text-muted border-b bg-surface">
        <tr>
          <th className="text-left py-2 px-3">{periodLabel}</th>
          {WEEKDAYS.map((d) => (
            <th key={d} className="text-right py-2 px-3">{d.slice(0, 3)}</th>
          ))}
        </tr>
      </thead>
      <tbody>
        {rows.map((r) => {
          const best = Math.max(...r.averages);
          return (
            <tr key={r.label} className="border-b last:border-0">
              <td className="py-2 px-3 tabular-nums">{r.label}</td>
              {r.averages.map((v, i) => (
                <td
                  key={i}
                  className={`py-2 px-3 text-right tabular-nums ${best > 0 && v === best ? "font-bold text-gold" : ""}`}
                >
                  {v.toFixed(2)}
                </td>
              ))}
            </tr>
          );
        })}
      </tbody>
    </table>
  );
}

/** Shift a YYYY-MM-DD date by whole days without local-timezone drift. */
function shiftDay(iso: string, days: number) {
  const d = new Date(`${iso}T00:00:00Z`);
  d.setUTCDate(d.getUTCDate() + days);
  return d.toISOString().slice(0, 10);
}

function lastOrder(at: string | null) {
  return at ? new Date(at).toLocaleDateString("en-KE", { day: "numeric", month: "short", year: "numeric" }) : "—";
}

function ShareBar({ pct }: { pct: number }) {
  return (
    <div className="flex items-center justify-end gap-2">
      <div className="hidden sm:block w-16 h-1.5 rounded-full bg-surface overflow-hidden">
        <div className="h-full bg-amber" style={{ width: `${Math.min(pct, 100)}%` }} />
      </div>
      <span className="tabular-nums">{pct.toFixed(1)}%</span>
    </div>
  );
}

function TopMerchantsTable({ rows }: { rows: TopMerchantRow[] }) {
  if (rows.length === 0) return <p className="text-sm text-muted p-4">No paid orders in this range.</p>;
  return (
    <table className="w-full text-sm">
      <thead className="text-xs text-muted border-b bg-surface">
        <tr>
          <th className="text-left py-2 px-3">#</th>
          <th className="text-left py-2 px-3">Merchant</th>
          <th className="text-right py-2 px-3">Orders</th>
          <th className="text-right py-2 px-3">Buyers</th>
          <th className="text-right py-2 px-3">GMV</th>
          <th className="text-right py-2 px-3">Avg. order</th>
          <th className="text-right py-2 px-3">Share of GMV</th>
          <th className="text-left py-2 px-3">Last order</th>
        </tr>
      </thead>
      <tbody>
        {rows.map((r, i) => (
          <tr key={r.shop_id} className="border-b last:border-0">
            <td className="py-2 px-3 text-muted tabular-nums">{i + 1}</td>
            <td className="py-2 px-3">
              <Link href={`/admin/sellers/${r.shop_id}`} className="font-medium hover:underline">
                {r.name}
              </Link>
              {r.county && <p className="text-xs text-muted">{r.county}</p>}
            </td>
            <td className="py-2 px-3 text-right tabular-nums">{r.orders}</td>
            <td className="py-2 px-3 text-right tabular-nums">{r.buyers}</td>
            <td className="py-2 px-3 text-right tabular-nums font-medium">{formatKES(r.gmv)}</td>
            <td className="py-2 px-3 text-right tabular-nums">{formatKES(r.average_order_value)}</td>
            <td className="py-2 px-3 text-right"><ShareBar pct={r.share_pct} /></td>
            <td className="py-2 px-3 whitespace-nowrap">{lastOrder(r.last_order_at)}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

function TopBuyersTable({ rows }: { rows: TopBuyerRow[] }) {
  if (rows.length === 0) return <p className="text-sm text-muted p-4">No paid orders in this range.</p>;
  return (
    <table className="w-full text-sm">
      <thead className="text-xs text-muted border-b bg-surface">
        <tr>
          <th className="text-left py-2 px-3">#</th>
          <th className="text-left py-2 px-3">Buyer</th>
          <th className="text-left py-2 px-3">Phone</th>
          <th className="text-right py-2 px-3">Orders</th>
          <th className="text-right py-2 px-3">GMV</th>
          <th className="text-right py-2 px-3">Delivery fees</th>
          <th className="text-right py-2 px-3">Total paid</th>
          <th className="text-right py-2 px-3">Avg. order</th>
          <th className="text-right py-2 px-3">Share of GMV</th>
          <th className="text-left py-2 px-3">Last order</th>
        </tr>
      </thead>
      <tbody>
        {rows.map((r, i) => (
          <tr key={r.user_id} className="border-b last:border-0">
            <td className="py-2 px-3 text-muted tabular-nums">{i + 1}</td>
            <td className="py-2 px-3">
              <p className="font-medium">{r.name || "Unnamed buyer"}</p>
              <p className="text-xs text-muted">{r.email}</p>
            </td>
            <td className="py-2 px-3 whitespace-nowrap">{r.phone || "—"}</td>
            <td className="py-2 px-3 text-right tabular-nums">{r.orders}</td>
            <td className="py-2 px-3 text-right tabular-nums">{formatKES(r.gmv)}</td>
            <td className="py-2 px-3 text-right tabular-nums">{formatKES(r.delivery_fee)}</td>
            <td className="py-2 px-3 text-right tabular-nums font-medium">{formatKES(r.total)}</td>
            <td className="py-2 px-3 text-right tabular-nums">{formatKES(r.average_order_value)}</td>
            <td className="py-2 px-3 text-right"><ShareBar pct={r.share_pct} /></td>
            <td className="py-2 px-3 whitespace-nowrap">{lastOrder(r.last_order_at)}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

/** The date range drives the daily table and both top 5 tables together. */
function RangeReports({ initialRows, initialTop }: { initialRows: RevenueBucket[]; initialTop: TopAccounts }) {
  // The server's first row is today in Kenya, so presets are anchored to that rather than the browser clock.
  const today = initialRows[0]?.label ?? new Date().toISOString().slice(0, 10);
  const monthStart = `${today.slice(0, 8)}01`;
  const presets = [
    { label: "Last 7 days", start: shiftDay(today, -6), end: today },
    { label: "Last 30 days", start: shiftDay(today, -29), end: today },
    { label: "This month", start: monthStart, end: today },
    { label: "Last month", start: `${shiftDay(monthStart, -1).slice(0, 8)}01`, end: shiftDay(monthStart, -1) },
  ];

  const [start, setStart] = useState(shiftDay(today, -29));
  const [end, setEnd] = useState(today);
  const [rows, setRows] = useState(initialRows);
  const [top, setTop] = useState(initialTop);
  const [shown, setShown] = useState({ start: shiftDay(today, -29), end: today });
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function load(from: string, to: string) {
    setStart(from);
    setEnd(to);
    if (!from || !to) return setError("Pick both a start and an end date.");
    if (to < from) return setError("The end date must be on or after the start date.");
    setError(null);
    setLoading(true);
    try {
      const qs = `start=${from}&end=${to}`;
      const [dailyRes, topRes] = await Promise.all([
        fetch(`/api/admin/metrics/revenue-daily?${qs}`),
        fetch(`/api/admin/metrics/top-accounts?${qs}`),
      ]);
      const [daily, topData] = await Promise.all([
        dailyRes.json().catch(() => null),
        topRes.json().catch(() => null),
      ]);
      if (!dailyRes.ok) throw new Error(daily?.detail ?? "Could not load daily revenue.");
      if (!topRes.ok) throw new Error(topData?.detail ?? "Could not load the top merchants and buyers.");
      setRows(daily);
      setTop(topData);
      setShown({ start: from, end: to });
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not load this date range.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="space-y-6">
      <div className="card flex flex-wrap items-end gap-3 px-4 py-3">
        <div className="w-full">
          <h3 className="font-bold">Date range</h3>
          <p className="text-xs text-muted mt-0.5">
            Showing {shown.start} to {shown.end}. Applies to daily revenue and the top 5 tables. Ranges can be up to
            one year.
          </p>
        </div>
        <label className="text-xs text-muted">
          From
          <input
            type="date"
            className="input-field block mt-1"
            value={start}
            max={today}
            onChange={(e) => setStart(e.target.value)}
          />
        </label>
        <label className="text-xs text-muted">
          To
          <input
            type="date"
            className="input-field block mt-1"
            value={end}
            max={today}
            onChange={(e) => setEnd(e.target.value)}
          />
        </label>
        <button className="btn-accent" disabled={loading} onClick={() => load(start, end)}>
          {loading ? "Loading..." : "Apply"}
        </button>
        <div className="flex flex-wrap gap-2">
          {presets.map((p) => (
            <button
              key={p.label}
              disabled={loading}
              onClick={() => load(p.start, p.end)}
              className={`px-3 py-1.5 text-xs rounded-full border transition-colors ${
                shown.start === p.start && shown.end === p.end
                  ? "border-amber text-ink bg-amber/10"
                  : "border-border text-muted hover:text-ink"
              }`}
            >
              {p.label}
            </button>
          ))}
        </div>
        {error && <p className="w-full text-sm text-danger">{error}</p>}
      </div>

      <div className={`space-y-6 transition-opacity ${loading ? "opacity-50" : ""}`}>
        <Section title="Daily revenue">
          <RevenueTable rows={rows} periodLabel="Date" />
        </Section>

        <Section title="Top 5 merchants" note={`Ranked by GMV out of ${formatKES(top.gmv_total)} in this range.`}>
          <TopMerchantsTable rows={top.merchants} />
        </Section>

        <Section title="Top 5 buyers" note="Ranked by GMV. Total paid includes delivery fees.">
          <TopBuyersTable rows={top.buyers} />
        </Section>
      </div>
    </div>
  );
}

export default function RevenueBreakdownPanel({ data }: { data: RevenueBreakdown }) {
  return (
    <div className="space-y-6">
      <RangeReports initialRows={data.daily} initialTop={data.top} />

      <Section title="Monthly revenue (last 12 months)">
        <RevenueTable rows={data.monthly} periodLabel="Month" />
      </Section>

      <Section title="Yearly revenue">
        <RevenueTable rows={data.yearly} periodLabel="Year" />
      </Section>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <Section title="Checkouts by status" note="Every checkout, including ones never paid.">
          <StatusTable rows={data.checkout_status} empty="No checkouts yet." />
        </Section>
        <Section title="Payment attempts by status" note="Each M-Pesa or card attempt, including failures.">
          <StatusTable rows={data.payment_status} empty="No payment attempts yet." />
        </Section>
      </div>

      <Section
        title="Average orders per weekday (all time)"
        note="Days with no orders count as zero. The busiest day is highlighted."
      >
        <WeekdayTable rows={[{ label: "All time", averages: data.weekday_overall }]} periodLabel="Range" />
      </Section>

      <Section title="Average orders per weekday (last 12 months)">
        <WeekdayTable rows={data.weekday_by_month} periodLabel="Month" />
      </Section>

      <Section title="Average orders per weekday (last 5 years)">
        <WeekdayTable rows={data.weekday_by_year} periodLabel="Year" />
      </Section>
    </div>
  );
}
