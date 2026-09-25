"use client";

import { useQuery } from "@tanstack/react-query";
import { Delivery } from "@/types/interface";

interface RouteStop {
  delivery_id: string;
  tracking_number: string;
  buyer_name: string;
  address: string;
  lat?: number;
  lng?: number;
  distance_from_previous_km?: number;
  duration_from_previous_min?: number;
}

interface RouteOptimizationResponse {
  origin_lat?: number;
  origin_lng?: number;
  total_distance_km?: number;
  total_duration_min?: number;
  stops: RouteStop[];
}

export default function AgentRoutePage() {
  const { data: deliveries = [], isLoading } = useQuery({
    queryKey: ["agent-deliveries"],
    queryFn: () => fetch("/api/agent/deliveries").then((r) => r.json()) as Promise<Delivery[]>,
    refetchInterval: 20000,
  });

  const pending = deliveries.filter((d) => d.status !== "delivered" && d.status !== "cancelled");

  const { data: route } = useQuery({
    queryKey: ["agent-route", pending.map((d) => d.id)],
    queryFn: async () => {
      if (pending.length < 2) return null;
      const res = await fetch("/api/agent/route/optimize", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ delivery_ids: pending.map((d) => d.id) }),
      });
      if (!res.ok) return null;
      return res.json() as Promise<RouteOptimizationResponse>;
    },
    enabled: pending.length >= 2,
  });

  const stops: RouteStop[] = route?.stops ?? pending.map((d) => ({
    delivery_id: d.id,
    tracking_number: d.tracking_number ?? "",
    buyer_name: d.order?.buyer_name ?? "Customer",
    address: [d.order?.delivery_address?.exact_location, d.order?.delivery_address?.town, d.order?.delivery_address?.county].filter(Boolean).join(", "),
  }));
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
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold">Route</h1>
          <p className="text-sm text-muted">Suggested order for today&apos;s stops</p>
        </div>
        {route && (
          <div className="text-xs text-muted">
            {route.total_distance_km != null ? `${route.total_distance_km.toFixed(1)} km` : ""}
            {route.total_duration_min != null ? ` · ${Math.round(route.total_duration_min)} min` : ""}
          </div>
        )}
      </div>

      {stops.length === 0 && completed.length === 0 ? (
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

          {stops.map((stop, idx) => (
            <div key={stop.delivery_id ?? idx} className="flex gap-4 py-4">
              <div className="flex flex-col items-center">
                <div className="w-8 h-8 rounded-full bg-surface-2 border-2 border-amber text-amber text-xs font-bold flex items-center justify-center">
                  {idx + 1}
                </div>
                {idx < stops.length - 1 && <div className="w-0.5 flex-1 bg-border mt-2" />}
              </div>
              <div className="pb-4 flex-1">
                <p className="font-semibold text-sm">{stop.buyer_name}</p>
                <p className="text-xs text-muted mt-0.5">{stop.address}</p>
                <div className="flex items-center gap-2 mt-1">
                  {stop.distance_from_previous_km != null && (
                    <span className="text-xs text-muted">{stop.distance_from_previous_km.toFixed(1)} km</span>
                  )}
                  {stop.duration_from_previous_min != null && (
                    <span className="text-xs text-muted">· {Math.round(stop.duration_from_previous_min)} min</span>
                  )}
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
