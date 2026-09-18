"use client";

import { useState } from "react";
import Link from "next/link";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { DeliveryRates, PricingModel } from "@/types/interface";

type RateField = keyof Omit<DeliveryRates, "id" | "updated_at" | "pricing_model" | "standard_delivery_hours">;

// The distance ladder, cheapest first. Each band must cost at least as much as
// the one above it, or a further delivery ends up cheaper than a nearer one —
// the exact defect the cart-total model shipped with.
const BAND_FIELDS: { key: RateField; label: string; hint: string }[] = [
  { key: "same_ward_fee", label: "Same ward", hint: "Buyer and vendor in the same ward — a short local hop" },
  { key: "same_subcounty_fee", label: "Same sub-county", hint: "Different ward, same sub-county" },
  { key: "same_county_fee", label: "Same county", hint: "Cross-town within one county" },
  { key: "same_region_fee", label: "Same region", hint: "Different county, same logistics cluster (e.g. Nairobi Metro)" },
  { key: "adjacent_region_fee", label: "Neighbouring region", hint: "Regions that share a border, e.g. Nairobi Metro → Central" },
  { key: "different_region_fee", label: "Countrywide", hint: "Unrelated parts of the country, e.g. Nairobi → Mandera" },
  { key: "unknown_origin_fee", label: "Unknown vendor location", hint: "Fallback when a shop hasn't set its county" },
];

const WEIGHT_FIELDS: { key: RateField; label: string; hint: string; unit: string }[] = [
  { key: "weight_allowance_kg", label: "Free weight allowance", hint: "Cart weight carried at no extra charge", unit: "kg" },
  { key: "per_kg_fee", label: "Per kg beyond allowance", hint: "Only products with a weight set count toward this", unit: "KES" },
  { key: "max_weight_surcharge", label: "Max weight surcharge", hint: "Ceiling on the weight component alone", unit: "KES" },
];

const BOUND_FIELDS: { key: RateField; label: string; hint: string; unit: string }[] = [
  { key: "min_delivery_fee", label: "Minimum fee", hint: "Floor, so a tiny cart isn't delivered at a loss", unit: "KES" },
  { key: "max_delivery_fee", label: "Maximum fee", hint: "Cap, so a heavy long-haul order stays orderable", unit: "KES" },
];

const ALL_FIELDS = [...BAND_FIELDS, ...WEIGHT_FIELDS, ...BOUND_FIELDS];

const MODELS: { value: PricingModel; label: string; hint: string }[] = [
  {
    value: "cost_based",
    label: "Cost-based (distance + weight)",
    hint: "Prices the journey itself. Cart value is not an input, so the fee can never fall as the cart grows.",
  },
  {
    value: "cart_total",
    label: "Cart total (legacy)",
    hint: "Charges a percentage or tier of cart value. Blind to distance, and drops from 150 to 66 as a cart crosses 800.",
  },
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
  { name: "Eastern", counties: ["Embu", "Kitui", "Meru", "Tharaka-Nithi", "Isiolo", "Makueni"] },
  { name: "North Eastern", counties: ["Garissa", "Wajir", "Mandera", "Marsabit"] },
];

function FeeInput({
  label,
  hint,
  unit,
  value,
  onChange,
}: {
  label: string;
  hint: string;
  unit: string;
  value: string;
  onChange: (value: string) => void;
}) {
  return (
    <div>
      <label className="block text-sm font-medium mb-1">{label}</label>
      <p className="text-xs text-muted mb-1.5">{hint}</p>
      <div className="flex items-center gap-2">
        <span className="text-sm text-muted w-8 shrink-0">{unit}</span>
        <input
          type="number"
          min="0"
          step="1"
          className="input-field"
          value={value}
          onChange={(e) => onChange(e.target.value)}
          required
        />
      </div>
    </div>
  );
}

