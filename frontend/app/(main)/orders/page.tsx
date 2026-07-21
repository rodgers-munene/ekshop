import Link from "next/link";
import { redirect } from "next/navigation";
import { serverFetch } from "@/lib/server-api";
import { OrderGroup } from "@/types/interface";
import { formatKES } from "@/lib/utils";

const STATUS_STYLE: Record<string, string> = {
  pending_payment: "bg-amber/15 text-amber",
  paid:            "bg-info/10 text-info",
  processing:      "bg-info/10 text-info",
  shipped:         "bg-progress/10 text-progress",
  delivered:       "bg-success/10 text-success",
  cancelled:       "bg-danger/10 text-danger",
};

export default async function OrdersPage() {
  const orders = await serverFetch<OrderGroup[]>("/orders/").catch(() => null);
  if (orders === null) redirect("/login");

  return (
    <div className="w-full max-w-4xl mx-auto px-4 md:px-6 py-6">
      <h1 className="text-2xl font-bold mb-6">My Orders</h1>

      {orders.length === 0 ? (
        <div className="card flex flex-col items-center justify-center py-24 text-center">
          <p className="text-2xl font-extrabold mb-2">No orders yet</p>
          <p className="text-muted text-sm mb-6">Start shopping to see your orders here.</p>
          <Link href="/products" className="btn-accent">
            Browse Products
          </Link>
        </div>
      ) : (
        <div className="space-y-4">
          {orders.map((group) => (
            <Link
              key={group.id}
              href={`/orders/${group.id}`}
              className="card block overflow-hidden hover:shadow-md transition-shadow"
            >
              <div className="flex items-center justify-between px-5 py-3 border-b border-border">
                <div className="flex items-center gap-3">
                  <span className="text-xs text-muted font-mono">#{group.id.slice(0, 8).toUpperCase()}</span>
                  <span className={`text-xs font-medium px-2 py-0.5 rounded-full ${STATUS_STYLE[group.status] ?? "bg-ink/10 text-ink"}`}>
                    {group.status.replace(/_/g, " ")}
                  </span>
                </div>
                <span className="text-xs text-muted">{new Date(group.created_at).toLocaleDateString("en-KE", { day: "numeric", month: "short", year: "numeric" })}</span>
              </div>
              <div className="px-5 py-3 flex items-center justify-between">
                <p className="text-sm text-muted">{group.orders.length} shop{group.orders.length !== 1 ? "s" : ""} · {group.orders.reduce((s, o) => s + o.items.length, 0)} items</p>
                <p className="font-bold text-ink">{formatKES(group.total)}</p>
              </div>
            </Link>
          ))}
        </div>
      )}
    </div>
  );
}
