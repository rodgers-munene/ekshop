import Link from "next/link";
import { serverFetch } from "@/lib/server-api";
import { Order } from "@/types/interface";
import { formatKES } from "@/lib/utils";
import OrderStatusPill from "@/components/dashboard/OrderStatusPill";

export default async function DashboardOrdersPage() {
  const orders = await serverFetch<Order[]>("/shops/me/orders").catch(() => []);

  return (
    <div>
      <h1 className="text-2xl font-bold mb-6">Orders</h1>

      {orders.length === 0 ? (
        <div className="card flex flex-col items-center justify-center py-20 text-center">
          <p className="font-bold mb-2">No orders yet</p>
          <p className="text-muted text-sm">Orders placed with your shop will show up here.</p>
        </div>
      ) : (
        <div className="card overflow-hidden overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-border text-left text-xs text-muted">
                <th className="px-4 py-3 font-medium">Order</th>
                <th className="px-4 py-3 font-medium">Date</th>
                <th className="px-4 py-3 font-medium">Items</th>
                <th className="px-4 py-3 font-medium">Total</th>
                <th className="px-4 py-3 font-medium">Status</th>
                <th className="px-4 py-3 font-medium"></th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border">
              {orders.map((order) => (
                <tr key={order.id}>
                  <td className="px-4 py-3 font-mono text-xs">#{order.id.slice(0, 8).toUpperCase()}</td>
                  <td className="px-4 py-3 text-muted">
                    {new Date(order.created_at).toLocaleDateString("en-KE", { day: "numeric", month: "short", year: "numeric" })}
                  </td>
                  <td className="px-4 py-3">{order.items.length}</td>
                  <td className="px-4 py-3 font-bold">{formatKES(order.total)}</td>
                  <td className="px-4 py-3">
                    <OrderStatusPill status={order.status} />
                  </td>
                  <td className="px-4 py-3 text-right">
                    <Link href={`/dashboard/orders/${order.id}`} className="text-amber text-sm underline underline-offset-2">
                      View
                    </Link>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
