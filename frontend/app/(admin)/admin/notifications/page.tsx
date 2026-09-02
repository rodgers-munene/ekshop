"use client";

import { useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { Trash2 } from "lucide-react";
import { OrderNotificationRecipient } from "@/types/interface";

export default function AdminOrderNotificationsPage() {
  const queryClient = useQueryClient();
  const [email, setEmail] = useState("");
  const [label, setLabel] = useState("");
  const [saving, setSaving] = useState(false);

  const { data: recipients, isPending: loading } = useQuery({
    queryKey: ["admin", "order-notification-recipients"],
    queryFn: () =>
      fetch("/api/admin/order-notification-recipients").then((r) => r.json()) as Promise<
        OrderNotificationRecipient[]
      >,
  });

  async function addRecipient(e: React.FormEvent) {
    e.preventDefault();
    setSaving(true);
    try {
      const res = await fetch("/api/admin/order-notification-recipients", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email, label: label || null }),
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) { toast.error(data.detail ?? "Could not add recipient"); return; }
      toast.success("Recipient added");
      setEmail("");
      setLabel("");
      queryClient.invalidateQueries({ queryKey: ["admin", "order-notification-recipients"] });
    } finally {
      setSaving(false);
    }
  }

  async function toggleActive(recipient: OrderNotificationRecipient) {
    const res = await fetch(`/api/admin/order-notification-recipients/${recipient.id}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ is_active: !recipient.is_active }),
    });
    if (!res.ok) { toast.error("Could not update recipient"); return; }
    queryClient.invalidateQueries({ queryKey: ["admin", "order-notification-recipients"] });
  }

  async function removeRecipient(id: string) {
    const res = await fetch(`/api/admin/order-notification-recipients/${id}`, { method: "DELETE" });
    if (!res.ok && res.status !== 204) { toast.error("Could not remove recipient"); return; }
    toast.success("Recipient removed");
    queryClient.invalidateQueries({ queryKey: ["admin", "order-notification-recipients"] });
  }

  return (
    <div>
      <h1 className="text-2xl font-bold mb-2">Order Notifications</h1>
      <p className="text-sm text-muted mb-6">
        Everyone listed here gets a full breakdown email — delivery fee, delivery address, buyer
        details, seller details, and per-product line items — the moment an order is paid, so they
        can start planning the delivery right away.
      </p>

      <div className="grid grid-cols-1 lg:grid-cols-[minmax(0,26rem)_1fr] gap-6 items-start">
        <form onSubmit={addRecipient} className="card p-6 space-y-4">
          <div>
            <label className="block text-sm font-medium mb-1">Email address</label>
            <input
              type="email"
              className="input-field"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="ops@ekshop.store"
              required
            />
          </div>
          <div>
            <label className="block text-sm font-medium mb-1">Label (optional)</label>
            <input
              type="text"
              className="input-field"
              value={label}
              onChange={(e) => setLabel(e.target.value)}
              placeholder="Warehouse manager"
            />
          </div>
          <button type="submit" disabled={saving} className="btn-accent disabled:opacity-50">
            {saving ? "Adding…" : "Add recipient"}
          </button>
        </form>

        <div className="card p-6">
          <h2 className="font-semibold text-sm mb-3">Recipients</h2>
          {loading ? (
            <p className="text-muted text-sm">Loading…</p>
          ) : !recipients?.length ? (
            <p className="text-muted text-sm">No recipients yet — add one to start receiving order emails.</p>
          ) : (
            <ul className="divide-y divide-border">
              {recipients.map((r) => (
                <li key={r.id} className="flex items-center justify-between gap-4 py-3">
                  <div className="min-w-0">
                    <p className="font-medium text-sm truncate">{r.email}</p>
                    {r.label && <p className="text-xs text-muted truncate">{r.label}</p>}
                  </div>
                  <div className="flex items-center gap-3 shrink-0">
                    <button
                      onClick={() => toggleActive(r)}
                      className={`relative w-11 h-6 rounded-full transition-colors ${r.is_active ? "bg-amber" : "bg-border"}`}
                      aria-pressed={r.is_active}
                      aria-label={`Toggle notifications for ${r.email}`}
                    >
                      <span
                        className={`absolute top-1 left-1 w-4 h-4 rounded-full bg-white shadow transition-transform ${
                          r.is_active ? "translate-x-5" : "translate-x-0"
                        }`}
                      />
                    </button>
                    <button
                      onClick={() => removeRecipient(r.id)}
                      className="text-muted hover:text-danger"
                      aria-label={`Remove ${r.email}`}
                    >
                      <Trash2 size={16} />
                    </button>
                  </div>
                </li>
              ))}
            </ul>
          )}
        </div>
      </div>
    </div>
  );
}
