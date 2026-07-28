"use client";

import { useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { Trash2 } from "lucide-react";
import { HeroSlide } from "@/types/interface";
import { resolveImageUrl } from "@/lib/utils";

export default function AdminHeroSlidesPage() {
  const [file, setFile] = useState<File | null>(null);
  const [title, setTitle] = useState("");
  const [linkUrl, setLinkUrl] = useState("");
  const [sortOrder, setSortOrder] = useState("0");
  const [uploading, setUploading] = useState(false);
  const [sortDrafts, setSortDrafts] = useState<Record<string, string>>({});
  const queryClient = useQueryClient();

  const { data: slides = [], isPending: loading } = useQuery({
    queryKey: ["admin", "hero-slides"],
    queryFn: () =>
      fetch("/api/admin/hero-slides")
        .then((r) => r.json())
        .then((data) => (Array.isArray(data) ? (data as HeroSlide[]) : [])),
  });

  function refresh() {
    queryClient.invalidateQueries({ queryKey: ["admin", "hero-slides"] });
  }

  async function upload(e: React.FormEvent) {
    e.preventDefault();
    if (!file) return;
    setUploading(true);
    try {
      const formData = new FormData();
      formData.append("file", file);
      if (title.trim()) formData.append("title", title.trim());
      if (linkUrl.trim()) formData.append("link_url", linkUrl.trim());
      formData.append("sort_order", sortOrder || "0");

      const res = await fetch("/api/admin/hero-slides", { method: "POST", body: formData });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) { toast.error(data.detail ?? "Could not upload slide"); return; }
      toast.success("Slide uploaded");
      setFile(null);
      setTitle("");
      setLinkUrl("");
      setSortOrder("0");
      (e.target as HTMLFormElement).reset();
      refresh();
    } finally {
      setUploading(false);
    }
  }

  async function toggleActive(slide: HeroSlide) {
    const res = await fetch(`/api/admin/hero-slides/${slide.id}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ is_active: !slide.is_active }),
    });
    if (!res.ok) { toast.error("Could not update slide"); return; }
    refresh();
  }

  async function saveSortOrder(slide: HeroSlide) {
    const value = sortDrafts[slide.id];
    if (value === undefined) return;
    const parsed = parseInt(value, 10);
    if (Number.isNaN(parsed)) { toast.error("Sort order must be a number"); return; }
    const res = await fetch(`/api/admin/hero-slides/${slide.id}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ sort_order: parsed }),
    });
    if (!res.ok) { toast.error("Could not update sort order"); return; }
    toast.success("Sort order updated");
    refresh();
  }

  async function remove(slideId: string) {
    if (!confirm("Delete this hero slide? This removes the image permanently.")) return;
    const res = await fetch(`/api/admin/hero-slides/${slideId}`, { method: "DELETE" });
    if (!res.ok) { toast.error("Could not delete slide"); return; }
    toast.success("Slide deleted");
    refresh();
  }

  return (
    <div>
      <h1 className="text-2xl font-bold mb-2">Hero Slides</h1>
      <p className="text-sm text-muted mb-6">
        Manage the ad images shown in the homepage hero slideshow. Only active slides are shown to visitors.
      </p>

      <form onSubmit={upload} className="card p-4 flex flex-wrap gap-3 items-end mb-6">
        <div>
          <label className="block text-xs font-medium mb-1">Image</label>
          <input
            type="file"
            accept="image/jpeg,image/png,image/webp"
            onChange={(e) => setFile(e.target.files?.[0] ?? null)}
            className="text-sm"
            required
          />
        </div>
        <div className="flex-1 min-w-[160px]">
          <label className="block text-xs font-medium mb-1">Title (optional)</label>
          <input className="input-field" value={title} onChange={(e) => setTitle(e.target.value)} placeholder="Headline shown on this slide" />
        </div>
        <div className="flex-1 min-w-[160px]">
          <label className="block text-xs font-medium mb-1">Link URL (optional)</label>
          <input className="input-field" value={linkUrl} onChange={(e) => setLinkUrl(e.target.value)} placeholder="/products?category=..." />
        </div>
        <div className="w-24">
          <label className="block text-xs font-medium mb-1">Sort order</label>
          <input type="number" className="input-field" value={sortOrder} onChange={(e) => setSortOrder(e.target.value)} />
        </div>
        <button type="submit" disabled={uploading || !file} className="btn-accent disabled:opacity-50">
          {uploading ? "Uploading…" : "Upload slide"}
        </button>
      </form>

      {loading ? (
        <p className="text-muted text-sm">Loading…</p>
      ) : slides.length === 0 ? (
        <div className="card p-10 text-center text-muted text-sm">No hero slides yet. Upload one above.</div>
      ) : (
        <div className="card divide-y divide-border overflow-hidden">
          {slides.map((slide) => (
            <div key={slide.id} className="flex items-center gap-4 p-4 flex-wrap">
              {/* eslint-disable-next-line @next/next/no-img-element */}
              <img
                src={resolveImageUrl(slide.image_url)}
                alt={slide.title ?? ""}
                className="w-24 h-14 object-cover rounded-md bg-surface shrink-0"
              />
              <div className="min-w-0 flex-1">
                <p className="font-medium truncate">{slide.title || "(no title)"}</p>
                <p className="text-xs text-muted truncate">{slide.link_url || "No link"}</p>
              </div>
              <div className="flex items-center gap-2 shrink-0">
                <input
                  type="number"
                  className="input-field w-16 text-sm py-1.5"
                  value={sortDrafts[slide.id] ?? String(slide.sort_order)}
                  onChange={(e) => setSortDrafts((s) => ({ ...s, [slide.id]: e.target.value }))}
                />
                <button onClick={() => saveSortOrder(slide)} className="text-xs py-1.5 px-3 rounded-md border border-border hover:bg-surface">
                  Save
                </button>
                <button onClick={() => toggleActive(slide)} className="text-xs py-1.5 px-3 rounded-md border border-border hover:bg-surface">
                  {slide.is_active ? "Deactivate" : "Activate"}
                </button>
                <button onClick={() => remove(slide.id)} className="p-1.5 rounded-md border border-danger text-danger hover:bg-danger/5">
                  <Trash2 size={14} />
                </button>
              </div>
              {!slide.is_active && (
                <span className="text-[10px] bg-ink/10 text-muted px-2 py-0.5 rounded-full">inactive</span>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
