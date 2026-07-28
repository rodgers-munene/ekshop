"use client";

import { useEffect, useState } from "react";
import { Truck } from "lucide-react";
import { Delivery } from "@/types/interface";

const EVENT_LABEL: Record<string, string> = {
  pending: "Pending",
  assigned: "Agent assigned",
  picked: "Picked up",
  in_transit: "In transit",
  delivered: "Delivered",
  cancelled: "Cancelled",
};

export default function DeliveryTracker({ orderId }: { orderId: string }) {
  const [delivery, setDelivery] = useState<Delivery | null>(null);
  const [loaded, setLoaded] = useState(false);

  useEffect(() => {
    fetch(`/api/delivery/${orderId}/track`)
      .then((r) => (r.ok ? r.json() : null))
      .then(setDelivery)
      .catch(() => setDelivery(null))
      .finally(() => setLoaded(true));
  }, [orderId]);

  if (!loaded || !delivery) return null;

  return (
    <div className="px-4 py-3 border-t border-border bg-surface/50">
      <div className="flex items-center gap-2 mb-2 text-sm font-medium">
        <Truck size={15} className="text-amber" />
        Delivery
        {delivery.tracking_number && (
          <span className="text-xs text-muted font-normal">· Tracking #{delivery.tracking_number}</span>
        )}
      </div>
      <div className="space-y-1.5">
        {delivery.events.map((event) => (
          <div key={event.id} className="flex items-center justify-between text-xs">
            <span className="text-ink">{EVENT_LABEL[event.status] ?? event.status}</span>
            <span className="text-muted">
              {new Date(event.created_at).toLocaleString("en-KE", { day: "numeric", month: "short", hour: "2-digit", minute: "2-digit" })}
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}
