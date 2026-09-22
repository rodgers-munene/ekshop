"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { toast } from "sonner";
import { Shop } from "@/types/interface";
import LocationPicker from "@/components/geo/LocationPicker";

export default function ShopSettingsForm({ shop }: { shop: Shop }) {
  const router = useRouter();
  const [loading, setLoading] = useState(false);
  const [name, setName] = useState(shop.name);
  const [description, setDescription] = useState(shop.description ?? "");
  const [county, setCounty] = useState(shop.county ?? "");
  const [town, setTown] = useState(shop.town ?? "");
  const [phone, setPhone] = useState(shop.phone ?? "");
  const [exactLocation, setExactLocation] = useState(shop.exact_location ?? "");
  const [logoUrl, setLogoUrl] = useState(shop.logo_url ?? "");
  const [bannerUrl, setBannerUrl] = useState(shop.banner_url ?? "");
  const [lat, setLat] = useState<number | undefined>(shop.lat ?? undefined);
  const [lng, setLng] = useState<number | undefined>(shop.lng ?? undefined);
  const [mapOpen, setMapOpen] = useState(false);

  function applyLocation(sel: { lat: number; lng: number; county: string; addressHint: string }) {
    setLat(sel.lat);
    setLng(sel.lng);
    if (sel.county) setCounty(sel.county);
    if (!exactLocation && sel.addressHint) setExactLocation(sel.addressHint);
  }

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    setLoading(true);
    try {
      const res = await fetch("/api/dashboard/shop", {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          name,
          description: description || null,
          county: county || null,
          town: town || null,
          phone: phone || null,
          exact_location: exactLocation || null,
          logo_url: logoUrl || null,
          banner_url: bannerUrl || null,
          lat,
          lng,
        }),
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) {
        toast.error(data.detail ?? "Could not save changes");
        return;
      }
      toast.success("Shop updated!");
      router.refresh();
    } catch {
      toast.error("Something went wrong. Try again.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <form onSubmit={onSubmit} className="card p-5 space-y-4 max-w-lg">
      <div>
        <label className="block text-sm font-medium mb-1">Shop name</label>
        <input className="input-field" value={name} onChange={(e) => setName(e.target.value)} required />
      </div>
      <div>
        <label className="block text-sm font-medium mb-1">Description</label>
        <textarea className="input-field" rows={3} value={description} onChange={(e) => setDescription(e.target.value)} />
      </div>
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
        <div>
          <label className="block text-sm font-medium mb-1">County</label>
          <input className="input-field" value={county} onChange={(e) => setCounty(e.target.value)} />
        </div>
        <div>
          <label className="block text-sm font-medium mb-1">Town</label>
          <input className="input-field" value={town} onChange={(e) => setTown(e.target.value)} />
        </div>
      </div>
      <div>
        <label className="block text-sm font-medium mb-1">Phone</label>
        <input className="input-field" value={phone} onChange={(e) => setPhone(e.target.value)} placeholder="e.g. 0712 345 678" />
      </div>
      <div>
        <label className="block text-sm font-medium mb-1">Exact location / landmark</label>
        <input className="input-field" value={exactLocation} onChange={(e) => setExactLocation(e.target.value)} placeholder="e.g. Near Naivas, Kimathi Street" />
      </div>
      <div>
        <label className="block text-sm font-medium mb-1">Location</label>
        <button type="button" onClick={() => setMapOpen((o) => !o)} className="btn-navy text-xs py-1.5 px-3">
          {mapOpen ? "Close map" : (lat && lng ? "Update location" : "Pick location")}
        </button>
        {mapOpen && (
          <div className="mt-2">
            <LocationPicker
              initial={lat && lng ? { lat, lng } : undefined}
              onConfirm={(sel) => {
                applyLocation(sel);
                setMapOpen(false);
                toast.success("Location saved");
              }}
              onCancel={() => setMapOpen(false)}
            />
          </div>
        )}
        {lat != null && lng != null && (
          <p className="text-xs text-muted mt-1">Lat: {lat.toFixed(5)}, Lng: {lng.toFixed(5)}</p>
        )}
      </div>
      <div>
        <label className="block text-sm font-medium mb-1">Logo URL</label>
        <input className="input-field" value={logoUrl} onChange={(e) => setLogoUrl(e.target.value)} placeholder="https://example.com/logo.png" />
      </div>
      <div>
        <label className="block text-sm font-medium mb-1">Banner URL</label>
        <input className="input-field" value={bannerUrl} onChange={(e) => setBannerUrl(e.target.value)} placeholder="https://example.com/banner.jpg" />
      </div>
      <button type="submit" disabled={loading} className="btn-accent disabled:opacity-50">
        {loading ? "Saving..." : "Save changes"}
      </button>
    </form>
  );
}
