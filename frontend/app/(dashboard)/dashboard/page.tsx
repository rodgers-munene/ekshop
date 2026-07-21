import Link from "next/link";
import { serverFetch } from "@/lib/server-api";
import { Order, ShopDashboardStats } from "@/types/interface";
import { formatKES } from "@/lib/utils";
import StatCard from "@/components/dashboard/StatCard";
import SalesChart from "@/components/dashboard/SalesChart";
import OrderStatusBreakdown from "@/components/dashboard/OrderStatusBreakdown";
import TopProducts from "@/components/dashboard/TopProducts";
import OrderStatusPill from "@/components/dashboard/OrderStatusPill";

const EXCLUDED_FROM_REVENUE = new Set(["cancelled", "refunded"]);

function buildSalesTrend(orders: Order[]) {
  const days: { key: string; label: string; value: number }[] = [];
  const byKey = new Map<string, number>();

  for (let i = 13; i >= 0; i--) {
    const d = new Date();
    d.setDate(d.getDate() - i);
    const key = d.toISOString().slice(0, 10);
    days.push({ key, label: d.toLocaleDateString("en-KE", { day: "numeric", month: "short" }), value: 0 });
    byKey.set(key, 0);
  }

  for (const order of orders) {
    if (EXCLUDED_FROM_REVENUE.has(order.status)) continue;
    const key = order.created_at.slice(0, 10);
    if (byKey.has(key)) byKey.set(key, (byKey.get(key) ?? 0) + parseFloat(order.total));
  }

  return days.map((d) => ({ label: d.label, value: byKey.get(d.key) ?? 0 }));
}

function buildStatusCounts(orders: Order[]) {
  const counts: Record<string, number> = {};
  for (const order of orders) counts[order.status] = (counts[order.status] ?? 0) + 1;
  return counts;
}

function buildTopProducts(orders: Order[]) {
  const byName = new Map<string, { name: string; qty: number; revenue: number }>();

  for (const order of orders) {
    if (EXCLUDED_FROM_REVENUE.has(order.status)) continue;
    for (const item of order.items) {
      const name = item.product_snapshot?.name ?? "Product";
      const entry = byName.get(name) ?? { name, qty: 0, revenue: 0 };
      entry.qty += item.quantity;
      entry.revenue += parseFloat(item.line_total);
      byName.set(name, entry);
    }
  }

  return Array.from(byName.values()).sort((a, b) => b.revenue - a.revenue).slice(0, 5);
}

export default async function DashboardOverviewPage() {
  const [stats, orders] = await Promise.all([
    serverFetch<ShopDashboardStats>("/shops/me/dashboard").catch(() => null),
    serverFetch<Order[]>("/shops/me/orders").catch(() => []),
  ]);

  const salesTrend = buildSalesTrend(orders);
  const statusCounts = buildStatusCounts(orders);
  const topProducts = buildTopProducts(orders);
  const recentOrders = orders.slice(0, 5);

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold">Overview</h1>
        <div className="hidden sm:flex gap-3">
          <Link href="/dashboard/products/new" className="btn-accent">Add a product</Link>
          <Link href="/dashboard/orders" className="btn-navy">View orders</Link>
        </div>
      </div>

      {stats ? (
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
          <StatCard label="Total sales" value={formatKES(stats.total_sales)} />
          <StatCard label="Total orders" value={stats.total_orders} />
          <StatCard label="Products" value={stats.total_products} />
          <StatCard label="Rating" value={`${parseFloat(stats.rating_avg).toFixed(1)} (${stats.rating_count})`} />
        </div>
      ) : (
        <p className="text-muted text-sm mb-6">Could not load shop stats.</p>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4 mb-6">
        <div className="lg:col-span-2">
          <SalesChart data={salesTrend} />
        </div>
        <OrderStatusBreakdown counts={statusCounts} total={orders.length} />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4 mb-6">
        <TopProducts products={topProducts} />

        <div className="lg:col-span-2 card overflow-hidden">
          <div className="px-4 py-3 border-b border-border flex items-center justify-between">
            <p className="text-sm font-semibold">Recent orders</p>
            <Link href="/dashboard/orders" className="text-xs text-amber underline underline-offset-2">View all</Link>
          </div>
          {recentOrders.length === 0 ? (
            <p className="text-sm text-muted px-4 py-6">No orders yet.</p>
          ) : (
            <div className="divide-y divide-border">
              {recentOrders.map((order) => (
                <Link
                  key={order.id}
                  href={`/dashboard/orders/${order.id}`}
                  className="flex items-center justify-between px-4 py-3 text-sm hover:bg-surface transition-colors"
                >
                  <div>
                    <p className="font-mono text-xs text-muted">#{order.id.slice(0, 8).toUpperCase()}</p>
                    <p className="text-xs text-muted">
                      {new Date(order.created_at).toLocaleDateString("en-KE", { day: "numeric", month: "short" })}
                    </p>
                  </div>
                  <p className="font-bold">{formatKES(order.total)}</p>
                  <OrderStatusPill status={order.status} />
                </Link>
              ))}
            </div>
          )}
        </div>
      </div>

      <div className="flex sm:hidden gap-3">
        <Link href="/dashboard/products/new" className="btn-accent">Add a product</Link>
        <Link href="/dashboard/orders" className="btn-navy">View orders</Link>
      </div>
    </div>
  );
}
