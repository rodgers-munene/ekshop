"use client";

import { useQuery } from "@tanstack/react-query";
import ReadOnlyMap from "@/components/geo/ReadOnlyMap";

interface AgentLocation {
  id: string;
  name: string;
  status: string;
  lat: number;
  lng: number;
  last_update: string | null;
  current_order_id: string | null;
}

export default function AdminTrackingPage() {
  const { data: agents = [], isLoading, refetch } = useQuery<AgentLocation[]>({
    queryKey: ["admin", "agent-locations"],
    queryFn: () =>
      fetch("/api/admin/delivery/agents/locations")
        .then((r) => r.json())
        .catch(() => []),
    refetchInterval: 10000,
  });

  const activeAgents = agents.filter((a) => a.lat != null && a.lng != null);

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">Live fleet</h1>
          <p className="text-sm text-muted">
            {activeAgents.length} rider{activeAgents.length === 1 ? "" : "s"} online
          </p>
        </div>
        <button
          onClick={() => refetch()}
          disabled={isLoading}
          className="px-3 py-1.5 rounded-md border border-border text-sm font-medium hover:bg-ink/5"
        >
          Refresh
        </button>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <div className="lg:col-span-2 card p-4">
          <ReadOnlyMap
            lat={activeAgents[0]?.lat}
            lng={activeAgents[0]?.lng}
            height="h-[500px]"
          >
            {activeAgents.map((a) => (
              <AgentPin key={a.id} agent={a} lat={a.lat} lng={a.lng} />
            ))}
          </ReadOnlyMap>
        </div>

        <div className="space-y-3">
          {activeAgents.length === 0 ? (
            <div className="card p-6 text-center text-muted text-sm">
              No riders online right now.
            </div>
          ) : (
            activeAgents.map((a) => (
              <AgentCard key={a.id} agent={a} />
            ))
          )}
        </div>
      </div>
    </div>
  );
}

function AgentPin({ agent, lat, lng }: { agent: AgentLocation; lat: number; lng: number }) {
  return (
    <div
      className="w-8 h-8 rounded-full bg-amber flex items-center justify-center text-white text-xs font-bold shadow-lg border-2 border-white"
      style={{ transform: "translate(-50%, -50%)" }}
      title={`${agent.name} — ${agent.status}`}
    >
      {agent.name.charAt(0).toUpperCase()}
    </div>
  );
}

function AgentCard({ agent }: { agent: AgentLocation }) {
  const statusColor =
    agent.status === "active"
      ? "bg-success/10 text-success"
      : agent.status === "inactive"
      ? "bg-muted/10 text-muted"
      : "bg-amber/10 text-amber";

  return (
    <div className="card p-3">
      <div className="flex items-center justify-between">
        <p className="font-medium">{agent.name}</p>
        <span className={`text-xs font-medium px-2 py-0.5 rounded-full ${statusColor}`}>
          {agent.status}
        </span>
      </div>
      <p className="text-xs text-muted mt-1">
        {agent.last_update
          ? `Updated ${new Date(agent.last_update).toLocaleTimeString()}`
          : "No location"}
      </p>
      {agent.current_order_id && (
        <p className="text-xs text-muted mt-1">On order {agent.current_order_id.slice(0, 8)}…</p>
      )}
    </div>
  );
}