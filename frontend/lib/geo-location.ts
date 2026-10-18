export const LOCATION_COOKIE = "ekshop_loc";

export const DEFAULT_RADIUS_KM = 30;

export interface CustomerLocation {
  lat: number;
  lng: number;
}

/**
 * Read the location cookie. Returns null rather than a guess when anything is
 * off, because the failure mode of a bad coordinate is silently ranking the whole
 * catalogue against the Gulf of Guinea -- a page that looks fine and is wrong.
 */
export function parseLocationCookie(value?: string | null): CustomerLocation | null {
  if (!value) return null;
  let raw = value;
  try {
    raw = decodeURIComponent(value);
  } catch {
    raw = value;
  }
  const [latRaw, lngRaw] = raw.split(",");
  const lat = Number(latRaw);
  const lng = Number(lngRaw);
  if (!Number.isFinite(lat) || !Number.isFinite(lng)) return null;
  if (lat < -90 || lat > 90 || lng < -180 || lng > 180) return null;
  return { lat, lng };
}

export function serializeLocation(location: CustomerLocation): string {
  return `${location.lat.toFixed(5)},${location.lng.toFixed(5)}`;
}

/** Query fragment for the product/recommendation endpoints; "" when unknown. */
export function buildLocationParams(
  location: CustomerLocation | null,
  radiusKm: number = DEFAULT_RADIUS_KM,
): string {
  if (!location) return "";
  return `&lat=${location.lat}&lng=${location.lng}&radius_km=${radiusKm}`;
}

/**
 * Remember where the shopper is, so the home rails and the next page they open
 * are already hyperlocal. 30 days is the same lifetime as the location pickers
 * that set it; a shorter one would make the site feel like it keeps forgetting.
 */
export function saveCustomerLocation(location: CustomerLocation): void {
  if (typeof document === "undefined") return;
  const maxAge = 60 * 60 * 24 * 30;
  document.cookie = `${LOCATION_COOKIE}=${encodeURIComponent(
    serializeLocation(location),
  )}; path=/; max-age=${maxAge}; samesite=lax`;
}

export function readCustomerLocation(): CustomerLocation | null {
  if (typeof document === "undefined") return null;
  const prefix = `${LOCATION_COOKIE}=`;
  const match = document.cookie
    .split("; ")
    .find((row) => row.startsWith(prefix));
  if (!match) return null;
  return parseLocationCookie(match.slice(prefix.length));
}
