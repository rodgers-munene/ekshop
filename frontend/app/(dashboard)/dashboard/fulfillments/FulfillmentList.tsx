"use client";

import { useState } from "react";
import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { Loader2, Truck } from "lucide-react";
import {
  FulfillmentListResponse,
  FulfillmentRead,
  FulfillmentStatus,
} from "@/types/interface";
import { formatKES } from "@/lib/utils";

/**
 * A merchant's fulfillments.
 *
 * Status is shown exactly as the server reports it. The backend derives it from
 * the current job rather than storing it, and recomputing it here is how a
 * merchant ends up looking at a "Delivered" badge that dispatch disagrees with.
 */

const STATUS_LABELS: Record<FulfillmentStatus, string> = {
  pending: "Preparing",
  assigned: "Rider assigned",
  picked_up: "Picked up",
  in_transit: "On the way",
  delivered: "Delivered",
  collected: "Collected",
  cancelled: "Cancelled",
  returned: "Returned",
  failed: "Needs attention",
};

const STATUS_STYLES: Record<FulfillmentStatus, string> = {
  pending: "bg-amber/15 text-amber",
  assigned: "bg-info/10 text-info",
  picked_up: "bg-info/10 text-info",
  in_transit: "bg-info/10 text-info",
  delivered: "bg-success/10 text-success",
  collected: "bg-success/10 text-success",
  cancelled: "bg-surface text-muted",
  returned: "bg-surface text-muted",
  failed: "bg-danger/10 text-danger",
};

const FILTERS: { value: string; label: string }[] = [
  { value: "", label: "All" },
  { value: "pending", label: "Preparing" },
  { value: "in_transit", label: "On the way" },
  { value: "delivered", label: "Delivered" },
  { value: "failed", label: "Needs attention" },
];

export default function FulfillmentList() {
  const [status, setStatus] = useState("");

  const { data, isLoading, isError } = useQuery({
    queryKey: ["fulfillments", status],
    queryFn: async () => {
      const query = new URLSearchParams({ page_size: "50" });
      if (status) query.set("status", status);
      const res = await fetch(`/api/fulfillments?${query}`);
      if (!res.ok) throw new Error();
      return (await res.json()) as FulfillmentListResponse;
    },
  });

  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-20">
        <Loader2 className="animate-spin text-amber" size={24} />
      </div>
    );
  }

  if (isError) {
    return (
      <div className="card flex flex-col items-center justify-center py-16 text-center">
        <p className="font-bold mb-1">Could not load deliveries</p>
        <p className="text-sm text-muted">Please refresh and try again.</p>
      </div>
    );
  }

  const items = data?.items ?? [];

  return (
    <div>
      <div className="flex flex-wrap items-center gap-2 mb-5">
        {FILTERS.map((filter) => (
          <button
            key={filter.value}
            onClick={() => setStatus(filter.value)}
            className={`text-xs px-3 py-1.5 rounded-full border transition-colors ${
              status === filter.value
                ? "bg-amber text-white border-amber"
                : "border-border hover:border-amber"
            }`}
          >
            {filter.label}
          </button>
        ))}
      </div>

      {items.length === 0 ? (
        <div className="card flex flex-col items-center justify-center py-20 text-center">
          <Truck size={28} className="text-muted mb-3" />
          <p className="font-bold mb-1">No deliveries yet</p>
          <p className="text-sm text-muted">
            Request delivery from an order to get started.
          </p>
        </div>
      ) : (
        <div className="card overflow-hidden overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-border text-left text-xs text-muted">
                <th className="px-4 py-3 font-medium">Order</th>
                <th className="px-4 py-3 font-medium">Mode</th>
                <th className="px-4 py-3 font-medium">Status</th>
                <th className="px-4 py-3 font-medium">Delivery fee</th>
                <th className="px-4 py-3 font-medium"></th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border">
              {items.map((f) => (
                <FulfillmentRow key={f.id} fulfillment={f} />
              ))}
            </tbody>
          </table>
        </div>
      )}

      {data && data.total > items.length && (
        <p className="text-xs text-muted mt-3">
          Showing {items.length} of {data.total}.
        </p>
      )}
    </div>
  );
}

function FulfillmentRow({ fulfillment: f }: { fulfillment: FulfillmentRead }) {
  // `delivery_price_gross` is what the delivery costs to serve.
  // `customer_payment` is what the buyer hands over after any subsidy. Showing
  // only the second would make a fully-subsidised delivery look like free
  // revenue, which is exactly backwards.
  const gross = f.delivery_price_gross ?? f.quoted_fee;
  const customerPays = f.customer_payment;
  const subsidised =
    gross != null && customerPays != null && customerPays !== gross;

  return (
    <tr>
      <td className="px-4 py-3 font-mono text-xs">
        #{f.order_id.slice(0, 8).toUpperCase()}
      </td>
      <td className="px-4 py-3 capitalize">{f.mode}</td>
      <td className="px-4 py-3">
        <span
          className={`text-xs font-medium px-2 py-1 rounded-full ${
            STATUS_STYLES[f.status] ?? "bg-surface text-muted"
          }`}
        >
          {STATUS_LABELS[f.status] ?? f.status}
        </span>
      </td>
      <td className="px-4 py-3">
        {gross != null ? (
          <>
            <span className="font-medium">{formatKES(gross)}</span>
            {subsidised && (
              <span className="block text-xs text-muted">
                Customer pays {formatKES(customerPays!)}
              </span>
            )}
          </>
        ) : (
          <span className="text-muted">Not quoted</span>
        )}
      </td>
      <td className="px-4 py-3 text-right">
        <Link
          href={`/dashboard/fulfillments/${f.id}`}
          className="text-amber text-sm underline underline-offset-2"
        >
          Manage
        </Link>
      </td>
    </tr>
  );
}