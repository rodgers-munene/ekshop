"use client";

import { useEffect, useState } from "react";
import { formatKES } from "@/lib/utils";
import StatCard from "@/components/dashboard/StatCard";
import SalesChart from "@/components/dashboard/SalesChart";
import TrendChart from "@/components/dashboard/TrendChart";
import PayerActivityPanel from "@/components/admin/PayerActivityPanel";
import PeriodFilter, {
  PeriodKey,
  CustomRange,
  isoDay,
} from "@/components/dashboard/PeriodFilter";
import StatDrillDown from "@/components/admin/StatDrillDown";
import { DrillSpec, ordersSpec, productsSpec, shopsSpec, usersSpec } from "@/components/admin/drillColumns";
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

export default function AdminOverviewClient({ initial }: { initial: AdminOverview | null }) {
  const [period, setPeriod] = useState<PeriodKey>("month");
  const [custom, setCustom] = useState<CustomRange>({
    from: isoDay(-29),
    to: isoDay(),
  });
  const [data, setData] = useState<AdminOverview | null>(initial);
  const [loading, setLoading] = useState(false);
  const [drill, setDrill] = useState<DrillSpec | null>(null);

  // A custom range travels as explicit bounds rather than as `period`, so the
  // backend can use it verbatim instead of guessing at a preset. One string,
  // shared by the cards and the payer panel, so the two can never be filtered
  // by different windows.
  const rangeQuery =
    period === "custom"
      ? `date_from=${custom.from}&date_to=${custom.to}`
      : `period=${period}`;

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    fetch(`/api/admin/stats/overview?${rangeQuery}`)
      .then((r) => (r.ok ? r.json() : Promise.resolve(null)))
      .then((json) => {
        if (!cancelled && json && typeof json === "object" && json.metrics) {
          setData(json as AdminOverview);
        }
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [rangeQuery]);

  const { metrics: m, previous: p } = data ?? { metrics: {} as AdminOverview["metrics"], previous: {} as AdminOverview["previous"] };

  const summary = [
    {
      label: "Total transacted",
      value: formatKES(m.total_transacted),
      prev: parseFloat(p.total_transacted),
      spec: ordersSpec(period),
      hint: "Goods + delivery + tax in the selected period",
    },
    {
      label: "GMV (goods)",
      value: formatKES(m.gmv),
      prev: parseFloat(p.gmv),
      spec: ordersSpec(period),
      hint: "Value of goods only",
    },
    {
      label: "Paid orders",
      value: m.orders,
      prev: p.orders,
      spec: ordersSpec(period),
      hint: "Recent paid order groups",
    },
    {
      label: "Avg. order value",
      value: formatKES(m.average_order_value),
      prev: parseFloat(p.average_order_value),
      spec: ordersSpec(period),
      hint: "Recent paid orders",
    },
    {
      label: "New users",
      value: m.new_users,
      prev: p.new_users,
      spec: usersSpec(),
      hint: "Latest signups",
    },
    {
      label: "New shops",
      value: m.new_shops,
      prev: p.new_shops,
      spec: shopsSpec(),
      hint: "Latest shops",
    },
  ];

  return (
    <div>
      <div className="flex flex-wrap items-center justify-between gap-3 mb-6">
        <div>
          <h1 className="text-2xl font-bold">Overview</h1>
          <p className="text-sm text-muted">
            {data ? `${formatDay(data.start)} – today — compared against the same span before` : "Loading overview…"}
          </p>
        </div>
        <PeriodFilter value={period} onChange={setPeriod} onCustomChange={setCustom} custom={custom} />
      </div>

      {loading && <OverviewSkeleton />}

      {!loading && !data && (
        <div className="card p-10 text-center text-sm text-muted">Could not load overview stats.</div>
      )}

      {!loading && data && (
        <>
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
                hint={s.hint}
                onClick={() => setDrill(s.spec)}
              />
            ))}
          </div>

          <h2 className="text-lg font-bold mb-3">Platform totals</h2>
          <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
            <StatCard label="Total users" value={data.totals.total_users} onClick={() => setDrill(usersSpec())} hint="Latest signups" />
            <StatCard label="Buyers" value={data.totals.total_buyers} onClick={() => setDrill(usersSpec("buyer"))} hint="Latest buyer signups" />
            <StatCard label="Sellers" value={data.totals.total_sellers} onClick={() => setDrill(usersSpec("seller"))} hint="Latest seller signups" />
            <StatCard label="Total shops" value={data.totals.total_shops} onClick={() => setDrill(shopsSpec())} hint="Latest shops" />
            <StatCard
              label="Pending verification"
              value={data.totals.shops_pending_verification}
              onClick={() => setDrill(shopsSpec("pending", "Shops pending verification"))}
              hint="Shops awaiting approval"
            />
            <StatCard label="Total products" value={data.totals.total_products} onClick={() => setDrill(productsSpec())} hint="Latest products" />
            <StatCard label="Paid orders" value={data.totals.total_orders} onClick={() => setDrill(ordersSpec())} hint="Baskets behind a successful payment, all time" />
            {/* The first four numbers used to share one label, and all of them
                counted orders placed rather than money received. */}
            <StatCard
              label="Cash received"
              value={formatKES(parseFloat(data.totals.cash_received_total))}
              onClick={() => setDrill(ordersSpec())}
              hint="Actual payments received, all time"
            />
            <StatCard
              label="Refunds"
              value={formatKES(parseFloat(data.totals.refunds_total))}
              onClick={() => setDrill(ordersSpec())}
              hint="Paid back to customers. Not netted into the figures above."
            />
            <StatCard
              label="GMV"
              value={formatKES(parseFloat(data.totals.gmv_total))}
              onClick={() => setDrill(ordersSpec())}
              hint="Value of goods only, all time"
            />
            <StatCard
              label="Total transacted"
              value={formatKES(parseFloat(data.totals.total_transacted_total))}
              onClick={() => setDrill(ordersSpec())}
              hint="Goods + delivery + tax. Money that moved through the platform"
            />
            <StatCard
              label="Platform revenue"
              value={
                data.totals.revenue_total == null
                  ? "Not set"
                  : formatKES(parseFloat(data.totals.revenue_total))
              }
              onClick={() => setDrill(ordersSpec())}
              hint={
                data.totals.revenue_total == null
                  ? "No commission rate configured. Nothing in the data model records one."
                  : "Commission on goods, all time"
              }
            />
          </div>

          {data.trend.length > 0 && (
            <div className="grid grid-cols-1 gap-4">
              <TrendChart
                points={data.trend.map((pt) => ({ label: pt.label }))}
                series={[
                  {
                    key: "gmv",
                    label: "GMV (goods)",
                    color: "text-gold",
                    values: data.trend.map((pt) => pt.gmv),
                  },
                  {
                    key: "transacted",
                    label: "Total transacted",
                    color: "text-info",
                    values: data.trend.map((pt) => pt.total_transacted),
                  },
                  ...(data.totals.revenue_total != null
                    ? [
                        {
                          key: "revenue",
                          label: "Platform revenue",
                          color: "text-success",
                          values: data.trend.map((pt) => pt.revenue_earned),
                        },
                      ]
                    : []),
                ]}
                formatValue={(v) => formatKES(v)}
                footnote={
                  data.totals.revenue_total == null
                    ? "Platform revenue is not plotted: no commission rate is configured, and the specification has no commission field to read one from."
                    : undefined
                }
              />
              <SalesChart
                data={data.trend.map((pt) => ({ label: pt.label, value: pt.orders }))}
                title="Baskets paid (last 14 days)"
                formatValue={(v) => `${v} order${v === 1 ? "" : "s"}`}
              />
            </div>
          )}

          <div className="mt-4">
            <PayerActivityPanel rangeQuery={rangeQuery} />
          </div>
        </>
      )}

      <StatDrillDown
        open={!!drill}
        onClose={() => setDrill(null)}
        title={drill?.title}
        subtitle={drill?.subtitle}
        queryUrl={drill?.queryUrl}
        rows={drill?.rows}
        columns={drill?.columns ?? []}
        rowKey={drill?.rowKey ?? ((_r, i) => i)}
        emptyText={drill?.emptyText}
        href={drill?.href}
        hrefLabel={drill?.hrefLabel}
      />
    </div>
  );
}