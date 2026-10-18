"use client";

import { Crosshair } from "lucide-react";
import { saveCustomerLocation } from "@/lib/geo-location";

/**
 * "Use my location" on the product feed.
 *
 * This has to be a Client Component: it reads `navigator.geolocation` and needs an
 * click handler, neither of which a Server Component can do. It previously lived
 * inline in the products page (a Server Component), where React refused to
 * serialise the `onClick` -- the button was inert and the page logged
 * "Event handlers cannot be passed to Client Component props" on every load.
 *
 * Granting permission is also the shopper telling us where they are, so the
 * coordinate is stored in a cookie: the feed applies it now, and the home rails
 * and the next page open already hyperlocal.
 */
export default function NearMeButton({
  radiusKm,
}: {
  radiusKm?: number;
}) {
  function useMyLocation() {
    if (!navigator.geolocation) {
      alert("Geolocation is not supported by your browser");
      return;
    }
    navigator.geolocation.getCurrentPosition(
      (pos) => {
        const { latitude, longitude } = pos.coords;
        saveCustomerLocation({ lat: latitude, lng: longitude });
        const params = new URLSearchParams(window.location.search);
        params.set("lat", String(latitude));
        params.set("lng", String(longitude));
        if (radiusKm) params.set("radius_km", String(radiusKm));
        window.location.search = params.toString();
      },
      () => {
        alert("Couldn't get your location. Check browser permissions.");
      },
      { enableHighAccuracy: true, timeout: 10000 },
    );
  }

  return (
    <button
      type="button"
      onClick={useMyLocation}
      className="w-full flex items-center justify-center gap-2 text-xs py-2 px-3 rounded-md border border-border hover:border-amber transition-colors"
    >
      <Crosshair size={14} />
      Use my location
    </button>
  );
}
