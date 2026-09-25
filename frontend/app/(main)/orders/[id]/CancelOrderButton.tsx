"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { toast } from "sonner";

interface Props {
  orderId: string;
  status: string;
}

export default function CancelOrderButton({ orderId, status }: Props) {
  const router = useRouter();
  const [loading, setLoading] = useState(false);

  if (status !== "pending" && status !== "confirmed") return null;

  async function cancel() {
    if (!confirm("Cancel this order? This cannot be undone.")) return;
    setLoading(true);
    try {
      const res = await fetch(`/api/orders/${orderId}/cancel`, {
        method: "PATCH",
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) {
        toast.error(data.detail ?? "Could not cancel order");
        return;
      }
      toast.success("Order cancelled");
      router.refresh();
    } catch {
      toast.error("Something went wrong. Try again.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <button onClick={cancel} disabled={loading} className="text-xs py-1.5 px-3 rounded-md border border-danger text-danger hover:bg-danger/5 disabled:opacity-50">
      {loading ? "Cancelling..." : "Cancel order"}
    </button>
  );
}
