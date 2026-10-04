"use client";

import { useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { DeliveryAgent, LedgerEntry, LedgerList, PaginatedResponse } from "@/types/interface";
import { formatKES } from "@/lib/utils";

const ENTRY_STYLE: Record<string, string> = {
  earning: "bg-success/10 text-success",
  b2c_payout: "bg-danger/10 text-danger",
  reversal: "bg-info/10 text-info",
  adjustment: "bg-amber/15 text-gold",
};

const STATUS_STYLE: Record<string, string> = {
  pending: "bg-amber/15 text-gold",
  succeeded: "bg-success/10 text-success",
  failed: "bg-danger/10 text-danger",
};

const AGENTS_LIMIT = 100;

export default function AdminLedgerPage() {
  const queryClient = useQueryClient();
  const [agentId, setAgentId] = useState<string>("");
  const [amount, setAmount] = useState("");
  const [note, setNote] = useState("");
  const [paying, setPaying] = useState(false);

  const { data: agentsData, isPending: loadingAgents } = useQuery({
    queryKey: ["admin", "delivery-agents", "ledger"],
    queryFn: () =>
      fetch(`/api/admin/delivery/agents?page=1&limit=${AGENTS_LIMIT}`)
        .then((r) => r.json())
        .then((data): PaginatedResponse<DeliveryAgent> =>
          data && Array.isArray(data.results) ? data : { total: 0, page: 1, limit: AGENTS_LIMIT, results: [] }
        ),
  });
  const agents = agentsData?.results ?? [];

  const { data: ledger, isPending: loadingLedger } = useQuery({
    queryKey: ["admin", "ledger", agentId],
    queryFn: () =>
      fetch(`/api/admin/fleet/ledger?agent_id=${agentId}&limit=200`)
        .then((r) => r.json())
        .then((data): LedgerList | null =>
          data && typeof data.wallet_balance === "string" ? data : null
        ),
    enabled: agentId.length > 0,
  });
  const entries = ledger?.entries ?? [];

  async function payout(e: React.FormEvent) {
    e.preventDefault();
    if (!agentId) { toast.error("Choose a rider first"); return; }
    setPaying(true);
    try {
      const res = await fetch(`/api/admin/fleet/ledger/${agentId}/payout`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ amount, note: note || undefined }),
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) { toast.error(data.detail ?? "Could not initiate payout"); return; }
      toast.success("Payout initiated — settles when M-Pesa confirms");
      setAmount(""); setNote("");
      queryClient.invalidateQueries({ queryKey: ["admin", "ledger", agentId] });
    } finally {
      setPaying(false);
    }
  }

  async function reverse(entry: LedgerEntry) {
    if (!confirm("Reverse this payout back into the rider's wallet?")) return;
    const res = await fetch(`/api/admin/fleet/ledger/${entry.id}/reverse`, { method: "POST" });
    const data = await res.json().catch(() => ({}));
    if (!res.ok) { toast.error(data.detail ?? "Could not reverse entry"); return; }
    toast.success("Entry reversed");
    queryClient.invalidateQueries({ queryKey: ["admin", "ledger", agentId] });
  }

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold">Rider Ledger &amp; Payouts</h1>

      <div className="card p-4 space-y-4">
        <div>
          <label className="block text-sm font-medium mb-1">Rider</label>
          <select className="input-field" value={agentId} onChange={(e) => setAgentId(e.target.value)}>
            <option value="">Select rider…</option>
            {agents.map((a) => (
              <option key={a.id} value={a.id}>{a.name} ({a.email})</option>
            ))}
          </select>
          {loadingAgents && <p className="text-xs text-muted mt-1">Loading riders…</p>}
        </div>

        {agentId && (
          <div className="flex items-center gap-4 flex-wrap">
            <span className="text-sm font-medium">
              Wallet balance: {formatKES(ledger?.wallet_balance ?? "0.00")}
            </span>
            <form onSubmit={payout} className="flex items-end gap-2 flex-wrap">
              <div>
                <label className="block text-xs font-medium mb-1">Amount (KES)</label>
                <input
                  className="input-field"
                  type="number"
                  min="1"
                  step="1"
                  placeholder="e.g. 1000"
                  value={amount}
                  onChange={(e) => setAmount(e.target.value)}
                  required
                />
              </div>
              <div>
                <label className="block text-xs font-medium mb-1">Note (optional)</label>
                <input
                  className="input-field"
                  placeholder="Weekly payout"
                  value={note}
                  onChange={(e) => setNote(e.target.value)}
                />
              </div>
              <button type="submit" disabled={paying || !agentId} className="btn-accent disabled:opacity-50">
                {paying ? "Sending…" : "Send payout"}
              </button>
            </form>
          </div>
        )}
      </div>

      {!agentId ? (
        <div className="card p-10 text-center text-muted text-sm">Select a rider to view their ledger.</div>
      ) : loadingLedger ? (
        <p className="text-muted text-sm">Loading…</p>
      ) : entries.length === 0 ? (
        <div className="card p-10 text-center text-muted text-sm">No ledger entries for this rider.</div>
      ) : (
        <div className="card overflow-hidden overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-border text-left text-xs text-muted">
                <th className="px-4 py-3 font-medium">Type</th>
                <th className="px-4 py-3 font-medium">Amount</th>
                <th className="px-4 py-3 font-medium">Balance after</th>
                <th className="px-4 py-3 font-medium">Status</th>
                <th className="px-4 py-3 font-medium">Reference</th>
                <th className="px-4 py-3 font-medium">Date</th>
                <th className="px-4 py-3 font-medium"></th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border">
              {entries.map((entry) => (
                <tr key={entry.id} className="hover:bg-surface/50 transition-colors">
                  <td className="px-4 py-3">
                    <span className={`text-xs font-medium px-2 py-0.5 rounded-full capitalize ${ENTRY_STYLE[entry.entry_type] ?? "bg-ink/10 text-ink"}`}>
                      {entry.entry_type.replace("_", " ")}
                    </span>
                  </td>
                  <td className="px-4 py-3">
                    <span className={entry.amount.startsWith("-") ? "text-danger" : "text-success"}>
                      {formatKES(entry.amount)}
                    </span>
                  </td>
                  <td className="px-4 py-3 text-muted">{formatKES(entry.balance_after)}</td>
                  <td className="px-4 py-3">
                    <span className={`text-xs font-medium px-2 py-0.5 rounded-full capitalize ${STATUS_STYLE[entry.status] ?? "bg-ink/10 text-ink"}`}>
                      {entry.status}
                    </span>
                  </td>
                  <td className="px-4 py-3">
                    {entry.failure_reason ? (
                      <span className="text-xs text-danger" title={entry.failure_reason}>{entry.reference ?? "—"}</span>
                    ) : (
                      <span className="text-xs text-muted">{entry.reference ?? "—"}</span>
                    )}
                  </td>
                  <td className="px-4 py-3 text-xs text-muted">
                    {new Date(entry.created_at).toLocaleString("en-KE", {
                      day: "numeric", month: "short", year: "numeric", hour: "2-digit", minute: "2-digit",
                    })}
                  </td>
                  <td className="px-4 py-3">
                    {entry.entry_type === "b2c_payout" && entry.status === "succeeded" && (
                      <button
                        onClick={() => reverse(entry)}
                        className="text-xs py-1.5 px-3 rounded-md border border-danger text-danger hover:bg-danger/5"
                      >
                        Reverse
                      </button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}