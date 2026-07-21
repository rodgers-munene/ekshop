import Link from "next/link";
import { notFound } from "next/navigation";
import { serverFetch } from "@/lib/server-api";
import { Order } from "@/types/interface";
import { formatKES } from "@/lib/utils";
import OrderStatusPill from "@/components/dashboard/OrderStatusPill";
import OrderStatusAction from "@/components/dashboard/OrderStatusAction";

interface Props {
  params: Promise<{ id: string }>;
}

export default async function DashboardOrderDetailPage({ params }: Props) {
  const { id } = await params;
  const order = await serverFetch<Order>(`/shops/me/orders/${id}`).catch(() => null);
  if (!order) notFound();

  const address = order.delivery_address;

  return (
    <div className="max-w-3xl">
      <Link href="/dashboard/orders" className="text-xs text-muted hover:text-amber underline">← Orders</Link>

      <div className="flex items-center justify-between mt-2 mb-6">
        <h1 className="text-2xl font-bold">Order #{order.id.slice(0, 8).toUpperCase()}</h1>
        <OrderStatusPill status={order.status} />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <div className="lg:col-span-2 space-y-4">
          <div className="card overflow-hidden">
            <div className="px-4 py-3 border-b border-border bg-surface">
              <p className="text-sm font-medium">Items</p>
            </div>
            <div className="divide-y divide-border">
              {order.items.map((item) => (
                <div key={item.id} className="flex items-center justify-between px-4 py-3 text-sm">
                  <div>
                    <p className="font-medium">{item.product_snapshot?.name ?? "Product"}</p>
                    <p className="text-xs text-muted">Qty: {item.quantity} × {formatKES(item.unit_price)}</p>
                  </div>
                  <p className="font-bold text-ink">{formatKES(item.line_total)}</p>
                </div>
              ))}
            </div>
          </div>

          <div className="card p-5">
            <OrderStatusAction orderId={order.id} status={order.status} />
          </div>
        </div>

        <div className="space-y-4">
          <div className="card p-5">
            <h2 className="font-semibold border-b border-border pb-2 mb-3">Buyer</h2>
            <p className="text-sm font-medium">{order.buyer_name ?? "Buyer"}</p>
            {address && (
              <p className="text-sm text-muted mt-1">
                {address.phone}<br />
                {[address.exact_location, address.apartment, address.town, address.county].filter(Boolean).join(", ")}
              </p>
            )}
          </div>

          <div className="card p-5 flex flex-col gap-3">
            <h2 className="font-semibold border-b border-border pb-2">Summary</h2>
            <div className="flex justify-between text-sm">
              <span className="text-muted">Subtotal</span>
              <span>{formatKES(order.subtotal)}</span>
            </div>
            <div className="flex justify-between text-sm">
              <span className="text-muted">Delivery</span>
              <span>{formatKES(order.delivery_fee)}</span>
            </div>
            <div className="flex justify-between font-bold border-t border-border pt-2">
              <span>Total</span>
              <span className="text-ink">{formatKES(order.total)}</span>
            </div>
            <p className="text-xs text-muted pt-1">
              Placed {new Date(order.created_at).toLocaleDateString("en-KE", { day: "numeric", month: "long", year: "numeric" })}
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}
