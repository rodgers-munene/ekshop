"use client";

import "leaflet/dist/leaflet.css";
import { useEffect, useRef, useState } from "react";
import type { LayerGroup, Map as LeafletMap } from "leaflet";
import {
  MarketExpansionReport,
  MarketExpansionSublocation,
} from "@/types/interface";

/** Density bands for the demand choropleth, people per km². They follow the
 * deciles of the study's own sublocations (median 532) rather than a generic
 * scale, so no band is empty and none swallows half the county. */
const DEMAND_BREAKS = [150, 350, 550, 750, 1000];
const DEMAND_COLORS = ["#FEF3C7", "#FDE68A", "#FCD806", "#F59E0B", "#EA580C", "#B91C1C"];
const NO_DEMAND_COLOR = "#E5E7EB";

export function demandColor(density: number | null | undefined): string {
  if (!density) return NO_DEMAND_COLOR;
  for (let i = 0; i < DEMAND_BREAKS.length; i += 1) {
    if (density < DEMAND_BREAKS[i]) return DEMAND_COLORS[i];
  }
  return DEMAND_COLORS[DEMAND_COLORS.length - 1];
}

export const DEMAND_LEGEND: { label: string; color: string }[] = [
  { label: "no reported population", color: NO_DEMAND_COLOR },
  { label: `under ${DEMAND_BREAKS[0]}`, color: DEMAND_COLORS[0] },
  { label: `${DEMAND_BREAKS[0]}–${DEMAND_BREAKS[1]}`, color: DEMAND_COLORS[1] },
  { label: `${DEMAND_BREAKS[1]}–${DEMAND_BREAKS[2]}`, color: DEMAND_COLORS[2] },
  { label: `${DEMAND_BREAKS[2]}–${DEMAND_BREAKS[3]}`, color: DEMAND_COLORS[3] },
  { label: `${DEMAND_BREAKS[3]}–${DEMAND_BREAKS[4]}`, color: DEMAND_COLORS[4] },
  { label: `over ${DEMAND_BREAKS[4]}`, color: DEMAND_COLORS[5] },
];

export type MarketLayerKey = "demand" | "suitability" | "anchors" | "candidates" | "reach" | "shops";

export const MARKET_LAYERS: { key: MarketLayerKey; label: string }[] = [
  { key: "demand", label: "Population density" },
  { key: "suitability", label: "Scored grid (suitability ≥ 55)" },
  { key: "anchors", label: "Demand anchors" },
  { key: "candidates", label: "Candidate sites" },
  { key: "reach", label: "3 km reach" },
  { key: "shops", label: "Ekshop shops" },
];

const DEFAULT_VISIBLE: Record<MarketLayerKey, boolean> = {
  demand: true,
  suitability: false,
  anchors: false,
  candidates: true,
  reach: false,
  shops: true,
};

/** Mirror of the backend's name normalisation: the layer properties are
 * UPPERCASE with double spaces, the coverage rows are proper-case. */
function key(name: string | null | undefined): string {
  return (name ?? "").replace(/\s+/g, " ").trim().toLowerCase();
}

