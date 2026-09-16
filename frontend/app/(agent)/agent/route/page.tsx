"use client";

import { useQuery } from "@tanstack/react-query";
import { Delivery } from "@/types/interface";

export default function AgentRoutePage() {
  const { data: deliveries = [], isLoading } = useQuery({
    queryKey: ["agent-deliveries"],
    queryFn: () => fetch("/api/agent/deliveries").then((r) => r.json()) as Promise<Delivery[]>,
    refetchInterval: 20000,
  });

  const pending = deliveries.filter((d) => d.status !== "delivered" && d.status !== "cancelled");
  const completed = deliveries.filter((d) => d.status === "delivered");

  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-20">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-amber" />
      </div>
    );
  }

  return (
    <div>
      <h1 className="text-2xl font-bold mb-6">Route</h1>
      <p className="text-sm text-muted mb-6">Suggested order for today&apos;s stops</p>

      {pending.length === 0 && completed.length === 0 ? (
        <div className="card flex flex-col items-center justify-center py-20 text-center">
          <p className="font-bold mb-1">No stops yet</p>
          <p className="text-sm text-muted">Assigned deliveries will appear here.</p>
        </div>
      ) : (
        <div className="space-y-0">
          {completed.map((delivery, idx) => (
            <div key={delivery.id} className="flex gap-4 py-4">
              <div className="flex flex-col items-center">
                <div className="w-8 h-8 rounded-full bg-success/20 text-success text-xs font-bold flex items-center justify-center">
                  ✓
                </div>
                {idx < completed.length - 1 && <div className="w-0.5 flex-1 bg-border mt-2" />}
              </div>
              <div className="pb-4">
                <p className="font-semibold text-sm">{delivery.order?.buyer_name}</p>
                <p className="text-xs text-muted mt-0.5">
                  {delivery.order?.delivery_address?.exact_location ||
                    delivery.order?.delivery_address?.town ||
                    delivery.order?.delivery_address?.county}
                </p>
                <p className="text-xs text-muted mt-1">Delivered</p>
              </div>
            </div>
          ))}

          {pending.map((delivery, idx) => (
            <div key={delivery.id} className="flex gap-4 py-4">
              <div className="flex flex-col items-center">
                <div className="w-8 h-8 rounded-full bg-surface-2 border-2 border-amber text-amber text-xs font-bold flex items-center justify-center">
                  {idx + 1}
                </div>
                {idx < pending.length - 1 && <div className="w-0.5 flex-1 bg-border mt-2" />}
              </div>
              <div className="pb-4 flex-1">
                <p className="font-semibold text-sm">{delivery.order?.buyer_name}</p>
                <p className="text-xs text-muted mt-0.5">
                  {delivery.order?.delivery_address?.exact_location ||
                    delivery.order?.delivery_address?.town ||
                    delivery.order?.delivery_address?.county}
                </p>
                <p className="text-xs text-muted mt-1 capitalize">
                  {delivery.status.replace("_", " ")}
                </p>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
