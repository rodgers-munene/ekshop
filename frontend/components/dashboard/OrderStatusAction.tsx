"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { toast } from "sonner";

const NEXT_STATUS: Record<string, string> = {
  pending: "confirmed",
  confirmed: "processing",
  processing: "shipped",
  shipped: "delivered",
};

export default function OrderStatusAction({ orderId, status }: { orderId: string; status: string }) {
  const router = useRouter();
  const [loading, setLoading] = useState(false);

  const next = NEXT_STATUS[status];
  if (!next) return null;

  async function markNext() {
    setLoading(true);
    try {
      const res = await fetch(`/api/dashboard/orders/${orderId}/status`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ status: next }),
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) {
        toast.error(data.detail ?? "Could not update order");
        return;
      }
      toast.success(`Order marked as ${next}`);
      router.refresh();
    } catch {
      toast.error("Something went wrong. Try again.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <button onClick={markNext} disabled={loading} className="btn-accent disabled:opacity-50">
      {loading ? "Updating..." : `Mark as ${next}`}
    </button>
  );
}