function escapeHtml(value: unknown): string {
  return String(value ?? "").replace(/[&<>"]/g, (c) =>
    ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" })[c] as string,
  );
}

/** Study numbers are always present in the bundle, but the API types allow a
 * null, so render a dash rather than "null". */
function text(value: number | string | null | undefined, suffix = ""): string {
  if (value === null || value === undefined) return "–";
  return `${typeof value === "number" ? value.toLocaleString() : value}${suffix}`;
}

export default function MarketExpansionMap({ report }: { report: MarketExpansionReport }) {
  const containerRef = useRef<HTMLDivElement>(null);
  const mapRef = useRef<LeafletMap | null>(null);
  const groupsRef = useRef<Map<MarketLayerKey, LayerGroup>>(new Map());
  const [visible, setVisible] = useState<Record<MarketLayerKey, boolean>>(DEFAULT_VISIBLE);
  const [ready, setReady] = useState(false);

  useEffect(() => {
    if (!containerRef.current) return;
    let cancelled = false;
    let map: LeafletMap | null = null;

    (async () => {
      // Leaflet touches `window` on import, so the module is loaded inside the
      // effect the same way the other maps in this app do it.
      const L = (await import("leaflet")).default as typeof import("leaflet");
      if (cancelled || !containerRef.current) return;

      // The live join is optional: when the API could not read coverage the
      // report arrives without it, and the map still draws the study.
      const coverageRows = new Map(
        (report.coverage?.sublocations ?? []).map((row) => [key(row.name), row]),
      );
      const describe = (row: MarketExpansionSublocation | undefined) =>
        row
          ? `<div style="min-width:11rem">
               <b>${escapeHtml(row.name)}</b><br/>
               ${text(row.population)} people · ${text(row.area_km2)} km²<br/>
               ${text(row.density)} per km²<br/>
               ${row.shops} shop${row.shops === 1 ? "" : "s"} ·
               ${row.orders} paid order${row.orders === 1 ? "" : "s"}${
                 row.unserved ? "<br/><b>no Ekshop shop here</b>" : ""
               }
             </div>`
          : "";
      // No coverage row for this polygon: fall back to the study's own numbers
      // so a demand area is never a shape you can hover but not read.
      const describeStudy = (feature: GeoJSON.Feature | undefined) => {
        const props = feature?.properties ?? {};
        if (!props.name) return "";
        return `<div style="min-width:11rem">
                  <b>${escapeHtml(props.name)}</b><br/>
                  ${text(props.population)} people · ${text(props.area_km2)} km²<br/>
                  ${text(props.density)} per km²<br/>
                  <span style="color:#6B7280">live coverage not shown</span>
                </div>`;
      };

      map = L.map(containerRef.current, { scrollWheelZoom: true });
      L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
        attribution: "© OpenStreetMap",
        maxZoom: 19,
      }).addTo(map);

      const groups = new Map<MarketLayerKey, LayerGroup>();

      // Demand: the choropleth the whole tab is read through.
      const demand = L.geoJSON(report.layers.sublocations, {
        style: (feature) => ({
          fillColor: demandColor(feature?.properties?.density),
          fillOpacity: 0.7,
          color: "#FFFFFF",
          weight: 0.5,
        }),
        onEachFeature: (feature, layer) => {
          const row = coverageRows.get(key(feature?.properties?.name));
          layer.bindTooltip(row ? describe(row) : describeStudy(feature), {
            sticky: true,
          });
        },
      });
      groups.set("demand", demand);

      // The scored grid, drawn as outlines so it reads as "the study looked
      // here too" rather than competing with the density fill.
      groups.set(
        "suitability",
        L.geoJSON(report.layers.suitability, {
          style: { color: "#7C3AED", weight: 0.5, fillColor: "#7C3AED", fillOpacity: 0.12 },
        }),
      );

      groups.set(
        "anchors",
        L.geoJSON(report.layers.anchors, {
          pointToLayer: (_feature, latlng) =>
            L.circleMarker(latlng, { radius: 2, color: "#1D3461", fillOpacity: 0.7 }),
          onEachFeature: (feature, layer) => {
            const props = feature?.properties ?? {};
            layer.bindTooltip(
              `${escapeHtml(props.name ?? "Anchor")} · ${escapeHtml(props.category ?? "")}`,
            );
          },
        }),
      );

      const candidates = L.layerGroup();
      report.candidates.forEach((site, index) => {
        const marker = L.marker([site.lat, site.lng], {
          icon: L.divIcon({
            className: "",
            html: `<div style="width:22px;height:22px;border-radius:9999px;background:#0F1F3D;color:#fff;font:600 11px/22px sans-serif;text-align:center;border:2px solid #FCD806">${index + 1}</div>`,
            iconSize: [22, 22],
            iconAnchor: [11, 11],
          }),
        });
        const factors = site.factors;
        marker.bindPopup(
          `<div style="min-width:12rem">
             <b>Site ${index + 1}</b> — ${text(site.suitability)}/100<br/>
             ${text(site.pop_1km)} people within 1 km<br/>
             ${text(site.poi_count_1_5km)} anchors within 1.5 km<br/>
             ${text(site.road_m)} m to a road · ${text(site.anchor_m)} m to an anchor<br/>
             <hr style="margin:4px 0"/>
             demand ${text(factors.demand)} · access ${text(factors.access)}<br/>
             amenities ${text(factors.amenities)} · anchor ${text(factors.anchor)}
           </div>`,
        );
        candidates.addLayer(marker);
      });
      groups.set("candidates", candidates);

      // The 3 km locality the storefront now ranks against, drawn so the
      // candidate sites can be read in the same units as the product list.
      const reach = L.layerGroup();
      report.candidates.forEach((site) => {
        reach.addLayer(
          L.circle([site.lat, site.lng], {
            radius: 3000,
            color: "#FCD806",
            weight: 1,
            fillColor: "#FCD806",
            fillOpacity: 0.08,
          }),
        );
      });
      groups.set("reach", reach);

      const shops = L.layerGroup();
      (report.coverage?.shops ?? []).forEach((shop) => {
        shops.addLayer(
          L.circleMarker([shop.lat, shop.lng], {
            radius: 6,
            color: "#0F1F3D",
            weight: 2,
            fillColor: shop.status === "active" ? "#1D8A4E" : "#EA580C",
            fillOpacity: 1,
          }).bindPopup(
            `<b>${escapeHtml(shop.name)}</b><br/>${escapeHtml(shop.town ?? "")}, ${escapeHtml(shop.county ?? "")}<br/>${escapeHtml(shop.status)}${shop.is_verified ? " · verified" : ""}`,
          ),
        );
      });
      groups.set("shops", shops);

      groupsRef.current = groups;
      mapRef.current = map;
      const bounds = demand.getBounds();
      if (bounds.isValid()) map.fitBounds(bounds, { padding: [12, 12] });
      setReady(true);
    })();

    return () => {
      cancelled = true;
      map?.remove();
      mapRef.current = null;
      groupsRef.current = new Map();
      setReady(false);
    };
  }, [report]);

  useEffect(() => {
    const map = mapRef.current;
    if (!map || !ready) return;
    groupsRef.current.forEach((group, layerKey) => {
      if (visible[layerKey]) group.addTo(map);
      else group.remove();
    });
  }, [visible, ready]);

  return (
    <div>
      <div className="flex flex-wrap gap-x-4 gap-y-1 mb-2">
        {/* The Ekshop shops layer exists only in the live join; offering a
         * toggle that draws nothing would read as "no shops here". */}
        {MARKET_LAYERS.filter(
          ({ key: layerKey }) => layerKey !== "shops" || report.coverage,
        ).map(({ key: layerKey, label }) => (
          <label key={layerKey} className="flex items-center gap-1.5 text-xs text-ink">
            <input
              type="checkbox"
              className="accent-amber"
              checked={visible[layerKey]}
              onChange={(event) =>
                setVisible((current) => ({ ...current, [layerKey]: event.target.checked }))
              }
            />
            {label}
          </label>
        ))}
      </div>
      <div ref={containerRef} className="w-full h-[28rem] rounded-lg bg-surface z-0" />
      <div className="mt-2 flex flex-wrap items-center gap-x-4 gap-y-1">
        {DEMAND_LEGEND.map(({ label, color }) => (
          <span key={label} className="flex items-center gap-1.5 text-xs text-muted">
            <span
              className="inline-block w-3 h-3 rounded-sm border border-border"
              style={{ background: color }}
            />
            {label}
          </span>
        ))}
        <span className="text-xs text-muted">per km², from the study</span>
      </div>
    </div>
  );
}
