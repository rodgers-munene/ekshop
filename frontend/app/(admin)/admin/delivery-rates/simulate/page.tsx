"use client";

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { DeliverySimulationResponse } from "@/types/interface";

const COUNTIES = [
  "Nairobi", "Kiambu", "Machakos", "Kajiado", "Murang'a",
  "Nyeri", "Nyandarua", "Kirinyaga",
  "Mombasa", "Kwale", "Kilifi", "Tana River", "Lamu", "Taita Taveta",
  "Nakuru", "Baringo", "Laikipia", "Nandi", "Uasin Gishu", "Trans Nzoia",
  "Elgeyo Marakwet", "West Pokot", "Samburu", "Turkana",
  "Kericho", "Bomet", "Narok",
  "Kakamega", "Bungoma", "Busia", "Vihiga",
  "Kisumu", "Siaya", "Homa Bay", "Migori", "Kisii", "Nyamira",
  "Embu", "Kitui", "Meru", "Tharaka-Nithi", "Isiolo",
  "Garissa", "Wajir", "Mandera",
];

export default function DeliverySimulatorPage() {
  const [buyerCounty, setBuyerCounty] = useState("Nairobi");
  const [cartTotal, setCartTotal] = useState("500");
  const [query, setQuery] = useState<{ county: string; total: string } | null>({ county: "Nairobi", total: "500" });

  const { data, isPending, isError } = useQuery({
    queryKey: ["admin", "delivery-simulate", query],
    queryFn: () =>
      fetch(`/api/admin/delivery/simulate?buyer_county=${encodeURIComponent(query!.county)}&sample_cart_total=${query!.total}`)
        .then((r) => r.json()) as Promise<DeliverySimulationResponse>,
    enabled: !!query,
  });

  function runSimulation(e: React.FormEvent) {
    e.preventDefault();
    setQuery({ county: buyerCounty, total: cartTotal || "0" });
  }

  return (
    <div>
      <div className="flex items-center gap-2 mb-2">
        <Link href="/admin/delivery-rates" className="text-xs text-muted hover:text-amber underline">
          ← Delivery Rates
        </Link>
      </div>
      <h1 className="text-2xl font-bold mb-2">Delivery Fee Simulator</h1>
      <p className="text-sm text-muted mb-6 max-w-2xl">
        Pick a buyer county and see what every active shop&apos;s county/region-based fee would be, side by
        side with today&apos;s live cart-total fee. Nothing here charges real buyers — it&apos;s a dry run
        against real seller locations. Once the geo numbers look right, flip &quot;Use county/region
        pricing&quot; on in <Link href="/admin/delivery-rates" className="underline hover:text-amber">Delivery Rates</Link> to
        make it live at checkout immediately.
      </p>

      <form onSubmit={runSimulation} className="card p-5 mb-6 flex flex-wrap items-end gap-4">
        <div>
          <label className="block text-sm font-medium mb-1">Buyer county</label>
          <input
            list="counties"
            className="input-field"
            value={buyerCounty}
            onChange={(e) => setBuyerCounty(e.target.value)}
            required
          />
          <datalist id="counties">
            {COUNTIES.map((c) => <option key={c} value={c} />)}
          </datalist>
        </div>
        <div>
          <label className="block text-sm font-medium mb-1">Sample cart total (KES)</label>
          <input
            type="number"
            min="0"
            step="1"
            className="input-field"
            value={cartTotal}
            onChange={(e) => setCartTotal(e.target.value)}
          />
        </div>
        <button type="submit" className="btn-accent">Run simulation</button>
      </form>

      {isPending && <p className="text-muted text-sm">Loading…</p>}
      {isError && <p className="text-danger text-sm">Could not run the simulation.</p>}

      {data && (
        <div className="card p-5">
          <div className="flex items-center justify-between mb-4">
            <p className="text-sm text-muted">
              {data.rows.length} active shop{data.rows.length === 1 ? "" : "s"} · buyer region:{" "}
              <span className="font-medium text-ink">{data.buyer_region ?? "unmapped"}</span>
            </p>
            <span
              className={`text-[10px] uppercase tracking-wide font-semibold px-2 py-1 rounded-full ${
                data.live_model === "geo" ? "bg-success/15 text-success" : "bg-progress/15 text-progress"
              }`}
            >
              Live model: {data.live_model === "geo" ? "County / region" : "Cart total (legacy)"}
            </span>
          </div>

          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="text-left text-muted border-b border-border">
                  <th className="py-2 pr-4">Shop</th>
                  <th className="py-2 pr-4">Shop county</th>
                  <th className="py-2 pr-4">Region</th>
                  <th className="py-2 pr-4">Geo fee</th>
                  <th className="py-2 pr-4">Cart-total fee</th>
                  <th className="py-2 pr-4">Difference</th>
                </tr>
              </thead>
              <tbody>
                {data.rows.map((row) => {
                  const diff = parseFloat(row.geo_fee) - parseFloat(row.cart_total_fee);
                  return (
                    <tr key={row.shop_id} className="border-b border-border last:border-0">
                      <td className="py-2 pr-4 font-medium">{row.shop_name}</td>
                      <td className="py-2 pr-4 text-muted">{row.shop_county ?? "—"}</td>
                      <td className="py-2 pr-4 text-muted">{row.region ?? "—"}</td>
                      <td className="py-2 pr-4">KES {row.geo_fee}</td>
                      <td className="py-2 pr-4 text-muted">KES {row.cart_total_fee}</td>
                      <td className={`py-2 pr-4 ${diff > 0 ? "text-danger" : diff < 0 ? "text-success" : "text-muted"}`}>
                        {diff > 0 ? "+" : ""}{diff.toFixed(0)}
                      </td>
                    </tr>
                  );
                })}
                {data.rows.length === 0 && (
                  <tr>
                    <td colSpan={6} className="py-6 text-center text-muted">No active shops yet.</td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
}
