import { serverFetch } from "@/lib/server-api";
import { AdminStats, AdminTrendPoint } from "@/types/interface";
import { formatKES } from "@/lib/utils";
import StatCard from "@/components/dashboard/StatCard";
import SalesChart from "@/components/dashboard/SalesChart";

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
