"use client";

import { useEffect, useState } from "react";
import { formatKES } from "@/lib/utils";
import StatCard from "@/components/dashboard/StatCard";
import SalesChart from "@/components/dashboard/SalesChart";
import PeriodFilter, { PeriodKey } from "@/components/dashboard/PeriodFilter";
import { AdminOverview } from "@/types/interface";

const formatDay = (d: string) =>
  new Date(d).toLocaleDateString("en-KE", {
    day: "numeric",
    month: "short",
    year: "numeric",
    timeZone: "Africa/Nairobi",
  });

function OverviewSkeleton() {
  return (
    <div className="grid grid-cols-2 lg:grid-cols-5 gap-4">
      {[0, 1, 2, 3, 4].map((i) => (
        <div key={i} className="card p-5 h-[88px] bg-muted/30 animate-pulse" />
      ))}
    </div>
  );
}

export default function AdminOverviewClient({ initial }: { initial: AdminOverview }) {
  const [period, setPeriod] = useState<PeriodKey>("month");
  const [data, setData] = useState(initial);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    setLoading(true);
    fetch(`/api/admin/stats/overview?period=${period}`)
      .then((r) => r.json())
      .then(setData)
      .finally(() => setLoading(false));
  }, [period]);

  const { metrics: m, previous: p } = data;

  const summary = [
    {
      label: "Revenue",
      value: formatKES(m.revenue),
      prev: parseFloat(p.revenue),
    },
    { label: "Paid orders", value: m.orders, prev: p.orders },
    {
      label: "Avg. order value",
      value: formatKES(m.average_order_value),
      prev: parseFloat(p.average_order_value),
    },
    { label: "New users", value: m.new_users, prev: p.new_users },
    { label: "New shops", value: m.new_shops, prev: p.new_shops },
  ];

  return (
    <div>
      <div className="flex flex-wrap items-center justify-between gap-3 mb-6">
        <div>
          <h1 className="text-2xl font-bold">Overview</h1>
          <p className="text-sm text-muted">
            {formatDay(data.start)} – today — compared against the same span before
          </p>
        </div>
        <PeriodFilter value={period} onChange={setPeriod} />
      </div>

      {loading ? (
        <OverviewSkeleton />
      ) : (
        <div className="grid grid-cols-2 lg:grid-cols-5 gap-4 mb-8">
          {summary.map((s) => (
            <StatCard
              key={s.label}
              label={s.label}
              value={s.value}
              change={{
                current: typeof s.value === "string" ? parseFloat(s.value) : s.value,
                previous: s.prev,
                label: "prev period",
              }}
            />
          ))}
        </div>
      )}

      <h2 className="text-lg font-bold mb-3">Platform totals</h2>
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
        <StatCard label="Total users" value={data.totals.total_users} />
        <StatCard label="Buyers" value={data.totals.total_buyers} />
        <StatCard label="Sellers" value={data.totals.total_sellers} />
        <StatCard label="Total shops" value={data.totals.total_shops} />
        <StatCard label="Pending verification" value={data.totals.shops_pending_verification} />
        <StatCard label="Total products" value={data.totals.total_products} />
        <StatCard label="Paid orders" value={data.totals.total_orders} />
        <StatCard label="Revenue (all-time)" value={formatKES(parseFloat(data.totals.revenue_total))} />
      </div>

      {data.trend.length > 0 && (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
          <SalesChart
            data={data.trend.map((pt) => ({ label: pt.label, value: pt.revenue }))}
            title="Revenue (last 14 days)"
          />
          <SalesChart
            data={data.trend.map((pt) => ({ label: pt.label, value: pt.orders }))}
            title="Orders (last 14 days)"
            formatValue={(v) => `${v} order${v === 1 ? "" : "s"}`}
          />
        </div>
      )}
    </div>
  );
}