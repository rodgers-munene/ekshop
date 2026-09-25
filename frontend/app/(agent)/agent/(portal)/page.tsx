"use client";

import { useEffect, useRef, useState } from "react";
import Link from "next/link";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { Delivery, DeliveryAgent } from "@/types/interface";
import MessageAdminButton from "@/components/MessageAdminButton";

type AgentStatus = "available" | "busy" | "offline";

const STATUS_LABELS: Record<AgentStatus, string> = {
  available: "Available",
  busy: "Busy",
  offline: "Offline",
};

// Backend statuses: active (taking jobs), busy (set on assignment), inactive (offline).
const FROM_AGENT_STATUS: Record<string, AgentStatus> = {
  active: "available",
  busy: "busy",
  inactive: "offline",
};

// Send at most one GPS fix this often, so an open tab doesn't write every second.
const LOCATION_INTERVAL_MS = 30_000;

export default function AgentHomePage() {
  const queryClient = useQueryClient();
  const [loading, setLoading] = useState(false);
  const lastLocationSent = useRef(0);

  const { data: agent } = useQuery({
    queryKey: ["agent-profile"],
    queryFn: async () => {
      const res = await fetch("/api/agent/auth/status");
      if (!res.ok) throw new Error();
      return res.json() as Promise<DeliveryAgent>;
    },
    refetchInterval: 30000,
  });
  const status: AgentStatus = (agent && FROM_AGENT_STATUS[agent.status]) || "available";
  const [locationError, setLocationError] = useState<string | null>(null);

  const { data: deliveries = [] } = useQuery({
    queryKey: ["agent-deliveries"],
    queryFn: () => fetch("/api/agent/deliveries").then((r) => r.json()) as Promise<Delivery[]>,
    refetchInterval: 20000,
  });

  useEffect(() => {
    if (!navigator.geolocation) {
      setLocationError("Geolocation not supported");
      return;
    }
    const watchId = navigator.geolocation.watchPosition(
      (pos) => {
        const now = Date.now();
        if (now - lastLocationSent.current < LOCATION_INTERVAL_MS) return;
        lastLocationSent.current = now;
        fetch("/api/agent/location", {
          method: "PATCH",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ lat: pos.coords.latitude, lng: pos.coords.longitude }),
        }).catch(() => {});
      },
      () => setLocationError("Location permission denied"),
      { enableHighAccuracy: true, maximumAge: 5000, timeout: 10000 }
    );
    return () => navigator.geolocation.clearWatch(watchId);
  }, []);

  const active = deliveries.filter((d) => d.status !== "delivered" && d.status !== "cancelled");
  const completed = deliveries.filter((d) => d.status === "delivered");
  const next = active[0];

  async function toggleStatus() {
    setLoading(true);
    try {
      const goOffline = status !== "offline";
      const res = await fetch("/api/agent/auth/status", {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ status: goOffline ? "inactive" : "active" }),
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) throw new Error(typeof data.detail === "string" ? data.detail : "Could not update status");
      queryClient.setQueryData(["agent-profile"], data);
      toast.success(goOffline ? "You're now offline" : "You're now available");
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Could not update status");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div>
      <div className="flex items-start justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold">Mambo</h1>
          <p className="text-sm text-muted">
            {next ? "You have active deliveries" : "No active deliveries"}
          </p>
          {locationError && <p className="text-xs text-danger mt-1">{locationError}</p>}
        </div>
        <button
          onClick={toggleStatus}
          disabled={loading}
          className={`flex items-center gap-2 rounded-full px-4 py-2 text-sm font-medium border transition-colors disabled:opacity-50 ${
            status === "available"
              ? "border-success text-success bg-success/10"
              : "border-border text-muted bg-surface"
          }`}
        >
          <span className={`w-2 h-2 rounded-full ${status === "available" ? "bg-success" : "bg-muted"}`} />
          {STATUS_LABELS[status]}
        </button>
        <MessageAdminButton />
      </div>

      {/* Summary stats */}
      <div className="grid grid-cols-3 gap-3 mb-6">
        <div className="card p-4 text-center">
          <p className="text-2xl font-bold">{active.length}</p>
          <p className="text-xs text-muted mt-1">Active</p>
        </div>
        <div className="card p-4 text-center">
          <p className="text-2xl font-bold">{completed.length}</p>
          <p className="text-xs text-muted mt-1">Completed</p>
        </div>
        <div className="card p-4 text-center">
          <p className="text-2xl font-bold">{deliveries.length}</p>
          <p className="text-xs text-muted mt-1">Total</p>
        </div>
      </div>

      {/* Next stop */}
      {next && (
        <Link
          href={`/agent/deliveries/${next.id}`}
          className="block card p-5 mb-6 hover:border-amber transition-colors"
        >
          <div className="flex items-center justify-between mb-3">
            <span className="text-xs font-semibold text-amber uppercase tracking-wide">Next stop</span>
            <span className="text-xs text-muted">Arrive in ~25 min</span>
          </div>
          <h2 className="text-lg font-bold mb-1">
            {next.order?.buyer_name ?? "Customer"}
          </h2>
          <p className="text-sm text-muted mb-4">
            {next.order?.delivery_address?.exact_location ||
              next.order?.delivery_address?.town ||
              next.order?.delivery_address?.county}
          </p>
          <div className="flex gap-2">
            <span className="text-xs bg-surface border border-border rounded-full px-3 py-1">
              {next.tracking_number}
            </span>
            <span className="text-xs bg-surface border border-border rounded-full px-3 py-1 capitalize">
              {next.status.replace("_", " ")}
            </span>
          </div>
        </Link>
      )}

      {/* Pending deliveries */}
      <div className="flex items-center justify-between mb-3">
        <h2 className="text-sm font-bold text-muted">Pending deliveries</h2>
        <span className="text-xs text-muted">{active.length} pending</span>
      </div>

      {active.length === 0 ? (
        <div className="card flex flex-col items-center justify-center py-12 text-center">
          <p className="font-bold mb-1">No active deliveries</p>
          <p className="text-sm text-muted">New assignments will show up here.</p>
        </div>
      ) : (
        <div className="space-y-3">
          {active.map((delivery, idx) => (
            <Link
              key={delivery.id}
              href={`/agent/deliveries/${delivery.id}`}
              className="block card p-4 hover:border-amber transition-colors"
            >
              <div className="flex items-center justify-between">
              <div className="flex items-center gap-3">
                <span className="w-8 h-8 rounded-full bg-surface-2 text-muted text-xs font-bold flex items-center justify-center">
                  {idx + 1}
                </span>
                <div>
                  <p className="font-semibold text-sm">{delivery.tracking_number}</p>
                  <p className="text-xs text-muted">{delivery.order?.buyer_name}</p>
                </div>
              </div>
                <span className={`text-xs font-medium px-2 py-1 rounded-full ${
                  delivery.status === "assigned" ? "bg-info/10 text-info" :
                  delivery.status === "picked" ? "bg-amber/10 text-amber" :
                  delivery.status === "in_transit" ? "bg-amber/10 text-amber" :
                  "bg-surface text-muted"
                }`}>
                  {STATUS_LABELS[delivery.status as keyof typeof STATUS_LABELS] ?? delivery.status}
                </span>
                {delivery.distance_km != null && delivery.duration_min != null && (
                  <span className="text-xs text-muted ml-2">
                    {delivery.distance_km} km · {Math.round(delivery.duration_min)} min
                  </span>
                )}
              </div>
            </Link>
          ))}
        </div>
      )}

      {/* Delivered today */}
      {completed.length > 0 && (
        <>
          <button
            onClick={() => {}}
            className="flex items-center justify-between w-full py-3 text-sm font-medium text-muted border-t border-border mt-6"
          >
            <span>Delivered today ({completed.length})</span>
            <span>▾</span>
          </button>
          <div className="space-y-3 mt-3">
            {completed.slice(0, 5).map((delivery) => (
              <div key={delivery.id} className="card p-4 opacity-75">
                <div className="flex items-center justify-between">
                <div className="flex items-center gap-3">
                  <span className="w-8 h-8 rounded-full bg-success/20 text-success text-xs font-bold flex items-center justify-center">
                    ✓
                  </span>
                  <div>
                    <p className="font-semibold text-sm">{delivery.tracking_number}</p>
                    <p className="text-xs text-muted">{delivery.order?.buyer_name}</p>
                  </div>
                </div>
                  <span className="text-xs font-medium px-2 py-1 rounded-full bg-success/10 text-success">
                    Delivered
                  </span>
                </div>
              </div>
            ))}
          </div>
        </>
      )}
    </div>
  );
}
