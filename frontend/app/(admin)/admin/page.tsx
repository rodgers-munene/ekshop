import { serverFetch } from "@/lib/server-api";
import { AdminStats, AdminTrendPoint, PeriodToDateMetrics } from "@/types/interface";
import { formatKES } from "@/lib/utils";
import StatCard from "@/components/dashboard/StatCard";
import SalesChart from "@/components/dashboard/SalesChart";

// Period boundaries are computed in Kenyan time on the backend; render them in
// the same zone so the server's own timezone (UTC in the container) can't shift
// "1 Sep 00:00 EAT" back to "31 Aug".
const formatDay = (d: Date | string) =>
  new Date(d).toLocaleDateString("en-KE", { day: "numeric", month: "short", year: "numeric", timeZone: "Africa/Nairobi" });

function PeriodSection({
  title,
  period,
  comparisonLabel,
}: {
  title: string;
  period: PeriodToDateMetrics;
  comparisonLabel: string;
}) {
  const { current, previous } = period;
  return (
    <section className="mb-6">
      <div className="flex flex-wrap items-baseline gap-x-3 mb-3">
        <h2 className="text-lg font-bold">{title}</h2>
        <p className="text-xs text-muted">
          {formatDay(period.start)} – {formatDay(new Date())}, compared with the same span {comparisonLabel}
        </p>
      </div>
      <div className="grid grid-cols-2 lg:grid-cols-5 gap-4">
        <StatCard
          label="Revenue"
          value={formatKES(current.revenue)}
          change={{ current: parseFloat(current.revenue), previous: parseFloat(previous.revenue), label: comparisonLabel }}
        />
        <StatCard
          label="Paid orders"
          value={current.orders}
          change={{ current: current.orders, previous: previous.orders, label: comparisonLabel }}
        />
        <StatCard
          label="Avg. order value"
          value={formatKES(current.average_order_value)}
          change={{
            current: parseFloat(current.average_order_value),
            previous: parseFloat(previous.average_order_value),
            label: comparisonLabel,
          }}
        />
        <StatCard
          label="New users"
          value={current.new_users}
          change={{ current: current.new_users, previous: previous.new_users, label: comparisonLabel }}
        />
        <StatCard
          label="New shops"
          value={current.new_shops}
          change={{ current: current.new_shops, previous: previous.new_shops, label: comparisonLabel }}
        />
      </div>
    </section>
  );
}

export default async function AdminOverviewPage() {
  const [stats, trend] = await Promise.all([
    serverFetch<AdminStats>("/admin/stats").catch(() => null),
    serverFetch<AdminTrendPoint[]>("/admin/stats/trend").catch(() => [] as AdminTrendPoint[]),
  ]);

  if (!stats) {
    return <p className="text-muted text-sm">Could not load stats.</p>;
  }

  return (
    <div>
      <h1 className="text-2xl font-bold mb-6">Overview</h1>

      <PeriodSection title="Month to date" period={stats.mtd} comparisonLabel="last month" />
      <PeriodSection title="Year to date" period={stats.ytd} comparisonLabel="last year" />

      <h2 className="text-lg font-bold mb-3">Platform totals</h2>
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
        <StatCard label="Total users" value={stats.total_users} />
        <StatCard label="Buyers" value={stats.total_buyers} />
        <StatCard label="Sellers" value={stats.total_sellers} />
        <StatCard label="New users (7d)" value={stats.new_users_7d} />
        <StatCard label="Total shops" value={stats.total_shops} />
        <StatCard label="Pending verification" value={stats.shops_pending_verification} />
        <StatCard label="Total products" value={stats.total_products} />
        <StatCard label="Paid orders" value={stats.total_orders} />
        <StatCard label="Orders (7d)" value={stats.orders_7d} />
        <StatCard label="Revenue (total)" value={formatKES(parseFloat(stats.revenue_total))} />
        <StatCard label="Revenue (7d)" value={formatKES(parseFloat(stats.revenue_7d))} />
      </div>

      {trend.length > 0 && (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
          <SalesChart
            data={trend.map((p) => ({ label: p.label, value: p.revenue }))}
            title="Revenue (last 14 days)"
          />
          <SalesChart
            data={trend.map((p) => ({ label: p.label, value: p.orders }))}
            title="Orders (last 14 days)"
            formatValue={(v) => `${v} order${v === 1 ? "" : "s"}`}
          />
        </div>
      )}
    </div>
  );
}
