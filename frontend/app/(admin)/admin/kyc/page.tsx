"use client";

import { useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { KYCAgent, KYCAgentList } from "@/types/interface";
import { formatKES } from "@/lib/utils";

type Filter = "pending_review" | "approved" | "rejected";

const FILTERS: { key: Filter; label: string }[] = [
  { key: "pending_review", label: "Pending" },
  { key: "approved", label: "Approved" },
  { key: "rejected", label: "Rejected" },
];

const STATUS_STYLE: Record<string, string> = {
  pending_review: "bg-amber/15 text-gold",
  approved: "bg-success/10 text-success",
  rejected: "bg-danger/10 text-danger",
};

export default function AdminKycPage() {
  const queryClient = useQueryClient();
  const [filter, setFilter] = useState<Filter>("pending_review");

  const { data, isPending: loading } = useQuery({
    queryKey: ["admin", "kyc", filter],
    queryFn: () =>
      fetch(`/api/admin/fleet/kyc?status=${filter}`)
        .then((r) => r.json())
        .then((data): KYCAgentList =>
          data && Array.isArray(data.results) ? data : { total: 0, pending: 0, results: [] }
        ),
  });
  const agents = data?.results ?? [];

  function refresh() {
    queryClient.invalidateQueries({ queryKey: ["admin", "kyc"] });
  }

  async function approve(agent: KYCAgent) {
    const res = await fetch(`/api/admin/fleet/kyc/${agent.id}/approve`, { method: "POST" });
    const body = await res.json().catch(() => ({}));
    if (!res.ok) { toast.error(body.detail ?? "Could not approve KYC"); return; }
    toast.success(`${agent.name} approved`);
    refresh();
  }

  async function reject(agent: KYCAgent) {
    const notes = window.prompt(`Rejection reason for ${agent.name}:`, "Identity or equipment could not be verified");
    if (notes === null) return;
    const res = await fetch(`/api/admin/fleet/kyc/${agent.id}/reject`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ notes: notes || "Rejected by admin" }),
    });
    const body = await res.json().catch(() => ({}));
    if (!res.ok) { toast.error(body.detail ?? "Could not reject KYC"); return; }
    toast.success(`${agent.name} rejected`);
    refresh();
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold">Rider KYC Review</h1>
        {data && data.pending > 0 && (
          <span className="text-xs font-medium px-2 py-1 rounded-full bg-amber/15 text-gold">
            {data.pending} pending
          </span>
        )}
      </div>

      <div className="flex gap-2">
        {FILTERS.map(({ key, label }) => (
          <button
            key={key}
            onClick={() => setFilter(key)}
            className={`rounded-full text-xs font-medium px-4 py-1.5 capitalize transition-colors ${
              filter === key ? "bg-navy text-white" : "bg-surface text-muted hover:bg-ink/10"
            }`}
          >
            {label}
          </button>
        ))}
      </div>

      {loading ? (
        <p className="text-muted text-sm">Loading…</p>
      ) : agents.length === 0 ? (
        <div className="card p-10 text-center text-muted text-sm">No riders here.</div>
      ) : (
        <div className="card divide-y divide-border overflow-hidden">
          {agents.map((a) => (
            <div key={a.id} className="flex items-center justify-between gap-4 p-4 flex-wrap">
              <div className="min-w-0">
                <p className="font-medium">{a.name}</p>
                <p className="text-xs text-muted truncate">
                  {a.email} · {a.phone}
                </p>
                <div className="flex items-center gap-2 mt-1 flex-wrap">
                  <span className={`text-xs font-medium px-2 py-0.5 rounded-full capitalize ${STATUS_STYLE[a.kyc_status] ?? "bg-ink/10 text-ink"}`}>
                    {a.kyc_status.replace("_", " ")}
                  </span>
                  {a.vehicle_type && (
                    <span className="text-xs text-muted capitalize">{a.vehicle_type}</span>
                  )}
                  <span className={`text-xs font-medium px-2 py-0.5 rounded-full ${a.equipment_verified ? "bg-success/10 text-success" : "bg-ink/10 text-ink"}`}>
                    {a.equipment_verified ? "equipment verified" : "equipment not verified"}
                  </span>
                  <span className="text-xs text-muted">Wallet {formatKES(Number(a.wallet_balance))}</span>
                </div>
              </div>
              <div className="flex gap-2 shrink-0">
                <button onClick={() => approve(a)} className="btn-accent text-xs py-1.5 px-3">
                  Approve
                </button>
                <button
                  onClick={() => reject(a)}
                  className="text-xs py-1.5 px-3 rounded-md border border-danger text-danger hover:bg-danger/5"
                >
                  Reject
                </button>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}