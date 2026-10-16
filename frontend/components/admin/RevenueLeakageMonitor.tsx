"use client";

import { useMemo } from "react";
import { MarginLeakageMetrics, MarginLeakageTrendPoint } from "@/types/interface";

function pct(value: number, total: number) {
  if (!total) return 0;
  return Math.round((value / total) * 100);
}

function money(value: string | null | undefined) {
  // An unset rate is unknown, not zero. Printing KES 0 would read as "this
  // cost nothing" and would quietly make the margin look better than it is.
  if (value == null || value === "") return "Not set";
  return `KES ${Number(value).toLocaleString()}`;
}

function FunnelBar({
  label,
  value,
  total,
  color,
  sub,
  note,
}: {
  label: string;
  value: number | null;
  total: number;
  color: string;
  sub?: string;
  note?: string;
}) {
  if (value == null) {
    return (
      <div className="space-y-1">
        <div className="flex items-center justify-between text-xs">
          <span className="text-muted">{label}</span>
          <span className="text-muted">Not configured</span>
        </div>
        <div className="h-2 w-full rounded-full bg-surface overflow-hidden" />
        <p className="text-right text-xs font-semibold text-muted">{note ?? "—"}</p>
      </div>
    );
  }
  const width = total ? Math.max((value / total) * 100, 2) : 0;
  return (
    <div className="space-y-1">
      <div className="flex items-center justify-between text-xs">
        <span className="text-muted">{label}</span>
        <span className="font-medium tabular-nums">{sub ?? `${pct(value, total)}%`}</span>
      </div>
      <div className="h-2 w-full rounded-full bg-surface overflow-hidden">
        <div className={`h-full rounded-full ${color}`} style={{ width: `${width}%` }} />
      </div>
      <p className="text-right text-xs font-semibold tabular-nums">KES {value.toLocaleString()}</p>
    </div>
  );
}

function TrendChart({ points }: { points: MarginLeakageTrendPoint[] }) {
  if (!points.length) return <p className="text-xs text-muted">No trend data for this period.</p>;
  const maxGmv = Math.max(...points.map((p) => p.gmv), 1);
  const width = 100 / (points.length - 1 || 1);
  // A missing profit for a day means a rate was not configured, so that point is
  // skipped rather than plotted as zero -- a zero would invent a day where the
  // platform earned nothing.
  const lineFor = (pick: (p: MarginLeakageTrendPoint) => number | null) => {
    let d = "";
    points.forEach((p, i) => {
      const v = pick(p);
      if (v == null) return;
      const x = i * width;
      const y = 100 - (v / maxGmv) * 100;
      d += `${d ? " L" : "M"} ${x} ${y}`;
    });
    return d;
  };

  const path = lineFor((p) => p.gmv);
  const profitPath = lineFor((p) => p.net_profit);

  return (
    <div className="mt-4">
      <p className="text-xs font-medium text-muted mb-2">GMV vs Net profit trend</p>
      <div className="relative h-40 w-full">
        <svg viewBox="0 0 100 100" preserveAspectRatio="none" className="h-full w-full">
          {/* non-scaling-stroke keeps the line one pixel thick; without it the
              non-uniform viewBox scale squashes the stroke vertically. */}
          <path
            d={path}
            fill="none"
            stroke="currentColor"
            strokeWidth="2"
            vectorEffect="non-scaling-stroke"
            className="text-gold"
          />
          <path
            d={profitPath}
            fill="none"
            stroke="currentColor"
            strokeWidth="2"
            vectorEffect="non-scaling-stroke"
            className="text-success"
          />
        </svg>
        <div className="flex items-center gap-4 mt-2 text-xs text-muted">
          <span className="flex items-center gap-1"><span className="w-3 h-1 rounded bg-amber inline-block" /> GMV</span>
          <span className="flex items-center gap-1"><span className="w-3 h-1 rounded bg-success inline-block" /> Net profit</span>
        </div>
      </div>
    </div>
  );
}

