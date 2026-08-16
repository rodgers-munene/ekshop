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

// Mirrors backend/app/services/delivery_pricing.py COUNTY_REGIONS — these are
// logistics clusters built around real courier routes, not official provinces.
const REGIONS: { name: string; counties: string[] }[] = [
  { name: "Nairobi Metro", counties: ["Nairobi", "Kiambu", "Machakos", "Kajiado", "Murang'a"] },
  { name: "Central", counties: ["Nyeri", "Nyandarua", "Kirinyaga"] },
  { name: "Coast", counties: ["Mombasa", "Kwale", "Kilifi", "Tana River", "Lamu", "Taita Taveta"] },
  {
    name: "Rift Valley North",
    counties: [
      "Nakuru", "Baringo", "Laikipia", "Nandi", "Uasin Gishu",
      "Trans Nzoia", "Elgeyo Marakwet", "West Pokot", "Samburu", "Turkana",
    ],
  },
  { name: "Rift Valley South", counties: ["Kericho", "Bomet", "Narok"] },
  { name: "Western", counties: ["Kakamega", "Bungoma", "Busia", "Vihiga"] },
  { name: "Nyanza", counties: ["Kisumu", "Siaya", "Homa Bay", "Migori", "Kisii", "Nyamira"] },
  { name: "Eastern", counties: ["Embu", "Kitui", "Meru", "Tharaka-Nithi", "Isiolo"] },
  { name: "North Eastern", counties: ["Garissa", "Wajir", "Mandera"] },
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

      <div className="grid grid-cols-1 lg:grid-cols-[minmax(0,26rem)_1fr] gap-6 items-start">
        <div>
          {loading ? (
            <p className="text-muted text-sm">Loading…</p>
          ) : (
            <>
              <div className="card p-6 mb-6">
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
                      className={`absolute top-1 left-1 w-5 h-5 rounded-full bg-white shadow transition-transform ${
                        rates?.use_geo_pricing ? "translate-x-5" : "translate-x-0"
                      }`}
                    />
                  </button>
                </div>
              </div>

              <form onSubmit={save} className="card p-6 space-y-4">
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

        <div className="card p-6">
          <h2 className="font-semibold text-sm mb-3">How the multi-region algorithm works</h2>
          <p className="text-sm text-muted mb-4">
            45 of Kenya&apos;s 47 counties are grouped into 9 logistics regions below, built around
            real courier routes rather than official provinces. Every delivery fee comes down to
            comparing the buyer&apos;s county against the seller&apos;s shop county:
          </p>

          <ol className="space-y-2.5 text-sm mb-5">
            <li className="flex gap-2">
              <span className="font-semibold text-amber shrink-0">1.</span>
              <span><span className="font-medium">Same county</span>: buyer and shop are in the exact same county. Cheapest tier.</span>
            </li>
            <li className="flex gap-2">
              <span className="font-semibold text-amber shrink-0">2.</span>
              <span><span className="font-medium">Same region</span>: different county, but both fall in the same logistics cluster below.</span>
            </li>
            <li className="flex gap-2">
              <span className="font-semibold text-amber shrink-0">3.</span>
              <span><span className="font-medium">Different region</span>: buyer and shop are in unrelated parts of the country. Most expensive tier.</span>
            </li>
            <li className="flex gap-2">
              <span className="font-semibold text-amber shrink-0">4.</span>
              <span><span className="font-medium">Unknown origin</span>: fallback when the shop hasn&apos;t set a county at all.</span>
            </li>
          </ol>

          <div className="rounded-lg bg-surface p-4 text-sm mb-5">
            <p className="font-medium mb-1.5">Worked example</p>
            <p className="text-muted">
              A shop is based in <span className="text-ink font-medium">Nyeri</span> (region: Central).
            </p>
            <ul className="mt-1.5 space-y-1 text-muted list-disc list-inside">
              <li>Buyer also in <span className="text-ink font-medium">Nyeri</span> → same county → cheapest fee</li>
              <li>Buyer in <span className="text-ink font-medium">Nyandarua</span> (also Central) → same region → mid fee</li>
              <li>Buyer in <span className="text-ink font-medium">Nairobi</span> (Nairobi Metro) → different region → highest fee</li>
            </ul>
          </div>

          <h3 className="font-semibold text-sm mb-3">Which county belongs to which region</h3>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="text-left text-muted border-b border-border">
                  <th className="py-2 pr-4">Region</th>
                  <th className="py-2 pr-4">Counties</th>
                </tr>
              </thead>
              <tbody>
                {REGIONS.map((region) => (
                  <tr key={region.name} className="border-b border-border last:border-0 align-top">
                    <td className="py-2 pr-4 font-medium whitespace-nowrap">{region.name}</td>
                    <td className="py-2 pr-4 text-muted">{region.counties.join(", ")}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <p className="text-xs text-muted mt-3">
            Marsabit and Makueni aren&apos;t mapped to a region yet, so orders touching those two
            counties always land on the (most expensive) different-region fee today.
          </p>
        </div>
      </div>
    </div>
  );
}
