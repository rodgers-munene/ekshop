"use client";

import { Crosshair } from "lucide-react";

// Reloads /products with the browser's coordinates so the page can list nearby shops.
export default function NearMeButton() {
  return (
    <button
      type="button"
      onClick={() => {
        if (!navigator.geolocation) {
          alert("Geolocation is not supported by your browser");
          return;
        }
        navigator.geolocation.getCurrentPosition(
          (pos) => {
            const params = new URLSearchParams(window.location.search);
            params.set("lat", String(pos.coords.latitude));
            params.set("lng", String(pos.coords.longitude));
            window.location.search = params.toString();
          },
          () => {
            alert("Couldn't get your location. Check browser permissions.");
          },
          { enableHighAccuracy: true, timeout: 10000 }
        );
      }}
      className="w-full flex items-center justify-center gap-2 text-xs py-2 px-3 rounded-md border border-border hover:border-amber transition-colors"
    >
      <Crosshair size={14} />
      Use my location
    </button>
  );
}
