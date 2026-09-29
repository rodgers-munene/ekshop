"use client";

import { useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { DeliveryPricingRule } from "@/types/interface";
import { formatKES } from "@/lib/utils";

const NUMERIC_FIELDS: { key: string; label: string; step: string }[] = [
  { key: "base_fare", label: "Base fare (KES)", step: "0.01" },
  { key: "per_km_rate", label: "Per km (KES)", step: "0.01" },
  { key: "per_minute_rate", label: "Per minute (KES)", step: "0.01" },
  { key: "rain_multiplier", label: "Rain ×", step: "0.05" },
  { key: "peak_hours_multiplier", label: "Peak hours ×", step: "0.05" },
  { key: "supply_demand_multiplier", label: "Supply/demand ×", step: "0.05" },
  { key: "max_surge_cap", label: "Surge cap ×", step: "0.05" },
];

export default function AdminPricingRulesPage() {
  const queryClient = useQueryClient();
  const [editing, setEditing] = useState<DeliveryPricingRule | null>(null);
  const [form, setForm] = useState<Record<string, string>>({});
  const [saving, setSaving] = useState(false);

  const { data, isPending: loading } = useQuery({
    queryKey: ["admin", "pricing-rules"],
    queryFn: () =>
      fetch("/api/admin/fleet/pricing")
        .then((r) => r.json())
        .then((data): { results: DeliveryPricingRule[] } =>
          data && Array.isArray(data.results) ? data : { results: [] }
        ),
  });
  const rules = data?.results ?? [];

  function openEditor(rule: DeliveryPricingRule) {
    const initial: Record<string, string> = {};
    for (const { key } of NUMERIC_FIELDS) initial[key] = rule[key as keyof DeliveryPricingRule] as string;
    initial.currency = rule.currency;
    setForm(initial);
    setEditing(rule);
  }

  async function save(e: React.FormEvent) {
    e.preventDefault();
    if (!editing) return;
    setSaving(true);
    try {
      const body: Record<string, string | boolean> = {
        vehicle_type: editing.vehicle_type,
        is_active: editing.is_active,
        currency: form.currency ?? "KES",
      };
      for (const { key } of NUMERIC_FIELDS) body[key] = form[key] ?? "";
      const res = await fetch(`/api/admin/fleet/pricing/${editing.vehicle_type}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) { toast.error(data.detail ?? "Could not save pricing rule"); return; }
      toast.success("Pricing rule saved");
      setEditing(null);
      queryClient.invalidateQueries({ queryKey: ["admin", "pricing-rules"] });
    } finally {
      setSaving(false);
    }
  }

  async function toggleActive(rule: DeliveryPricingRule) {
    const body = {
      vehicle_type: rule.vehicle_type,
      base_fare: rule.base_fare,
      per_km_rate: rule.per_km_rate,
      per_minute_rate: rule.per_minute_rate,
      rain_multiplier: rule.rain_multiplier,
      peak_hours_multiplier: rule.peak_hours_multiplier,
      supply_demand_multiplier: rule.supply_demand_multiplier,
      max_surge_cap: rule.max_surge_cap,
      currency: rule.currency,
      is_active: !rule.is_active,
    };
    const res = await fetch(`/api/admin/fleet/pricing/${rule.vehicle_type}`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    const data = await res.json().catch(() => ({}));
    if (!res.ok) { toast.error(data.detail ?? "Could not toggle pricing rule"); return; }
    toast.success(rule.is_active ? "Rule paused" : "Rule active");
    queryClient.invalidateQueries({ queryKey: ["admin", "pricing-rules"] });
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold">Metered Delivery Pricing</h1>
        <p className="text-sm text-muted mt-1">
          Distance-based delivery fees per vehicle. The final multiplier is capped at the surge cap
          (peak × rain × supply/demand). Rain auto-detects via OpenWeather during quotes.
        </p>
      </div>

      {loading ? (
        <p className="text-muted text-sm">Loading…</p>
      ) : rules.length === 0 ? (
        <div className="card p-10 text-center text-muted text-sm">No pricing rules configured.</div>
      ) : (
        <div className="card overflow-hidden overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-border text-left text-xs text-muted">
                <th className="px-4 py-3 font-medium">Vehicle</th>
                <th className="px-4 py-3 font-medium">Base</th>
                <th className="px-4 py-3 font-medium">Per km</th>
                <th className="px-4 py-3 font-medium">Per min</th>
                <th className="px-4 py-3 font-medium">Rain ×</th>
                <th className="px-4 py-3 font-medium">Peak ×</th>
                <th className="px-4 py-3 font-medium">Supply ×</th>
                <th className="px-4 py-3 font-medium">Cap ×</th>
                <th className="px-4 py-3 font-medium">Status</th>
                <th className="px-4 py-3 font-medium"></th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border">
              {rules.map((rule) => (
                <tr key={rule.id} className="hover:bg-surface/50 transition-colors">
                  <td className="px-4 py-3 font-medium capitalize">{rule.vehicle_type.replace("_", " ")}</td>
                  <td className="px-4 py-3">{formatKES(rule.base_fare)}</td>
                  <td className="px-4 py-3">{formatKES(rule.per_km_rate)}</td>
                  <td className="px-4 py-3">{formatKES(rule.per_minute_rate)}</td>
                  <td className="px-4 py-3">{rule.rain_multiplier}</td>
                  <td className="px-4 py-3">{rule.peak_hours_multiplier}</td>
                  <td className="px-4 py-3">{rule.supply_demand_multiplier}</td>
                  <td className="px-4 py-3">{rule.max_surge_cap}</td>
                  <td className="px-4 py-3">
                    <span className={`text-xs font-medium px-2 py-0.5 rounded-full capitalize ${rule.is_active ? "bg-success/10 text-success" : "bg-ink/10 text-ink"}`}>
                      {rule.is_active ? "active" : "paused"}
                    </span>
                  </td>
                  <td className="px-4 py-3">
                    <div className="flex gap-2">
                      <button onClick={() => openEditor(rule)} className="btn-outline text-xs py-1.5 px-3">
                        Edit
                      </button>
                      <button
                        onClick={() => toggleActive(rule)}
                        className="text-xs py-1.5 px-3 rounded-md border border-border text-muted hover:bg-ink/5"
                      >
                        {rule.is_active ? "Pause" : "Activate"}
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {editing && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4">
          <form onSubmit={save} className="card w-full max-w-md p-6 space-y-4 max-h-[90vh] overflow-y-auto">
            <div className="flex items-center justify-between">
              <h2 className="font-semibold capitalize">Edit {editing.vehicle_type.replace("_", " ")} pricing</h2>
              <button type="button" onClick={() => setEditing(null)} className="text-muted hover:text-ink" aria-label="Close">
                ✕
              </button>
            </div>
            {NUMERIC_FIELDS.map(({ key, label, step }) => (
              <div key={key}>
                <label className="block text-sm font-medium mb-1">{label}</label>
                <input
                  className="input-field"
                  type="number"
                  step={step}
                  min="0"
                  value={form[key] ?? ""}
                  onChange={(e) => setForm((f) => ({ ...f, [key]: e.target.value }))}
                  required
                />
              </div>
            ))}
            <div>
              <label className="block text-sm font-medium mb-1">Currency</label>
              <input
                className="input-field"
                value={form.currency ?? "KES"}
                onChange={(e) => setForm((f) => ({ ...f, currency: e.target.value.toUpperCase() }))}
                maxLength={3}
                required
              />
            </div>
            <div className="flex gap-2 pt-2">
              <button type="submit" disabled={saving} className="btn-accent disabled:opacity-50">
                {saving ? "Saving…" : "Save rule"}
              </button>
              <button type="button" onClick={() => setEditing(null)} className="btn-outline">
                Cancel
              </button>
            </div>
          </form>
        </div>
      )}
    </div>
  );
}