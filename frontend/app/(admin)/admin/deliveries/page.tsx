"use client";

import { useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { PaginatedResponse, DeliveryAgent, Order } from "@/types/interface";
import { formatKES } from "@/lib/utils";
import Pagination from "@/components/admin/Pagination";

const LIMIT = 20;

export default function AdminDeliveriesPage() {
  const queryClient = useQueryClient();
  const [selectedAgent, setSelectedAgent] = useState<Record<string, string>>({});
  const [agentsPage, setAgentsPage] = useState(1);
  const [ordersPage, setOrdersPage] = useState(1);

  const [agentName, setAgentName] = useState("");
  const [agentEmail, setAgentEmail] = useState("");
  const [agentPhone, setAgentPhone] = useState("");
  const [agentPassword, setAgentPassword] = useState("");
  const [creatingAgent, setCreatingAgent] = useState(false);

  const { data: agentsData, isPending: loadingAgents } = useQuery({
    queryKey: ["admin", "delivery-agents", agentsPage],
    queryFn: () =>
      fetch(`/api/admin/delivery/agents?page=${agentsPage}&limit=${LIMIT}`)
        .then((r) => r.json())
        .then((data): PaginatedResponse<DeliveryAgent> =>
          data && Array.isArray(data.results) ? data : { total: 0, page: 1, limit: LIMIT, results: [] }
        ),
  });
  const agents = agentsData?.results ?? [];
  const agentsTotalPages = Math.max(1, Math.ceil((agentsData?.total ?? 0) / LIMIT));

  const { data: ordersData, isPending: loadingOrders } = useQuery({
    queryKey: ["admin", "orders-needing-delivery", ordersPage],
    queryFn: () =>
      fetch(`/api/admin/orders-needing-delivery?page=${ordersPage}&limit=${LIMIT}`)
        .then((r) => r.json())
        .then((data): PaginatedResponse<Order> =>
          data && Array.isArray(data.results) ? data : { total: 0, page: 1, limit: LIMIT, results: [] }
        ),
  });
  const orders = ordersData?.results ?? [];
  const ordersTotalPages = Math.max(1, Math.ceil((ordersData?.total ?? 0) / LIMIT));

  const loading = loadingAgents || loadingOrders;

  async function createAgent(e: React.FormEvent) {
    e.preventDefault();
    setCreatingAgent(true);
    try {
      const res = await fetch("/api/admin/delivery/agents", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name: agentName, email: agentEmail, phone: agentPhone, password: agentPassword }),
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) { toast.error(data.detail ?? "Could not create agent"); return; }
      toast.success("Delivery agent created");
      setAgentName(""); setAgentEmail(""); setAgentPhone(""); setAgentPassword("");
      queryClient.invalidateQueries({ queryKey: ["admin", "delivery-agents"] });
    } finally {
      setCreatingAgent(false);
    }
  }

  async function assign(orderId: string) {
    const agentId = selectedAgent[orderId];
    if (!agentId) { toast.error("Choose an agent first"); return; }
    const res = await fetch(`/api/admin/delivery/${orderId}/assign`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ agent_id: agentId }),
    });
    const data = await res.json().catch(() => ({}));
    if (!res.ok) { toast.error(data.detail ?? "Could not assign delivery"); return; }
    toast.success("Delivery assigned");
    queryClient.invalidateQueries({ queryKey: ["admin", "orders-needing-delivery"] });
  }

  return (
    <div className="space-y-8">
      <div>
        <h1 className="text-2xl font-bold mb-4">Deliveries</h1>
        <h2 className="font-semibold mb-3">Orders awaiting assignment</h2>
        {loading ? (
          <p className="text-muted text-sm">Loading…</p>
        ) : orders.length === 0 ? (
          <div className="card p-8 text-center text-muted text-sm">No orders need a delivery agent right now.</div>
        ) : (
          <div className="card divide-y divide-border overflow-hidden">
            {orders.map((order) => (
              <div key={order.id} className="flex items-center justify-between gap-4 p-4 flex-wrap">
                <div>
                  <p className="font-medium">Order #{order.id.slice(0, 8).toUpperCase()}</p>
                  <p className="text-xs text-muted">{formatKES(order.total)} · {order.status}</p>
                </div>
                <div className="flex gap-2 shrink-0">
                  <select
                    className="input-field text-sm py-1.5"
                    value={selectedAgent[order.id] ?? ""}
                    onChange={(e) => setSelectedAgent((s) => ({ ...s, [order.id]: e.target.value }))}
                  >
                    <option value="">Choose agent…</option>
                    {agents.filter((a) => a.status !== "inactive").map((a) => (
                      <option key={a.id} value={a.id}>{a.name} ({a.status})</option>
                    ))}
                  </select>
                  <button onClick={() => assign(order.id)} className="btn-accent text-xs py-1.5 px-3">
                    Assign
                  </button>
                </div>
              </div>
            ))}
          </div>
        )}
        <Pagination page={ordersPage} totalPages={ordersTotalPages} onPageChange={setOrdersPage} />
      </div>

      <div>
        <h2 className="font-semibold mb-3">Delivery agents</h2>
        <form onSubmit={createAgent} className="card p-4 grid grid-cols-2 md:grid-cols-4 gap-2 mb-4">
          <input className="input-field" placeholder="Name" value={agentName} onChange={(e) => setAgentName(e.target.value)} required />
          <input className="input-field" placeholder="Email" type="email" value={agentEmail} onChange={(e) => setAgentEmail(e.target.value)} required />
          <input className="input-field" placeholder="Phone" value={agentPhone} onChange={(e) => setAgentPhone(e.target.value)} required />
          <input className="input-field" placeholder="Password" type="password" value={agentPassword} onChange={(e) => setAgentPassword(e.target.value)} required />
          <button type="submit" disabled={creatingAgent} className="btn-navy col-span-2 md:col-span-4 disabled:opacity-50">
            {creatingAgent ? "Adding…" : "Add delivery agent"}
          </button>
        </form>

        {agents.length === 0 ? (
          <div className="card p-8 text-center text-muted text-sm">No delivery agents yet.</div>
        ) : (
          <div className="card divide-y divide-border overflow-hidden">
            {agents.map((a) => (
              <div key={a.id} className="flex items-center justify-between gap-4 p-4">
                <div>
                  <p className="font-medium">{a.name}</p>
                  <p className="text-xs text-muted">{a.email} · {a.phone}</p>
                </div>
                <div className="text-right text-xs text-muted">
                  <p className="capitalize">{a.status}</p>
                  <p>{a.total_deliveries} deliveries</p>
                </div>
              </div>
            ))}
          </div>
        )}
        <Pagination page={agentsPage} totalPages={agentsTotalPages} onPageChange={setAgentsPage} />
      </div>
    </div>
  );
}
