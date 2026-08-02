import Link from "next/link";
import { notFound, redirect } from "next/navigation";
import { serverFetch, ServerFetchError } from "@/lib/server-api";
import { OrderGroup } from "@/types/interface";
import { formatKES } from "@/lib/utils";
import PaystackReturnHandler from "./PaystackReturnHandler";
import DeliveryTracker from "./DeliveryTracker";

const STATUS_STYLE: Record<string, string> = {
  pending_payment: "bg-amber/15 text-amber",
  paid:            "bg-info/10 text-info",
  processing:      "bg-info/10 text-info",
  shipped:         "bg-progress/10 text-progress",
  delivered:       "bg-success/10 text-success",
  cancelled:       "bg-danger/10 text-danger",
};

const STEPS = ["pending_payment", "paid", "processing", "shipped", "delivered"];

interface Props { params: Promise<{ id: string }> }

export default async function OrderDetailPage({ params }: Props) {
  const { id } = await params;

  const group = await serverFetch<OrderGroup>(`/orders/${id}`).catch((err) => {
    if (err instanceof ServerFetchError) {
      if (err.status === 401) redirect("/login");
      if (err.status === 404) notFound();
    }
    throw err;
  });

  const stepIndex = STEPS.indexOf(group.status);

  return (
    <div className="w-full max-w-4xl mx-auto px-4 md:px-6 py-6">
      <PaystackReturnHandler />

      {/* Header */}
      <div className="flex items-center gap-3 mb-2">
        <Link href="/orders" className="text-xs text-muted hover:text-amber underline">← Orders</Link>
      </div>
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold">Order #{group.id.slice(0, 8).toUpperCase()}</h1>
        <span className={`text-xs font-medium px-3 py-1 rounded-full ${STATUS_STYLE[group.status] ?? "bg-ink/10 text-ink"}`}>
          {group.status.replace(/_/g, " ")}
        </span>
      </div>

      {/* Progress tracker */}
      {group.status !== "cancelled" && (
        <div className="card mb-6 p-5 overflow-x-auto">
          <div className="flex items-center min-w-max gap-0">
            {STEPS.map((s, i) => (
              <div key={s} className="flex items-center">
                <div className="flex flex-col items-center">
                  <div className={`w-8 h-8 rounded-full flex items-center justify-center text-xs font-bold transition-colors ${
                    i <= stepIndex ? "bg-amber text-ink" : "bg-surface text-muted"
                  }`}>
                    {i < stepIndex ? "✓" : i + 1}
                  </div>
                  <span className="text-xs mt-1 text-muted whitespace-nowrap">{s.replace(/_/g, " ")}</span>
                </div>
                {i < STEPS.length - 1 && (
                  <div className={`h-0.5 w-12 mx-1 mb-4 ${i < stepIndex ? "bg-amber" : "bg-border"}`} />
                )}
              </div>
            ))}
          </div>
        </div>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">

        {/* Orders per shop */}
        <div className="lg:col-span-2 space-y-4">
          {group.orders.map((order) => (
            <div key={order.id} className="card overflow-hidden">
              <div className="flex items-center justify-between px-4 py-3 border-b border-border bg-surface">
                <p className="text-sm font-medium">{order.shop?.name ?? "Shop"}</p>
                <span className={`text-xs px-2 py-0.5 rounded-full ${STATUS_STYLE[order.status] ?? "bg-ink/10 text-ink"}`}>
                  {order.status.replace(/_/g, " ")}
                </span>
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
              <DeliveryTracker orderId={order.id} />
            </div>
          ))}
        </div>

        {/* Summary */}
        <div className="card p-5 flex flex-col gap-3 h-fit">
          <h2 className="font-semibold border-b border-border pb-2">Summary</h2>
          <div className="flex justify-between text-sm">
            <span className="text-muted">Subtotal</span>
            <span>{formatKES(group.subtotal)}</span>
          </div>
          <div className="flex justify-between text-sm">
            <span className="text-muted">Delivery</span>
            <span>{formatKES(group.delivery_fee)}</span>
          </div>
          <div className="flex justify-between font-bold border-t border-border pt-2">
            <span>Total</span>
            <span className="text-ink">{formatKES(group.total)}</span>
          </div>
          <p className="text-xs text-muted pt-1">
            Placed {new Date(group.created_at).toLocaleDateString("en-KE", { day: "numeric", month: "long", year: "numeric" })}
          </p>
        </div>
      </div>
    </div>
  );
}
