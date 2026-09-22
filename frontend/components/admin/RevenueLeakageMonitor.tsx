"use client";

import { useMemo } from "react";
import { MarginLeakageMetrics, MarginLeakageTrendPoint } from "@/types/interface";

function pct(value: number, total: number) {
  if (!total) return 0;
  return Math.round((value / total) * 100);
}

function FunnelBar({ label, value, total, color, sub }: { label: string; value: number; total: number; color: string; sub?: string }) {
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
  const path = points
    .map((p, i) => {
      const x = i * width;
      const y = 100 - (p.gmv / maxGmv) * 100;
      return `${i === 0 ? "M" : "L"} ${x} ${y}`;
    })
    .join(" ");
  const profitPath = points
    .map((p, i) => {
      const x = i * width;
      const y = 100 - (p.net_profit / maxGmv) * 100;
      return `${i === 0 ? "M" : "L"} ${x} ${y}`;
    })
    .join(" ");

  return (
    <div className="mt-4">
      <p className="text-xs font-medium text-muted mb-2">GMV vs Net profit trend</p>
      <div className="relative h-40 w-full">
        <svg viewBox="0 0 100 100" preserveAspectRatio="none" className="h-full w-full">
          <path d={path} fill="none" stroke="currentColor" strokeWidth="1.5" className="text-amber" />
          <path d={profitPath} fill="none" stroke="currentColor" strokeWidth="1.5" className="text-success" />
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
  const commission = useMemo(() => Number(data.platform_commission), [data.platform_commission]);
  const mpesa = useMemo(() => Number(data.mpesa_fees), [data.mpesa_fees]);
  const server = useMemo(() => Number(data.server_cost), [data.server_cost]);
  const net = useMemo(() => Number(data.net_profit), [data.net_profit]);

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
          <h3 className="font-bold">Revenue Leakage & Margin Monitor</h3>
          <p className="text-xs text-muted mt-1">
            {data.period === "custom" ? `${data.start} → ${data.end}` : data.period} · {data.orders} orders · AOV KES {Number(data.average_order_value).toLocaleString()}
          </p>
        </div>
        <div className="flex items-center gap-3">
          <button onClick={downloadPdf} className="text-xs border border-border rounded-md px-3 py-1.5 hover:border-amber transition-colors">Download PDF</button>
          <button onClick={downloadCsv} className="text-xs border border-border rounded-md px-3 py-1.5 hover:border-amber transition-colors">Download CSV</button>
          <div className="text-right">
            <p className="text-2xl font-bold">{data.gross_margin_pct.toFixed(1)}%</p>
            <p className="text-xs text-muted">Gross margin</p>
          </div>
        </div>
      </div>

      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <div className="card p-4">
          <p className="text-xs text-muted">GMV</p>
          <p className="text-lg font-bold mt-1">KES {gmv.toLocaleString()}</p>
        </div>
        <div className="card p-4">
          <p className="text-xs text-muted">Platform commission</p>
          <p className="text-lg font-bold mt-1 text-amber">KES {commission.toLocaleString()}</p>
          <p className="text-xs text-muted">{data.commission_rate_pct}%</p>
        </div>
        <div className="card p-4">
          <p className="text-xs text-muted">M-Pesa fees</p>
          <p className="text-lg font-bold mt-1 text-danger">KES {mpesa.toLocaleString()}</p>
          <p className="text-xs text-muted">{data.mpesa_rate_pct}%</p>
        </div>
        <div className="card p-4">
          <p className="text-xs text-muted">Net profit</p>
          <p className="text-lg font-bold mt-1 text-success">KES {net.toLocaleString()}</p>
        </div>
      </div>

      <div className="space-y-3">
        <FunnelBar label="Gross Merchandise Value" value={gmv} total={gmv} color="bg-amber" sub="100%" />
        <FunnelBar label="Platform commission (10%)" value={commission} total={gmv} color="bg-amber/70" sub={`${pct(commission, gmv)}%`} />
        <FunnelBar label="M-Pesa merchant fee (0.55%)" value={mpesa} total={gmv} color="bg-danger/70" sub={`${pct(mpesa, gmv)}%`} />
        <FunnelBar label="Server & API cost" value={server} total={gmv} color="bg-muted" sub={`${pct(server, gmv)}%`} />
        <FunnelBar label="Net profit" value={net} total={gmv} color="bg-success" sub={`${pct(net, gmv)}%`} />
      </div>

      <TrendChart points={data.trend} />
    </div>
  );
}
