"use client";

import { useState } from "react";
import Link from "next/link";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { DeliveryRates } from "@/types/interface";

const FIELDS: { key: keyof Omit<DeliveryRates, "id" | "updated_at" | "use_geo_pricing">; label: string; hint: string }[] = [
  { key: "same_county_fee", label: "Same county", hint: "Buyer and vendor are in the same county" },
  { key: "same_region_fee", label: "Same region", hint: "Different county, but a neighboring cluster (e.g. Nairobi Metro)" },
  { key: "different_region_fee", label: "Different region", hint: "Buyer and vendor are in unrelated parts of the country" },
  { key: "unknown_origin_fee", label: "Unknown vendor location", hint: "Fallback when a shop hasn't set its county" },
];

export default function AdminDeliveryRatesPage() {
  const queryClient = useQueryClient();
  const [draftOverride, setDraftOverride] = useState<Record<string, string> | null>(null);
  const [saving, setSaving] = useState(false);
  const [togglingLive, setTogglingLive] = useState(false);

  const { data: rates, isPending: loading } = useQuery({
    queryKey: ["admin", "delivery-rates"],
    queryFn: () => fetch("/api/admin/delivery/rates").then((r) => r.json()) as Promise<DeliveryRates>,
  });

  const draft: Record<string, string> = draftOverride ?? (rates
    ? {
        same_county_fee: rates.same_county_fee,
        same_region_fee: rates.same_region_fee,
        different_region_fee: rates.different_region_fee,
        unknown_origin_fee: rates.unknown_origin_fee,
      }
    : {});

  function setField(key: string, value: string) {
    setDraftOverride({ ...draft, [key]: value });
  }

  async function save(e: React.FormEvent) {
    e.preventDefault();
    setSaving(true);
    try {
      const res = await fetch("/api/admin/delivery/rates", {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(draft),
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) { toast.error(data.detail ?? "Could not save rates"); return; }
      toast.success("Delivery rates updated");
      queryClient.invalidateQueries({ queryKey: ["admin", "delivery-rates"] });
    } finally {
      setSaving(false);
    }
  }

  async function toggleLive(useGeo: boolean) {
    setTogglingLive(true);
    try {
      const res = await fetch("/api/admin/delivery/rates", {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ use_geo_pricing: useGeo }),
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) { toast.error(data.detail ?? "Could not switch pricing model"); return; }
      toast.success(useGeo ? "County/region pricing is now live at checkout" : "Reverted to cart-total pricing");
      queryClient.invalidateQueries({ queryKey: ["admin", "delivery-rates"] });
    } finally {
      setTogglingLive(false);
    }
  }

  return (
    <div>
      <h1 className="text-2xl font-bold mb-2">Delivery Rates</h1>
      <p className="text-sm text-muted mb-6">
        Flat KES delivery fees, chosen by comparing the buyer&apos;s delivery county against the vendor&apos;s
        shop county. Applied per-vendor at checkout, so a cart split across multiple sellers charges each
        seller&apos;s own delivery fee independently.
      </p>

      {loading ? (
        <p className="text-muted text-sm">Loading…</p>
      ) : (
        <>
          <div className="card p-6 max-w-xl mb-6">
            <div className="flex items-start justify-between gap-4">
              <div>
                <h2 className="font-semibold text-sm mb-1">Use county/region pricing</h2>
                <p className="text-xs text-muted">
                  {rates?.use_geo_pricing
                    ? "Live: checkout charges buyers based on distance from the seller's county."
                    : "Off: checkout still uses the legacy cart-total-tiered fee, same for every seller."}{" "}
                  Test it first in the{" "}
                  <Link href="/admin/delivery-rates/simulate" className="underline hover:text-amber">
                    Delivery Fee Simulator
                  </Link>.
                </p>
              </div>
              <button
                onClick={() => toggleLive(!rates?.use_geo_pricing)}
                disabled={togglingLive}
                className={`shrink-0 relative w-12 h-7 rounded-full transition-colors disabled:opacity-50 ${
                  rates?.use_geo_pricing ? "bg-amber" : "bg-border"
                }`}
                aria-pressed={!!rates?.use_geo_pricing}
                aria-label="Toggle county/region delivery pricing"
              >
                <span
                  className={`absolute top-1 w-5 h-5 rounded-full bg-white shadow transition-transform ${
                    rates?.use_geo_pricing ? "translate-x-6" : "translate-x-1"
                  }`}
                />
              </button>
            </div>
          </div>

          <form onSubmit={save} className="card p-6 max-w-xl space-y-4">
            {FIELDS.map(({ key, label, hint }) => (
              <div key={key}>
                <label className="block text-sm font-medium mb-1">{label}</label>
                <p className="text-xs text-muted mb-1.5">{hint}</p>
                <div className="flex items-center gap-2">
                  <span className="text-sm text-muted">KES</span>
                  <input
                    type="number"
                    min="0"
                    step="1"
                    className="input-field"
                    value={draft[key] ?? ""}
                    onChange={(e) => setField(key, e.target.value)}
                    required
                  />
                </div>
              </div>
            ))}
            <button type="submit" disabled={saving} className="btn-accent disabled:opacity-50">
              {saving ? "Saving…" : "Save rates"}
            </button>
          </form>
        </>
      )}
    </div>
  );
}
