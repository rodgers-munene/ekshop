"use client";

import { useEffect, useRef, useState } from "react";
import "leaflet/dist/leaflet.css";
import { Crosshair, Map as MapIcon, Search } from "lucide-react";
import { MARKER_ICON, NAIROBI_CENTER, searchGeo, reverseGeocode } from "@/lib/geo";
import type { GeoSearchResult, GeoSelection } from "@/types/interface";
// Leaflet itself (the JS module) is loaded lazily inside the mount effect so it
// never executes during server-side prerendering — it references `window` at
// import time, which breaks the `/register` static export. Only its types are
// imported here.
import type { Map as LeafletMap, Marker, TileLayer, LeafletMouseEvent } from "leaflet";

type Basemap = "hybrid" | "osm";

const BASEMAPS: { key: Basemap; label: string }[] = [
  { key: "hybrid", label: "Satellite" },
  { key: "osm", label: "Streets" },
];

export default function LocationPicker({
  initial,
  onConfirm,
  onCancel,
  className = "",
}: {
  initial?: { lat: number; lng: number };
  onConfirm: (sel: GeoSelection) => void;
  onCancel?: () => void;
  className?: string;
}) {
  const containerRef = useRef<HTMLDivElement>(null);
  const mapRef = useRef<LeafletMap | null>(null);
  const markerRef = useRef<Marker | null>(null);
  const hybridRef = useRef<TileLayer | null>(null);
  const osmRef = useRef<TileLayer | null>(null);
  const leafletRef = useRef<typeof import("leaflet") | null>(null);
  const requestIdRef = useRef(0);

  const [basemap, setBasemap] = useState<Basemap>("hybrid");
  const [place, setPlace] = useState<GeoSelection | null>(null);
  const [locating, setLocating] = useState(false);
  const [reverseLoading, setReverseLoading] = useState(false);
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<GeoSearchResult[]>([]);
  const [searching, setSearching] = useState(false);

  useEffect(() => {
    let disposed = false;
    let createdMap: LeafletMap | null = null;

    (async () => {
      // @types/leaflet uses `export =`, so the namespace type has no
      // `default`; at runtime the CJS module exposes one via bundler interop.
      const L = (await import("leaflet")).default as typeof import("leaflet");
      if (disposed || !containerRef.current) return;
      leafletRef.current = L;

      const map = L.map(containerRef.current, { zoomControl: false }).setView(
        initial ? [initial.lat, initial.lng] : [NAIROBI_CENTER[0], NAIROBI_CENTER[1]],
        initial ? 14 : 6
      );
      createdMap = map;
      L.control.zoom({ position: "topright" }).addTo(map);

      hybridRef.current = L.tileLayer(
        "https://mt1.google.com/vt/lyrs=y&x={x}&y={y}&z={z}",
        { attribution: "© Google", maxZoom: 20 }
      );
      osmRef.current = L.tileLayer(
        "https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png",
        { attribution: "© OpenStreetMap", maxZoom: 19 }
      );
      osmRef.current.addTo(map);
      hybridRef.current.addTo(map);

      if (initial) {
        const marker = L.marker([initial.lat, initial.lng], { icon: L.icon(MARKER_ICON()), draggable: true }).addTo(map);
        markerRef.current = marker;
        marker.on("dragend", () => {
          const pos = marker.getLatLng();
          placeMarker(map, pos.lat, pos.lng);
        });
      }

      map.on("click", (e: LeafletMouseEvent) => {
        placeMarker(map, e.latlng.lat, e.latlng.lng);
        map.flyTo(e.latlng, Math.max(map.getZoom(), 14));
      });

      mapRef.current = map;
    })();

    return () => {
      disposed = true;
      if (createdMap) createdMap.remove();
      mapRef.current = null;
      markerRef.current = null;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    const map = mapRef.current;
    if (!map || !hybridRef.current || !osmRef.current) return;
    if (basemap === "hybrid") {
      if (!map.hasLayer(hybridRef.current)) hybridRef.current.addTo(map);
      if (map.hasLayer(osmRef.current)) map.removeLayer(osmRef.current);
    } else {
      if (!map.hasLayer(osmRef.current)) osmRef.current.addTo(map);
      if (map.hasLayer(hybridRef.current)) map.removeLayer(hybridRef.current);
    }
  }, [basemap]);

  function placeMarker(map: LeafletMap, lat: number, lng: number) {
    const L = leafletRef.current;
    if (!L) return;
    setPlace(null);
    if (!markerRef.current) {
      markerRef.current = L.marker([lat, lng], { icon: L.icon(MARKER_ICON()), draggable: true }).addTo(map);
      markerRef.current.on("dragend", () => {
        const pos = markerRef.current?.getLatLng();
        if (pos) placeMarker(map, pos.lat, pos.lng);
      });
    } else {
      markerRef.current.setLatLng([lat, lng]);
    }
    resolvePlace(lat, lng);
  }

  async function resolvePlace(lat: number, lng: number) {
    const id = ++requestIdRef.current;
    setReverseLoading(true);
    try {
      const data = await reverseGeocode(lat, lng);
      if (requestIdRef.current !== id) return;
      if (!data) {
        setPlace(null);
        return;
      }
      setPlace({
        lat: data.lat,
        lng: data.lng,
        county: data.county,
        subcounty: data.subcounty,
        ward: data.ward,
        location: data.location,
        sublocation: data.sublocation,
        addressHint: data.address_hint,
        countyId: data.county_id,
        subcountyId: data.subcounty_id,
        wardId: data.ward_id,
      });
    } catch {
      if (requestIdRef.current === id) setPlace(null);
    } finally {
      if (requestIdRef.current === id) setReverseLoading(false);
    }
  }

  function findMe() {
    if (!navigator.geolocation) {
      setPlace(null);
      return;
    }
    setLocating(true);
    navigator.geolocation.getCurrentPosition(
      (pos) => {
        const { latitude, longitude } = pos.coords;
        const map = mapRef.current;
        if (map) {
          placeMarker(map, latitude, longitude);
          map.flyTo([latitude, longitude], 15);
        } else {
          resolvePlace(latitude, longitude);
        }
        setLocating(false);
      },
      () => {
        setLocating(false);
      },
      { enableHighAccuracy: true, timeout: 10000 }
    );
  }

  async function runSearch(e: React.FormEvent) {
    e.preventDefault();
    const q = query.trim();
    if (q.length < 2) return;
    setSearching(true);
    try {
      setResults(await searchGeo(q));
    } catch {
      setResults([]);
    } finally {
      setSearching(false);
    }
  }

  function pickResult(r: GeoSearchResult) {
    setQuery(r.name);
    setResults([]);
    const map = mapRef.current;
    if (!map) return;
    placeMarker(map, r.lat, r.lng);
    map.setView([r.lat, r.lng], 14);
  }

  return (
    <div className={`flex flex-col overflow-hidden rounded-xl border border-border bg-bg ${className}`}>
      <div className="relative">
        <div ref={containerRef} className="h-72 md:h-80 w-full bg-surface" />

        <form onSubmit={runSearch} className="absolute left-3 top-3 right-24 md:right-28 z-[500]">
          <div className="relative">
            <input
              value={query}
              onChange={(e) => {
                setQuery(e.target.value);
                if (results.length) setResults([]);
              }}
              placeholder="Search e.g. Kawangware, Kabarnet…"
              className="w-full rounded-lg border border-border bg-white/95 px-3 py-2 pr-8 text-sm shadow-sm outline-none focus:border-amber"
            />
            <button type="submit" className="absolute right-2 top-1/2 -translate-y-1/2 text-muted" aria-label="Search">
              <Search size={15} />
            </button>
          </div>
          {results.length > 0 && (
            <ul className="mt-1 overflow-hidden rounded-lg border border-border bg-white shadow-lg text-sm">
              {results.slice(0, 6).map((r, i) => (
                <li key={`${r.type}-${r.name}-${i}`}>
                  <button
                    type="button"
                    onClick={() => pickResult(r)}
                    className="w-full px-3 py-2 text-left hover:bg-surface"
                  >
                    <span className="font-medium text-ink">{r.name}</span>
                    <span className="block text-xs text-muted">{r.subtitle}</span>
                  </button>
                </li>
              ))}
            </ul>
          )}
        </form>

        <div className="absolute right-3 top-3 z-[500] flex flex-col gap-1.5">
          {BASEMAPS.map((b) => (
            <button
              key={b.key}
              type="button"
              onClick={() => setBasemap(b.key)}
              className={`flex items-center gap-1.5 rounded-md px-2 py-1.5 text-xs font-medium shadow-sm border transition-colors ${
                basemap === b.key
                  ? "bg-navy text-white border-navy"
                  : "bg-white/95 text-ink border-border hover:border-amber"
              }`}
            >
              <MapIcon size={13} />
              {b.label}
            </button>
          ))}
          <button
            type="button"
            onClick={findMe}
            disabled={locating}
            className="flex items-center justify-center gap-1.5 rounded-md px-2 py-1.5 text-xs font-medium shadow-sm border border-border bg-white/95 text-ink hover:border-amber disabled:opacity-50"
          >
            <Crosshair size={13} className={locating ? "animate-spin" : ""} />
            {locating ? "Locating…" : "My location"}
          </button>
        </div>
      </div>

      <div className="flex items-center justify-between gap-3 border-t border-border px-4 py-3">
        <div className="min-w-0 flex-1">
          {place ? (
            <>
              <p className="text-sm font-semibold text-ink truncate">{place.addressHint}</p>
              <p className="text-xs text-muted truncate">
                {place.sublocation || place.location ? `Tap Confirm to save ${place.sublocation || place.location}, ${place.ward}.` : "Tap Confirm when the pin is where you want delivery."}
              </p>
            </>
          ) : (
            <p className="text-xs text-muted">{reverseLoading ? "Pinpointing…" : "Drag the map / tap to drop the pin, or use My location."}</p>
          )}
        </div>
        <div className="flex items-center gap-2 shrink-0">
          {onCancel && (
            <button type="button" onClick={onCancel} className="rounded-md border border-border px-3 py-1.5 text-sm text-muted hover:text-ink">
              Cancel
            </button>
          )}
          <button
            type="button"
            onClick={() => place && onConfirm(place)}
            disabled={!place || reverseLoading}
            className="btn-accent !px-4 !py-1.5 text-sm disabled:opacity-40"
          >
            Confirm
          </button>
        </div>
      </div>
    </div>
  );
}