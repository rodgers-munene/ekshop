"use client";

import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { Shop, ShopUpdate } from "@/types/interface";
import LocationPicker from "@/components/geo/LocationPicker";

type ShopLocationForm = Pick<ShopUpdate, "lat" | "lng" | "county" | "town" | "exact_location">;

export default function AdminShopLocationPage({ params }: { params: Promise<{ shopId: string }> }) {
  const queryClient = useQueryClient();
  const [mapOpen, setMapOpen] = useState(false);
  const [detecting, setDetecting] = useState(false);
  const [geoHint, setGeoHint] = useState("");
  const { shopId } = use(params);

  const { data: shop, isLoading } = useQuery<Shop | null>({
    queryKey: ["admin", "shop", shopId],
    queryFn: () =>
      fetch(`/api/admin/shops/${shopId}`)
        .then((r) => r.json())
        .catch(() => null),
    enabled: !!shopId,
  });

  const updateMutation = useMutation({
    mutationFn: async (data: ShopLocationForm) => {
      const res = await fetch(`/api/admin/shops/${shopId}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(data),
      });
      const json = await res.json().catch(() => ({}));
      if (!res.ok) throw new Error(json.detail ?? "Failed to update location");
      return json;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["admin", "shop", shopId] });
      queryClient.invalidateQueries({ queryKey: ["admin", "shops"] });
      toast.success("Shop location updated");
    },
    onError: (e: Error) => toast.error(e.message),
  });

  const [formData, setFormData] = useState<ShopLocationForm>({
    lat: shop?.lat ?? 0,
    lng: shop?.lng ?? 0,
    county: shop?.county ?? "",
    town: shop?.town ?? "",
    exact_location: shop?.exact_location ?? "",
  });

  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-20">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-amber" />
      </div>
    );
  }

  if (!shop) {
    return (
      <div className="card flex flex-col items-center justify-center py-20 text-center">
        <p className="font-bold mb-1">Shop not found</p>
      </div>
    );
  }

  function applyLocation(sel: { lat: number; lng: number; county?: string; subcounty?: string; ward?: string; location?: string; sublocation?: string; addressHint?: string; countyId?: string; subcountyId?: string; wardId?: string }) {
    setFormData((prev) => ({
      ...prev,
      lat: sel.lat,
      lng: sel.lng,
      county: sel.county ?? prev.county,
      town: sel.subcounty ?? prev.town,
      exact_location: sel.addressHint ?? prev.exact_location,
    }));
    setGeoHint(sel.addressHint ?? "");
  }

  function detectLocation() {
    if (!navigator.geolocation) {
      toast.error("Location isn't available on this device. Use the map instead.");
      return;
    }
    if (typeof window !== "undefined" && window.location.protocol !== "https:" && window.location.hostname !== "localhost") {
      toast.error("Location requires HTTPS. Use the map instead.");
      return;
    }
    setDetecting(true);
    navigator.geolocation.getCurrentPosition(
      async (pos) => {
        try {
          setDetecting(false);
          setFormData((prev) => ({
            ...prev,
            lat: pos.coords.latitude,
            lng: pos.coords.longitude,
            exact_location: `${pos.coords.latitude.toFixed(4)}, ${pos.coords.longitude.toFixed(4)}`,
          }));
          setGeoHint(`${pos.coords.latitude.toFixed(4)}, ${pos.coords.longitude.toFixed(4)}`);
          toast.success("Location detected");
        } catch {
          setDetecting(false);
          toast.error("Location service error. Try the map instead.");
        }
      },
      (err) => {
        setDetecting(false);
        if (err.code === err.PERMISSION_DENIED) {
          toast.error("Location permission denied. Enable in browser settings or use the map.");
        } else if (err.code === err.POSITION_UNAVAILABLE) {
          toast.error("Location unavailable. Try the map instead.");
        } else if (err.code === err.TIMEOUT) {
          toast.error("Location request timed out. Try the map.");
        } else {
          toast.error("Couldn't get your location. Check browser permission or use the map.");
        }
      },
      { enableHighAccuracy: true, timeout: 10000, maximumAge: 0 }
    );
  }

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    updateMutation.mutate(formData);
  }

  return (
    <div className="card w-full max-w-2xl p-6">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-xl font-bold">Edit shop location</h1>
          <p className="text-sm text-muted">{shop.name} &bull; {shop.slug}</p>
        </div>
      </div>

      <form onSubmit={handleSubmit} className="space-y-5">
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          <div>
            <label className="block text-sm font-medium mb-1">County</label>
            <input
              value={formData.county}
              onChange={(e) => setFormData((prev) => ({ ...prev, county: e.target.value }))}
              className="input-field"
              placeholder="Nairobi"
            />
          </div>
          <div>
            <label className="block text-sm font-medium mb-1">Town</label>
            <input
              value={formData.town}
              onChange={(e) => setFormData((prev) => ({ ...prev, town: e.target.value }))}
              className="input-field"
              placeholder="Westlands"
            />
          </div>
        </div>

        <div>
          <label className="block text-sm font-medium mb-1">Exact location</label>
          <input
            value={formData.exact_location}
            onChange={(e) => setFormData((prev) => ({ ...prev, exact_location: e.target.value }))}
            className="input-field"
            placeholder="Landmark, building, floor, etc."
          />
        </div>

        <div>
          <label className="block text-sm font-medium mb-1">Coordinates <span className="text-danger">*</span></label>
          <div className="flex flex-wrap items-center gap-2">
            <button
              type="button"
              onClick={detectLocation}
              disabled={detecting}
              className="flex items-center gap-1.5 rounded-lg border border-border px-3 py-1.5 text-xs font-medium hover:border-amber disabled:opacity-50"
            >
              <span className={detecting ? "animate-spin" : ""}>📍</span>
              {detecting ? "Detecting..." : "Use my location"}
            </button>
            <button
              type="button"
              onClick={() => setMapOpen(true)}
              className="flex items-center gap-1.5 rounded-lg border border-border px-3 py-1.5 text-xs font-medium hover:border-amber"
            >
              📍 Set on map
            </button>
            {geoHint && (
              <span className="text-xs text-ink/70">
                Detected: <strong>{geoHint}</strong>
              </span>
            )}
          </div>
        </div>

        <div className="grid grid-cols-2 gap-3">
          <div>
            <label className="block text-xs text-muted mb-1">Latitude</label>
            <input
              type="number"
              step="any"
              value={formData.lat}
              onChange={(e) => setFormData((prev) => ({ ...prev, lat: parseFloat(e.target.value) || 0 }))}
              className="input-field"
              placeholder="-1.286"
              required
            />
          </div>
          <div>
            <label className="block text-xs text-muted mb-1">Longitude</label>
            <input
              type="number"
              step="any"
              value={formData.lng}
              onChange={(e) => setFormData((prev) => ({ ...prev, lng: parseFloat(e.target.value) || 0 }))}
              className="input-field"
              placeholder="36.817"
              required
            />
          </div>
        </div>

        <div className="flex gap-3 pt-4">
          <button type="submit" disabled={updateMutation.isPending} className="btn-accent flex-1 disabled:opacity-50">
            {updateMutation.isPending ? "Saving..." : "Save location"}
          </button>
          <button type="button" onClick={() => setMapOpen(true)} className="btn-navy flex-1">
            Set on map
          </button>
        </div>
      </form>

      {mapOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4" onClick={() => setMapOpen(false)}>
          <div className="w-full max-w-2xl" onClick={(e) => e.stopPropagation()}>
            <p className="mb-2 text-center text-sm font-medium text-white">
              Drop the pin where the shop is located
            </p>
            <LocationPicker
              initial={{ lat: formData.lat, lng: formData.lng }}
              onCancel={() => setMapOpen(false)}
              onConfirm={(sel) => {
                setFormData((prev) => ({
                  ...prev,
                  lat: sel.lat,
                  lng: sel.lng,
                  county: sel.county ?? prev.county,
                  town: sel.subcounty ?? prev.town,
                  exact_location: sel.addressHint ?? prev.exact_location,
                }));
                setGeoHint(sel.addressHint ?? "");
                setMapOpen(false);
                toast.success("Location set");
              }}
            />
          </div>
        </div>
      )}
    </div>
  );
}