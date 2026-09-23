"use client";

import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { toast } from "sonner";
import { Delivery } from "@/types/interface";
import { formatKES } from "@/lib/utils";

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

export default function AgentJobPage() {
  const params = useParams();
  const router = useRouter();
  const deliveryId = params?.id as string;

  const [delivery, setDelivery] = useState<Delivery | null>(null);
  const [loading, setLoading] = useState(true);
  const [updating, setUpdating] = useState(false);

  useEffect(() => {
    if (!deliveryId) return;
    fetch(`/api/agent/deliveries/${deliveryId}`)
      .then((r) => (r.ok ? r.json() : Promise.reject()))
      .then((data: Delivery) => {
        setDelivery(data);
        setLoading(false);
      })
      .catch(() => {
        setLoading(false);
      });
  }, [deliveryId]);

  async function updateStatus(status: string) {
    if (!deliveryId) return;
    setUpdating(true);
    try {
      const res = await fetch(`/api/agent/deliveries/${deliveryId}/status`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ status }),
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) {
        toast.error(data.detail ?? "Failed to update");
        return;
      }
      toast.success(`Marked as ${STATUS_LABELS[status] ?? status}`);
      setDelivery(data);
    } catch {
      toast.error("Something went wrong. Try again.");
    } finally {
      setUpdating(false);
    }
  }

  function navigateTo(lat?: number, lng?: number, label?: string) {
    if (!lat || !lng) {
      toast.error("Location not available");
      return;
    }
    window.open(`https://www.google.com/maps/dir/?api=1&destination=${encodeURIComponent(`${lat},${lng}`)}`, "_blank");
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center py-20">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-amber" />
      </div>
    );
  }

  if (!delivery) {
    return (
      <div className="flex flex-col items-center justify-center py-20 text-center">
        <p className="font-bold mb-1">Delivery not found</p>
        <button onClick={() => router.push("/agent")} className="btn-accent mt-4">Back to dashboard</button>
      </div>
    );
  }

  const order = delivery.order;
  const address = order?.delivery_address;
  const nextStatuses: string[] = [];

  if (delivery.status === "assigned") nextStatuses.push("picked");
  if (delivery.status === "picked") nextStatuses.push("in_transit");
  if (delivery.status === "in_transit") nextStatuses.push("delivered");

  return (
    <div className="max-w-lg mx-auto px-4 py-6 space-y-4">
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-bold">Delivery</h1>
        <span className={`text-xs font-medium px-2 py-1 rounded-full ${STATUS_STYLES[delivery.status] ?? "bg-surface text-muted"}`}>
          {STATUS_LABELS[delivery.status] ?? delivery.status}
        </span>
      </div>

      <div className="card p-5 space-y-3">
        <div>
          <p className="text-xs text-muted mb-1">Tracking</p>
          <p className="font-mono text-sm font-medium">{delivery.tracking_number}</p>
        </div>
        <div>
          <p className="text-xs text-muted mb-1">Shop</p>
          <p className="text-sm font-medium">{order?.shop?.name ?? "—"}</p>
        </div>
        <div>
          <p className="text-xs text-muted mb-1">Customer</p>
          <p className="text-sm font-medium">{order?.buyer_name ?? "—"}</p>
        </div>
        {address && (
          <div>
            <p className="text-xs text-muted mb-1">Delivery address</p>
            <p className="text-sm">{address.phone}</p>
            <p className="text-sm text-muted">
              {[address.exact_location, address.town, address.county].filter(Boolean).join(", ")}
            </p>
          </div>
        )}
        {delivery.distance_km != null && delivery.duration_min != null && (
          <div className="flex gap-4 text-xs text-muted">
            <span>{delivery.distance_km} km</span>
            <span>{Math.round(delivery.duration_min)} min</span>
          </div>
        )}
      </div>

      {order?.items && order.items.length > 0 && (
        <div className="card p-5">
          <p className="text-xs text-muted mb-2">Package</p>
          <ul className="space-y-1">
            {order.items.map((item) => (
              <li key={item.id} className="text-sm flex justify-between">
                <span>{item.quantity}× {item.product_snapshot?.name ?? "Item"}</span>
              </li>
            ))}
          </ul>
          <div className="border-t border-border mt-3 pt-3 flex justify-between text-sm font-medium">
            <span>Total</span>
            <span>{formatKES(order.total)}</span>
          </div>
        </div>
      )}

      <div className="card p-5">
        <p className="text-xs text-muted mb-2">Actions</p>
        <div className="grid grid-cols-2 gap-3">
          <button
            onClick={() => navigateTo(delivery.order?.shop?.lat, delivery.order?.shop?.lng, "Shop")}
            className="card p-4 flex flex-col items-center gap-2 hover:border-amber transition-colors"
          >
            <svg width="20" height="20" fill="none" stroke="currentColor" strokeWidth="1.8" viewBox="0 0 24 24">
              <path d="M21 10c0 6-9 12-9 12S3 16 3 10a9 9 0 0118 0z" />
              <circle cx="12" cy="10" r="3" />
            </svg>
            <span className="text-xs font-medium">Navigate to shop</span>
          </button>
          <button
            onClick={() => navigateTo(address?.lat, address?.lng, "Customer")}
            className="card p-4 flex flex-col items-center gap-2 hover:border-amber transition-colors"
          >
            <svg width="20" height="20" fill="none" stroke="currentColor" strokeWidth="1.8" viewBox="0 0 24 24">
              <path d="M21 10c0 6-9 12-9 12S3 16 3 10a9 9 0 0118 0z" />
              <circle cx="12" cy="10" r="3" />
            </svg>
            <span className="text-xs font-medium">Navigate to customer</span>
          </button>
        </div>
      </div>

      {nextStatuses.length > 0 && (
        <div className="space-y-2">
          {nextStatuses.map((status) => (
            <button
              key={status}
              onClick={() => updateStatus(status)}
              disabled={updating}
              className="w-full btn-accent disabled:opacity-50"
            >
              {updating ? "Updating…" : `Mark as ${STATUS_LABELS[status] ?? status}`}
            </button>
          ))}
        </div>
      )}

      {delivery.status === "delivered" && (
        <div className="card p-5 text-center">
          <p className="text-success font-bold mb-1">Delivery completed</p>
          <button onClick={() => router.push("/agent")} className="btn-navy mt-2">Back to dashboard</button>
        </div>
      )}
    </div>
  );
}
