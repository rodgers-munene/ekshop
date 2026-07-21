"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { toast } from "sonner";
import { Shop } from "@/types/interface";

export default function ShopSettingsForm({ shop }: { shop: Shop }) {
  const router = useRouter();
  const [loading, setLoading] = useState(false);
  const [name, setName] = useState(shop.name);
  const [description, setDescription] = useState(shop.description ?? "");
  const [county, setCounty] = useState(shop.county ?? "");
  const [logoUrl, setLogoUrl] = useState(shop.logo_url ?? "");
  const [bannerUrl, setBannerUrl] = useState(shop.banner_url ?? "");

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
          logo_url: logoUrl || null,
          banner_url: bannerUrl || null,
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
      <div>
        <label className="block text-sm font-medium mb-1">County</label>
        <input className="input-field" value={county} onChange={(e) => setCounty(e.target.value)} />
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
