"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { Delivery } from "@/types/interface";
import MessageAdminButton from "@/components/MessageAdminButton";
import {
  agentStatusLabel,
  isOnline,
  nextAgentStatus,
  statusLabel,
  statusStyle,
  type AgentStatus,
} from "@/lib/agent-status";

export default function AgentHomePage() {
  const queryClient = useQueryClient();
  const [loading, setLoading] = useState(false);
  const [locationError, setLocationError] = useState<string | null>(null);

  // The rider's real availability comes from the server. It used to be a local
  // constant, so the screen claimed "Available" regardless of what dispatch
  // actually thought. The query is the source of truth and is re-read after every
  // change, rather than mirrored into component state by an effect.
  const { data: remoteStatus } = useQuery({
    queryKey: ["agent-status"],
    queryFn: async () => {
      const res = await fetch("/api/agent/auth/status");
      if (!res.ok) throw new Error();
      return (await res.json()) as { status: AgentStatus };
    },
    refetchInterval: 30000,
  });

  const status: AgentStatus = remoteStatus?.status ?? "inactive";

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

  // This used to re-fetch the delivery list purely to set a local "busy" status
  // when anything was active. The server already reports `busy`, so the guess was
  // both redundant and wrong -- and it duplicated the request the query above
  // already makes. `active` is derived from that query instead.
  const active = deliveries.filter((d) => d.status !== "delivered" && d.status !== "cancelled");
  const completed = deliveries.filter((d) => d.status === "delivered");
  const next = active[0];

  async function toggleStatus() {
    setLoading(true);
    try {
      const newStatus = nextAgentStatus(status);
      // Was POSTing `{action:"status"}` to `/api/agent/auth`, which only handles
      // login and logout -- every toggle came back 401 and the rider could never
      // come online. It also sent "available"/"offline", which the backend's
      // DeliveryAgentStatus does not define. `PATCH /api/agent/auth/status` with
      // the real enum is the endpoint and vocabulary that exist.
      const res = await fetch("/api/agent/auth/status", {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ status: newStatus }),
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) {
        // The backend refuses to go online without approved KYC, verified
        // equipment and a shared location. Say which, rather than a generic
        // failure the rider cannot act on.
        throw new Error(data.detail ?? "Could not update status");
      }
      queryClient.invalidateQueries({ queryKey: ["agent-status"] });
      toast.success(
        newStatus === "active" ? "You're now available" : "You're now offline"
      );
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Could not update status");
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
            isOnline(status)
              ? "border-success text-success bg-success/10"
              : "border-border text-muted bg-surface"
          }`}
        >
          <span className={`w-2 h-2 rounded-full ${isOnline(status) ? "bg-success" : "bg-muted"}`} />
          {agentStatusLabel(status)}
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
            <span className="text-xs font-semibold text-gold uppercase tracking-wide">Next stop</span>
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
<span className={`text-xs font-medium px-2 py-1 rounded-full ${statusStyle(delivery.status)}`}>
                  {statusLabel(delivery.status)}
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
