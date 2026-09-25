"use client";

import { useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Package, MapPin, Phone, Loader2, Check } from "lucide-react";
import { toast } from "sonner";
import { Delivery, OrderItem } from "@/types/interface";
import { formatKES } from "@/lib/utils";
import ReadOnlyMap from "@/components/geo/ReadOnlyMap";

const DELIVERY_TRANSITIONS: Record<string, string[]> = {
  assigned: ["picked", "cancelled"],
  picked: ["in_transit"],
  in_transit: ["delivered", "cancelled"],
};

const STATUS_LABELS: Record<string, string> = {
  pending: "Pending",
  assigned: "Assigned",
  picked: "Picked up",
  in_transit: "In transit",
  delivered: "Delivered",
  cancelled: "Cancelled",
};

const STATUS_STYLES: Record<string, string> = {
  pending: "bg-surface text-muted",
  assigned: "bg-info/10 text-info",
  picked: "bg-amber/10 text-amber",
  in_transit: "bg-amber/10 text-amber",
  delivered: "bg-success/10 text-success",
  cancelled: "bg-danger/10 text-danger",
};

/** Which delivery is being updated, and to what — so only the button that was
    actually tapped shows a spinner. */
type Pending = { id: string; status: string } | null;

export default function AgentDeliveriesPage() {
  const queryClient = useQueryClient();
  const [pending, setPending] = useState<Pending>(null);

  const { data: deliveries = [], isLoading } = useQuery({
    queryKey: ["agent-deliveries"],
    queryFn: () => fetch("/api/agent/deliveries").then((r) => r.json()) as Promise<Delivery[]>,
    refetchInterval: 20000,
  });

  async function advance(deliveryId: string, status: string) {
    setPending({ id: deliveryId, status });
    try {
      const res = await fetch(`/api/agent/deliveries/${deliveryId}/status`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ status }),
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) {
        toast.error(data.detail ?? "Failed to update delivery");
        return;
      }
      toast.success(`Marked as ${STATUS_LABELS[status] ?? status}`);
      queryClient.invalidateQueries({ queryKey: ["agent-deliveries"] });
    } catch {
      toast.error("Something went wrong. Try again.");
    } finally {
      setPending(null);
    }
  }

  const active = deliveries.filter((d) => d.status !== "delivered" && d.status !== "cancelled");
  const past = deliveries.filter((d) => d.status === "delivered" || d.status === "cancelled");

  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-20">
        <Loader2 size={24} className="animate-spin text-muted" />
      </div>
    );
  }

  return (
    <div>
      <h1 className="text-2xl font-bold mb-6">My deliveries</h1>

      {deliveries.length === 0 ? (
        <div className="card flex flex-col items-center justify-center py-20 text-center">
          <Package size={32} className="text-muted mb-3" />
          <p className="font-bold mb-1">No deliveries assigned</p>
          <p className="text-muted text-sm">New assignments will show up here.</p>
        </div>
      ) : (
        <div className="space-y-4">
          {active.map((delivery) => (
            <DeliveryCard
              key={delivery.id}
              delivery={delivery}
              pendingStatus={pending?.id === delivery.id ? pending.status : null}
              busy={pending?.id === delivery.id}
              onAdvance={(status) => advance(delivery.id, status)}
            />
          ))}

          {past.length > 0 && (
            <>
              <h2 className="text-sm font-bold text-muted mt-8 mb-2">Completed</h2>
              {past.map((delivery) => (
                <DeliveryCard key={delivery.id} delivery={delivery} pendingStatus={null} busy={false} onAdvance={() => {}} />
              ))}
            </>
          )}
        </div>
      )}
    </div>
  );
}

/**
 * One line of an order, written so the quantity cannot be read as part of the
 * product name.
 *
 * The old "2× Smocha + Chips + Club Soda Combo" put the multiplier flush
 * against a name that itself lists several things, and an agent read it as two
 * smochas instead of two whole combos. The count now sits in its own box away
 * from the text, the name wraps in full instead of being truncated, and
 * anything above one is spelled out underneath.
 */
