"use client";

import { useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Package, MapPin, Phone, Loader2 } from "lucide-react";
import { toast } from "sonner";
import { Delivery } from "@/types/interface";
import { formatKES } from "@/lib/utils";

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

export default function AgentDeliveriesPage() {
  const queryClient = useQueryClient();
  const [updatingId, setUpdatingId] = useState<string | null>(null);

  const { data: deliveries = [], isLoading } = useQuery({
    queryKey: ["agent-deliveries"],
    queryFn: () => fetch("/api/agent/deliveries").then((r) => r.json()) as Promise<Delivery[]>,
    refetchInterval: 20000,
  });

  async function advance(deliveryId: string, status: string) {
    setUpdatingId(deliveryId);
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
      setUpdatingId(null);
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
              updating={updatingId === delivery.id}
              onAdvance={(status) => advance(delivery.id, status)}
            />
          ))}

          {past.length > 0 && (
            <>
              <h2 className="text-sm font-bold text-muted mt-8 mb-2">Completed</h2>
              {past.map((delivery) => (
                <DeliveryCard key={delivery.id} delivery={delivery} updating={false} onAdvance={() => {}} />
              ))}
            </>
          )}
        </div>
      )}
    </div>
  );
}

function DeliveryCard({
  delivery,
  updating,
  onAdvance,
}: {
  delivery: Delivery;
  updating: boolean;
  onAdvance: (status: string) => void;
}) {
  const order = delivery.order;
  const address = order?.delivery_address;
  const nextStatuses = DELIVERY_TRANSITIONS[delivery.status] ?? [];

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
        </div>
      )}

      {order?.items && order.items.length > 0 && (
        <ul className="text-sm text-muted mb-3 space-y-0.5">
          {order.items.map((item) => (
            <li key={item.id}>
              {item.quantity}× {item.product_snapshot.name}
            </li>
          ))}
        </ul>
      )}

      {order && (
        <p className="text-sm font-bold mb-3">{formatKES(order.total)}</p>
      )}

      {nextStatuses.length > 0 && (
        <div className="flex gap-2 pt-2 border-t border-border">
          {nextStatuses.map((status) => (
            <button
              key={status}
              onClick={() => onAdvance(status)}
              disabled={updating}
              className={`text-sm font-medium px-3 py-1.5 rounded-md disabled:opacity-50 ${
                status === "cancelled"
                  ? "text-danger hover:bg-danger/10"
                  : "btn-accent"
              }`}
            >
              {updating ? "..." : `Mark ${STATUS_LABELS[status]}`}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