export default function RevenueLeakageMonitor({ data }: { data: MarginLeakageMetrics }) {
  const gmv = useMemo(() => Number(data.gmv), [data.gmv]);
  const gmv1p = useMemo(() => Number(data.gmv_1p), [data.gmv_1p]);
  const gmv3p = useMemo(() => Number(data.gmv_3p), [data.gmv_3p]);
  // null, not zero: an unconfigured rate is unknown, and Number(null) would
  // silently turn it into a cost of zero.
  const commission = data.platform_commission == null ? null : Number(data.platform_commission);
  const mpesa = data.mpesa_fees == null ? null : Number(data.mpesa_fees);
  const server = data.server_cost == null ? null : Number(data.server_cost);
  const net = data.net_profit == null ? null : Number(data.net_profit);

  function downloadCsv() {
    const params = new URLSearchParams();
    if (data.period && data.period !== "custom") params.set("period", data.period);
    const start = (data.start as string | undefined)?.split("T")[0];
    const end = (data.end as string | undefined)?.split("T")[0];
    if (start) params.set("start", start);
    if (end) params.set("end", end);
    window.open(`/api/admin/reports/margin-leakage.csv?${params.toString()}`, "_blank");
  }

  function downloadPdf() {
    const params = new URLSearchParams();
    if (data.period && data.period !== "custom") params.set("period", data.period);
    window.open(`/api/admin/reports/margin-leakage?${params.toString()}`, "_blank");
  }

  return (
    <div className="card p-5 space-y-5">
      <div className="flex items-start justify-between gap-3">
        <div>
          <h3 className="font-bold">Revenue Leakage &amp; Margin Monitor</h3>
          <p className="text-xs text-muted mt-1">
            {data.period === "custom" ? `${data.start} → ${data.end}` : data.period} · {data.orders} orders · AOV KES {Number(data.average_order_value).toLocaleString()}
          </p>
        </div>
        <div className="flex items-center gap-3">
          <button onClick={downloadPdf} className="text-xs border border-border rounded-md px-3 py-1.5 hover:border-amber transition-colors">Download PDF</button>
          <button onClick={downloadCsv} className="text-xs border border-border rounded-md px-3 py-1.5 hover:border-amber transition-colors">Download CSV</button>
          <div className="text-right">
            <p className="text-2xl font-bold">
              {data.gross_margin_pct == null ? "—" : `${data.gross_margin_pct.toFixed(1)}%`}
            </p>
            <p className="text-xs text-muted">
              {data.gross_margin_pct == null ? "Gross margin not set" : "Gross margin"}
            </p>
          </div>
        </div>
      </div>

      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <div className="card p-4">
          <p className="text-xs text-muted">GMV (goods)</p>
          <p className="text-lg font-bold mt-1">KES {gmv.toLocaleString()}</p>
          <p className="text-xs text-muted">
            1P {gmv1p.toLocaleString()} · 3P {gmv3p.toLocaleString()}
          </p>
        </div>
        <div className="card p-4">
          <p className="text-xs text-muted">Platform commission (3P only)</p>
          <p className="text-lg font-bold mt-1 text-gold">{money(data.platform_commission)}</p>
          <p className="text-xs text-muted">
            {data.commission_rate_pct == null ? "Rate not set" : `${data.commission_rate_pct}% of marketplace goods`}
          </p>
        </div>
        <div className="card p-4">
          <p className="text-xs text-muted">M-Pesa fees</p>
          <p className="text-lg font-bold mt-1 text-danger">{money(data.mpesa_fees)}</p>
          <p className="text-xs text-muted">
            {data.mpesa_rate_pct == null ? "Rate not set" : `${data.mpesa_rate_pct}% of what customers paid`}
          </p>
        </div>
        <div className="card p-4">
          <p className="text-xs text-muted">Net profit</p>
          <p className="text-lg font-bold mt-1 text-success">{money(data.net_profit)}</p>
          <p className="text-xs text-muted">
            {data.net_profit == null ? "Not calculated" : "Commission less fees and cost"}
          </p>
        </div>
      </div>

      <div className="space-y-3">
        <FunnelBar label="Gross Merchandise Value" value={gmv} total={gmv} color="bg-amber" sub="100%" />
        <FunnelBar label="— of which Ekshop 1P" value={gmv1p} total={gmv} color="bg-forest/60" sub={`${pct(gmv1p, gmv)}%`} />
        <FunnelBar label="— of which marketplace 3P" value={gmv3p} total={gmv} color="bg-info/60" sub={`${pct(gmv3p, gmv)}%`} />
        <FunnelBar
          label="Platform commission"
          value={commission}
          total={gmv}
          color="bg-amber/70"
          sub={commission == null ? undefined : `${pct(commission, gmv)}% of goods`}
          note="No commission rate configured"
        />
        <FunnelBar
          label="M-Pesa merchant fee"
          value={mpesa}
          total={gmv}
          color="bg-danger/70"
          sub={mpesa == null ? undefined : `${pct(mpesa, gmv)}%`}
          note="No fee rate configured"
        />
        <FunnelBar
          label="Server & API cost"
          value={server}
          total={gmv}
          color="bg-muted"
          sub={server == null ? undefined : `${pct(server, gmv)}%`}
          note="No server cost configured"
        />
        <FunnelBar
          label="Net profit"
          value={net}
          total={gmv}
          color="bg-success"
          sub={net == null ? undefined : `${pct(net, gmv)}%`}
          note="Not calculated until every rate is configured"
        />
      </div>

      <TrendChart points={data.trend} />
    </div>
  );
}
