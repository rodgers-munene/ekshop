"use client";

import { useEffect, useRef } from "react";
import type { Map as LeafletMap } from "leaflet";
import { NAIROBI_CENTER } from "@/lib/geo";

export default function ReadOnlyMap({
  lat,
  lng,
  height = "h-48",
}: {
  lat?: number;
  lng?: number;
  height?: string;
}) {
  const containerRef = useRef<HTMLDivElement>(null);
  const mapRef = useRef<LeafletMap | null>(null);

  useEffect(() => {
    if (!containerRef.current) return;

    (async () => {
      const L = (await import("leaflet")).default as typeof import("leaflet");
      const map = L.map(containerRef.current!, { zoomControl: false }).setView(
        lat != null && lng != null ? [lat, lng] : [NAIROBI_CENTER[0], NAIROBI_CENTER[1]],
        lat != null && lng != null ? 15 : 6
      );
      L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
        attribution: "© OpenStreetMap",
        maxZoom: 19,
      }).addTo(map);

      if (lat != null && lng != null) {
        L.marker([lat, lng]).addTo(map);
      }

      mapRef.current = map;
    })();

    return () => {
      mapRef.current?.remove();
      mapRef.current = null;
    };
  }, [lat, lng]);

  return <div ref={containerRef} className={`w-full ${height} bg-surface rounded-lg`} />;
}
