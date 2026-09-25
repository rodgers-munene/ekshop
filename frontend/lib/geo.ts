export const NAIROBI_CENTER = [-1.286, 36.817] as const;

export const TILE_URLS = {
  hybrid: "https://mt1.google.com/vt/lyrs=y&x={x}&y={y}&z={z}",
  osm: "https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png",
} as const;

export type BasemapKey = keyof typeof TILE_URLS;

const SVG_MARKER = (size: number) =>
  `data:image/svg+xml,${encodeURIComponent(
    `<svg xmlns="http://www.w3.org/2000/svg" width="${size}" height="${size * 1.4}" viewBox="0 0 24 34"><path d="M12 0C5.4 0 0 5.4 0 12c0 9 12 22 12 22s12-13 12-22c0-6.6-5.4-12-12-12z" fill="#f59e0b"/><circle cx="12" cy="12" r="5" fill="white"/></svg>`
  )}`;

export const MARKER_ICON = (size = 28) => ({
  iconUrl: SVG_MARKER(size),
  iconSize: [size, size * 1.4] as [number, number],
  iconAnchor: [size / 2, size * 1.4] as [number, number],
});

export async function reverseGeocode(lat: number, lng: number) {
  const res = await fetch(`/api/geography/reverse-geocode?lat=${lat}&lng=${lng}`);
  if (!res.ok) return null;
  return (await res.json()) as import("@/types/interface").ReverseGeocodeResult;
}

export async function searchGeo(q: string) {
  const res = await fetch(`/api/geography/search?q=${encodeURIComponent(q)}`);
  if (!res.ok) return [];
  return (await res.json()) as import("@/types/interface").GeoSearchResult[];
}
