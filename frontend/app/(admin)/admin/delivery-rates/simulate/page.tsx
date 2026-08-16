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
  const [counties, setCounties] = useState<string[]>(["Nairobi", "Nyeri"]);
  const [countyInput, setCountyInput] = useState("");
  const [cartTotal, setCartTotal] = useState("500");
  const [query, setQuery] = useState<{ counties: string[]; total: string } | null>({
    counties: ["Nairobi", "Nyeri"],
    total: "500",
  });

  const { data, isPending, isError } = useQuery({
    queryKey: ["admin", "delivery-simulate", query],
    queryFn: () => {
      const params = new URLSearchParams();
      for (const c of query!.counties) params.append("buyer_county", c);
      params.set("sample_cart_total", query!.total);
      return fetch(`/api/admin/delivery/simulate?${params.toString()}`).then(
        (r) => r.json(),
      ) as Promise<DeliverySimulationResponse>;
    },
    enabled: !!query,
  });

  function addCounty(name: string) {
    const trimmed = name.trim();
    if (!trimmed) return;
    const match = COUNTIES.find((c) => c.toLowerCase() === trimmed.toLowerCase()) ?? trimmed;
    setCounties((prev) => (prev.includes(match) ? prev : [...prev, match]));
    setCountyInput("");
  }

  function removeCounty(name: string) {
    setCounties((prev) => prev.filter((c) => c !== name));
  }

  function runSimulation(e: React.FormEvent) {
    e.preventDefault();
    if (counties.length === 0) return;
    setQuery({ counties, total: cartTotal || "0" });
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
        Pick one or more buyer counties and see how every active shop&apos;s county/region-based fee
        changes across them, side by side with today&apos;s live cart-total fee. Nothing here charges
        real buyers — it&apos;s a dry run against real seller locations. Once the geo numbers look
        right, flip &quot;Use county/region pricing&quot; on in{" "}
        <Link href="/admin/delivery-rates" className="underline hover:text-amber">Delivery Rates</Link> to
        make it live at checkout immediately.
      </p>

      <form onSubmit={runSimulation} className="card p-5 mb-6 flex flex-wrap items-end gap-4">
        <div className="flex-1 min-w-[16rem]">
          <label className="block text-sm font-medium mb-1">Buyer counties</label>
          <div className="flex flex-wrap gap-2 mb-2">
            {counties.map((c) => (
              <span
                key={c}
                className="inline-flex items-center gap-1 text-xs font-medium px-2 py-1 rounded-full bg-amber/15 text-amber"
              >
                {c}
                <button
                  type="button"
                  onClick={() => removeCounty(c)}
                  className="hover:text-danger"
                  aria-label={`Remove ${c}`}
                >
                  ×
                </button>
              </span>
            ))}
            {counties.length === 0 && (
              <span className="text-xs text-muted">Add at least one county below.</span>
            )}
          </div>
          <div className="flex gap-2">
            <input
              list="counties"
              className="input-field flex-1"
              placeholder="Type a county and press Enter"
              value={countyInput}
              onChange={(e) => setCountyInput(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter" || e.key === ",") {
                  e.preventDefault();
                  addCounty(countyInput);
                }
              }}
            />
            <button
              type="button"
              className="btn-outline-dark px-4"
              onClick={() => addCounty(countyInput)}
            >
              Add
            </button>
            <datalist id="counties">
              {COUNTIES.map((c) => <option key={c} value={c} />)}
            </datalist>
          </div>
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
        <button type="submit" className="btn-accent" disabled={counties.length === 0}>
          Run simulation
        </button>
      </form>

      {isPending && <p className="text-muted text-sm">Loading…</p>}
      {isError && <p className="text-danger text-sm">Could not run the simulation.</p>}

      {data && (
        <div className="card p-5">
          <div className="flex items-center justify-between mb-4 flex-wrap gap-2">
            <p className="text-sm text-muted">
              {data.rows.length} active shop{data.rows.length === 1 ? "" : "s"} ·{" "}
              {data.buyer_counties.length} buyer count{data.buyer_counties.length === 1 ? "y" : "ies"}
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
                  {data.buyer_counties.map((c) => (
                    <th key={c} className="py-2 pr-4">
                      {c}
                      <span className="block font-normal normal-case text-[10px] text-muted">
                        {data.buyer_regions[c] ?? "unmapped"}
                      </span>
                    </th>
                  ))}
                  <th className="py-2 pr-4">Cart-total fee</th>
                </tr>
              </thead>
              <tbody>
                {data.rows.map((row) => (
                  <tr key={row.shop_id} className="border-b border-border last:border-0">
                    <td className="py-2 pr-4 font-medium">{row.shop_name}</td>
                    <td className="py-2 pr-4 text-muted">{row.shop_county ?? "—"}</td>
                    <td className="py-2 pr-4 text-muted">{row.region ?? "—"}</td>
                    {data.buyer_counties.map((c) => {
                      const geoFee = row.geo_fees[c];
                      const diff = parseFloat(geoFee) - parseFloat(row.cart_total_fee);
                      return (
                        <td key={c} className="py-2 pr-4">
                          KES {geoFee}
                          <span
                            className={`block text-[10px] ${diff > 0 ? "text-danger" : diff < 0 ? "text-success" : "text-muted"}`}
                          >
                            {diff > 0 ? "+" : ""}{diff.toFixed(0)} vs legacy
                          </span>
                        </td>
                      );
                    })}
                    <td className="py-2 pr-4 text-muted">KES {row.cart_total_fee}</td>
                  </tr>
                ))}
                {data.rows.length === 0 && (
                  <tr>
                    <td colSpan={4 + data.buyer_counties.length} className="py-6 text-center text-muted">
                      No active shops yet.
                    </td>
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