export default function AdminDeliveryRatesPage() {
  const queryClient = useQueryClient();
  const [draftOverride, setDraftOverride] = useState<Record<string, string> | null>(null);
  const [saving, setSaving] = useState(false);
  const [togglingLive, setTogglingLive] = useState(false);

  const { data: rates, isPending: loading, error } = useQuery({
    queryKey: ["admin", "delivery-rates"],
    // Checked rather than cast. An expired admin session answers 401 with
    // {detail}, and casting that to DeliveryRates leaves pricing_model
    // undefined — which this page would render as "no model is live", when in
    // fact checkout is charging normally and only the page failed to load.
    queryFn: async (): Promise<DeliveryRates> => {
      const res = await fetch("/api/admin/delivery/rates");
      const body = await res.json().catch(() => null);
      if (!res.ok || typeof body?.pricing_model !== "string") {
        throw new Error(
          body?.detail ??
            (res.status === 401
              ? "Your admin session has expired. Sign in again to load the rates."
              : "The delivery rates endpoint returned an unexpected response."),
        );
      }
      return body as DeliveryRates;
    },
  });

  const draft: Record<string, string> = draftOverride ?? (rates
    ? Object.fromEntries(ALL_FIELDS.map(({ key }) => [key, rates[key]]))
    : {});

  function setField(key: string, value: string) {
    setDraftOverride({ ...draft, [key]: value });
  }

  // Guard the one invariant an admin can break from this form: a band that costs
  // less than a nearer one means a longer delivery is charged less.
  const ladderBreak = BAND_FIELDS
    .filter(({ key }) => key !== "unknown_origin_fee")
    .map(({ key, label }) => ({ label, value: parseFloat(draft[key] ?? "0") }))
    .find(({ value }, i, all) => i > 0 && value < all[i - 1].value);

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

  async function switchModel(model: PricingModel) {
    if (model === rates?.pricing_model) return;
    setTogglingLive(true);
    try {
      const res = await fetch("/api/admin/delivery/rates", {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ pricing_model: model }),
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) { toast.error(data.detail ?? "Could not switch pricing model"); return; }
      toast.success(`${MODELS.find((m) => m.value === model)?.label} is now live at checkout`);
      queryClient.invalidateQueries({ queryKey: ["admin", "delivery-rates"] });
    } finally {
      setTogglingLive(false);
    }
  }

  return (
    <div>
      <h1 className="text-2xl font-bold mb-2">Delivery Rates</h1>
      <p className="text-sm text-muted mb-6">
        Delivery is priced from the journey, not the basket: how far the parcel travels and how much it
        weighs. A cart spanning several sellers is charged one journey — the longest leg — rather than a
        fee per seller.
      </p>

      <div className="grid grid-cols-1 lg:grid-cols-[minmax(0,26rem)_1fr] gap-6 items-start">
        <div>
          {loading ? (
            <p className="text-muted text-sm">Loading…</p>
          ) : error || !rates ? (
            <div className="card p-6 border-red-500/40">
              <h2 className="font-semibold text-sm mb-1 text-red-500">Could not load the delivery rates</h2>
              <p className="text-xs text-muted">
                {error instanceof Error ? error.message : "The delivery rates endpoint did not respond."}
              </p>
              <p className="text-xs text-muted mt-2">
                Checkout is unaffected — it reads the live setting directly, not this page.
              </p>
            </div>
          ) : (
            <>
              <div className="card p-6 mb-6">
                <h2 className="font-semibold text-sm mb-1">Live pricing model</h2>
                <p className="text-xs text-muted mb-4">
                  What checkout charges right now. Check any change in the{" "}
                  <Link href="/admin/delivery-rates/simulate" className="underline hover:text-amber">
                    Delivery Fee Simulator
                  </Link>{" "}
                  first — it prices every active seller against the counties you pick.
                </p>

                <div className="space-y-2">
                  {MODELS.map(({ value, label, hint }) => {
                    const active = rates?.pricing_model === value;
                    return (
                      <button
                        key={value}
                        onClick={() => switchModel(value)}
                        disabled={togglingLive || active}
                        aria-pressed={active}
                        className={`w-full text-left rounded-lg border p-3 transition-colors disabled:cursor-default ${
                          active ? "border-amber bg-amber/5" : "border-border hover:border-amber/50"
                        } ${togglingLive ? "opacity-50" : ""}`}
                      >
                        <span className="flex items-center gap-2">
                          <span
                            className={`w-3.5 h-3.5 rounded-full border-2 shrink-0 ${
                              active ? "border-amber bg-amber" : "border-border"
                            }`}
                          />
                          <span className="text-sm font-medium">{label}</span>
                          {active && <span className="text-xs text-amber font-medium">Live</span>}
                        </span>
                        <span className="block text-xs text-muted mt-1 pl-5.5">{hint}</span>
                      </button>
                    );
                  })}
                </div>

                {/* Every stored value should match a button above. If one does
                    not, say so rather than leaving all three unselected, which
                    reads as "nothing is live" when something certainly is. */}
                {!MODELS.some((m) => m.value === rates.pricing_model) && (
                  <p className="text-xs text-red-500 mt-3">
                    Checkout is set to &quot;{rates.pricing_model}&quot;, which is not one of the models
                    above. Pick one to move it onto a supported model.
                  </p>
                )}
              </div>

              <form onSubmit={save} className="card p-6 space-y-5">
                <div>
                  <h2 className="font-semibold text-sm mb-1">Distance bands</h2>
                  <p className="text-xs text-muted mb-3">
                    How far the parcel travels. Every cart is charged exactly one of these.
                  </p>
                  <div className="space-y-4">
                    {BAND_FIELDS.map(({ key, label, hint }) => (
                      <FeeInput
                        key={key}
                        label={label}
                        hint={hint}
                        unit="KES"
                        value={draft[key] ?? ""}
                        onChange={(v) => setField(key, v)}
                      />
                    ))}
                  </div>
                </div>

                {ladderBreak && (
                  <p className="text-xs rounded-lg bg-amber/10 border border-amber/40 p-3">
                    <span className="font-medium">{ladderBreak.label}</span> costs less than the band before
                    it, so a longer delivery would be charged less than a shorter one. That is the defect the
                    legacy model had — worth a second look before saving.
                  </p>
                )}

                <div className="border-t border-border pt-5">
                  <h2 className="font-semibold text-sm mb-1">Weight surcharge</h2>
                  <p className="text-xs text-muted mb-3">
                    Added on top of the band. Products with no weight set contribute nothing, so a seller who
                    left the field blank never has a surcharge invented for them.
                  </p>
                  <div className="space-y-4">
                    {WEIGHT_FIELDS.map(({ key, label, hint, unit }) => (
                      <FeeInput
                        key={key}
                        label={label}
                        hint={hint}
                        unit={unit}
                        value={draft[key] ?? ""}
                        onChange={(v) => setField(key, v)}
                      />
                    ))}
                  </div>
                </div>

                <div className="border-t border-border pt-5">
                  <h2 className="font-semibold text-sm mb-3">Bounds</h2>
                  <div className="space-y-4">
                    {BOUND_FIELDS.map(({ key, label, hint, unit }) => (
                      <FeeInput
                        key={key}
                        label={label}
                        hint={hint}
                        unit={unit}
                        value={draft[key] ?? ""}
                        onChange={(v) => setField(key, v)}
                      />
                    ))}
                  </div>
                </div>

                <button type="submit" disabled={saving} className="btn-accent disabled:opacity-50">
                  {saving ? "Saving…" : "Save rates"}
                </button>
              </form>
            </>
          )}
        </div>

        <div className="card p-6">
          <h2 className="font-semibold text-sm mb-3">How the cost-based algorithm works</h2>
          <p className="text-sm text-muted mb-4">
            A quote is built from two things only — distance and weight. Cart value never enters it, which
            is what guarantees the fee can&apos;t fall as a buyer adds items:
          </p>

          <ol className="space-y-2.5 text-sm mb-5">
            <li className="flex gap-2">
              <span className="font-semibold text-amber shrink-0">1.</span>
              <span>
                Each seller in the cart is matched to a <span className="font-medium">distance band</span>,
                using the finest detail both ends share — ward, then sub-county, then county, then region.
              </span>
            </li>
            <li className="flex gap-2">
              <span className="font-semibold text-amber shrink-0">2.</span>
              <span>
                The cart is charged <span className="font-medium">one journey</span>: the single most
                expensive leg. Extra sellers nearer than that add nothing.
              </span>
            </li>
            <li className="flex gap-2">
              <span className="font-semibold text-amber shrink-0">3.</span>
              <span>
                Cart weight above the free allowance adds a{" "}
                <span className="font-medium">per-kg surcharge</span>, itself capped.
              </span>
            </li>
            <li className="flex gap-2">
              <span className="font-semibold text-amber shrink-0">4.</span>
              <span>
                The result is held between the <span className="font-medium">minimum and maximum</span> fee
                and rounded up to the nearest 5.
              </span>
            </li>
          </ol>

          <div className="rounded-lg bg-surface p-4 text-sm mb-5">
            <p className="font-medium mb-1.5">Worked example</p>
            <p className="text-muted">
              A buyer in <span className="text-ink font-medium">Lang&apos;ata, Nairobi</span> orders from two
              sellers — one in <span className="text-ink font-medium">Lang&apos;ata</span>, one in{" "}
              <span className="text-ink font-medium">Nyeri</span>.
            </p>
            <ul className="mt-1.5 space-y-1 text-muted list-disc list-inside">
              <li>Lang&apos;ata seller → same ward → cheapest band</li>
              <li>Nyeri seller → Central borders Nairobi Metro → neighbouring region band</li>
              <li>One journey is charged, so the cart pays the <span className="text-ink font-medium">Nyeri</span> band only</li>
              <li>Whether the cart holds Ksh 20 or Ksh 20,000 of goods, the fee is identical</li>
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
            All 47 counties are mapped. Makueni and Marsabit were previously missing, which silently
            put every order touching them on the most expensive band; they now sit in Eastern and North
            Eastern respectively. A test fails the build if a county is ever left unmapped again.
          </p>
        </div>
      </div>
    </div>
  );
}
