"use client";

import React, { useEffect, useRef, useMemo } from "react";
import type { Map as LeafletMap, LatLngTuple } from "leaflet";
import { NAIROBI_CENTER } from "@/lib/geo";

interface ReadOnlyMapProps {
  lat?: number;
  lng?: number;
  height?: string;
  children?: React.ReactNode;
  className?: string;
}

export default function ReadOnlyMap({ lat, lng, height = "h-48", children, className = "" }: ReadOnlyMapProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const mapRef = useRef<LeafletMap | null>(null);
  const markersRef = useRef<Array<{ lat: number; lng: number; element: HTMLElement; marker: unknown }>>([]);

  const center = useMemo<LatLngTuple>(
    () => (lat != null && lng != null ? [lat, lng] : [...NAIROBI_CENTER] as LatLngTuple),
    [lat, lng]
  );
  const zoom = lat != null && lng != null ? 15 : 6;

  useEffect(() => {
    if (!containerRef.current) return;

    let map: LeafletMap;
    (async () => {
      const L = (await import("leaflet")).default as typeof import("leaflet");
      map = L.map(containerRef.current!, { zoomControl: false }).setView(center, zoom);
      L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
        attribution: "Ac OpenStreetMap",
        maxZoom: 19,
      }).addTo(map);

      // Default marker if no children and lat/lng provided
      if (children == null && lat != null && lng != null) {
        L.marker([lat, lng]).addTo(map);
      }

      // Custom markers from children
      if (children != null) {
        const childrenArray = React.Children.toArray(children);
        childrenArray.forEach((child) => {
          if (!React.isValidElement(child)) return;
          const props = child.props as { lat?: number; lng?: number; element?: React.ReactNode; children?: React.ReactNode };
          if (props.lat != null && props.lng != null) {
            const div = document.createElement("div");
            const content = props.element ?? props.children;
            if (typeof content === "string" || typeof content === "number") {
              div.textContent = String(content);
            } else if (React.isValidElement(content)) {
              div.textContent = "●";
            }
            div.style.cssText = "font-size: 20px; line-height: 1;";
            const marker = L.marker([props.lat, props.lng], {
              icon: L.divIcon({ className: "", html: div.outerHTML, iconSize: [24, 24] }),
            }).addTo(map);
            markersRef.current.push({ lat: props.lat, lng: props.lng, element: div, marker });
          }
        });
      }

      mapRef.current = map;
    })();

    return () => {
      markersRef.current.forEach((m) => m.marker && typeof m.marker === "object" && "remove" in m.marker && (m.marker as { remove: () => void }).remove());
      markersRef.current = [];
      mapRef.current?.remove();
      mapRef.current = null;
    };
  }, [lat, lng, children, center, zoom]);

  return <div ref={containerRef} className={`w-full ${height} bg-surface rounded-lg ${className}`} />;
}