function ItemLine({ item }: { item: OrderItem }) {
  const multiple = item.quantity > 1;

  return (
    <li className="flex items-start gap-3 py-2.5">
      <span
        className={`shrink-0 flex flex-col items-center justify-center w-11 h-11 rounded-lg font-bold leading-none ${
          multiple ? "bg-navy text-white" : "bg-surface text-muted"
        }`}
      >
        <span className="text-base tabular-nums">{item.quantity}</span>
        <span className="text-[9px] font-semibold uppercase tracking-wide opacity-70">qty</span>
      </span>

      <div className="min-w-0">
        <p className="text-sm font-medium text-ink break-words">{item.product_snapshot.name}</p>
        {multiple && (
          <p className="text-xs text-amber font-medium mt-0.5">
            Take {item.quantity} of this whole item — everything the name lists, {item.quantity} times.
          </p>
        )}
      </div>
    </li>
  );
}

function DeliveryCard({
  delivery,
  pendingStatus,
  busy,
  onAdvance,
}: {
  delivery: Delivery;
  pendingStatus: string | null;
  busy: boolean;
  onAdvance: (status: string) => void;
}) {
  const order = delivery.order;
  const address = order?.delivery_address;
  const nextStatuses = DELIVERY_TRANSITIONS[delivery.status] ?? [];
  const items = order?.items ?? [];
  const totalUnits = items.reduce((sum, item) => sum + item.quantity, 0);

  return (
    <div className="card p-4">
      <div className="flex items-start justify-between gap-3 mb-3">
        <div>
          <p className="font-mono text-xs text-muted">{delivery.tracking_number}</p>
          <p className="font-bold">{order?.shop?.name ?? "Order"}</p>
        </div>
        <span className={`text-xs font-medium px-2 py-1 rounded-full shrink-0 ${STATUS_STYLES[delivery.status] ?? "bg-surface"}`}>
          {STATUS_LABELS[delivery.status] ?? delivery.status}
        </span>
      </div>

      {address && (
        <div className="text-sm space-y-1 mb-3">
          <p className="font-medium">
            {order?.buyer_name}
          </p>
          <p className="flex items-center gap-1.5 text-muted">
            <Phone size={13} /> {address.phone}
          </p>
          <p className="flex items-center gap-1.5 text-muted">
            <MapPin size={13} />
            {[address.exact_location || address.town, address.county].filter(Boolean).join(", ")}
          </p>
          {address.lat && address.lng && (
            <div className="mt-2">
              <ReadOnlyMap lat={address.lat} lng={address.lng} height="h-40" />
            </div>
          )}
        </div>
      )}

      {items.length > 0 && (
        <div className="mb-3 rounded-lg border border-border bg-surface/40 px-3 py-1">
          <div className="flex items-center justify-between py-1.5">
            <p className="text-[11px] font-semibold uppercase tracking-wide text-muted">To deliver</p>
            <p className="text-[11px] font-semibold text-muted tabular-nums">
              {totalUnits} {totalUnits === 1 ? "unit" : "units"}
              {items.length !== totalUnits && ` · ${items.length} ${items.length === 1 ? "line" : "lines"}`}
            </p>
          </div>
          <ul className="divide-y divide-border">
            {items.map((item) => (
              <ItemLine key={item.id} item={item} />
            ))}
          </ul>
        </div>
      )}

      {order && (
        <p className="text-sm font-bold mb-3">{formatKES(order.total)}</p>
      )}

      {nextStatuses.length > 0 && (
        <div className="flex gap-2 pt-2 border-t border-border">
          {nextStatuses.map((status) => {
            const isPending = pendingStatus === status;
            return (
              <button
                key={status}
                onClick={() => onAdvance(status)}
                disabled={busy}
                aria-busy={isPending}
                className={`inline-flex items-center justify-center gap-1.5 text-sm font-medium px-3 py-1.5 rounded-md transition-all active:scale-95 disabled:opacity-60 disabled:cursor-wait ${
                  status === "cancelled"
                    ? "text-danger hover:bg-danger/10"
                    : "btn-accent"
                }`}
              >
                {isPending ? (
                  <>
                    <Loader2 size={14} className="animate-spin" />
                    Marking…
                  </>
                ) : (
                  <>
                    {status !== "cancelled" && <Check size={14} />}
                    Mark {STATUS_LABELS[status]}
                  </>
                )}
              </button>
            );
          })}
        </div>
      )}
    </div>
  );
}
