"use client";

import { useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { Trash2, Upload } from "lucide-react";
import { PaginatedResponse, Category } from "@/types/interface";
import Pagination from "@/components/admin/Pagination";
import { resolveImageUrl } from "@/lib/utils";

const LIMIT = 20;

function slugify(value: string) {
  return value.toLowerCase().trim().replace(/[^a-z0-9\s-]/g, "").replace(/\s+/g, "-");
}

export default function AdminCategoriesPage() {
  const [name, setName] = useState("");
  const [parentId, setParentId] = useState("");
  const [saving, setSaving] = useState(false);
  const [page, setPage] = useState(1);
  const [uploadingIconFor, setUploadingIconFor] = useState<string | null>(null);
  const queryClient = useQueryClient();

  const { data, isPending: loading } = useQuery({
    queryKey: ["admin", "categories", page],
    queryFn: () =>
      fetch(`/api/admin/categories?page=${page}&limit=${LIMIT}`)
        .then((r) => r.json())
        .then((data): PaginatedResponse<Category> =>
          data && Array.isArray(data.results) ? data : { total: 0, page: 1, limit: LIMIT, results: [] }
        ),
  });
  const categories = data?.results ?? [];
  const totalPages = Math.max(1, Math.ceil((data?.total ?? 0) / LIMIT));

  function refresh() {
    queryClient.invalidateQueries({ queryKey: ["admin", "categories", page] });
  }

  async function createCategory(e: React.FormEvent) {
    e.preventDefault();
    if (!name.trim()) return;
    setSaving(true);
    try {
      const res = await fetch("/api/admin/categories", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name: name.trim(), slug: slugify(name), parent_id: parentId || null }),
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) { toast.error(data.detail ?? "Could not create category"); return; }
      toast.success("Category created");
      setName("");
      setParentId("");
      refresh();
    } finally {
      setSaving(false);
    }
  }

  async function toggleActive(cat: Category) {
    const res = await fetch(`/api/admin/categories/${cat.id}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ is_active: !cat.is_active }),
    });
    if (!res.ok) { toast.error("Could not update category"); return; }
    refresh();
  }

  async function uploadIcon(catId: string, file: File) {
    setUploadingIconFor(catId);
    try {
      const formData = new FormData();
      formData.append("file", file);
      const res = await fetch(`/api/admin/categories/${catId}/icon`, { method: "POST", body: formData });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) { toast.error(data.detail ?? "Could not upload icon"); return; }
      toast.success("Icon updated");
      refresh();
    } finally {
      setUploadingIconFor(null);
    }
  }

  async function remove(catId: string) {
    if (!confirm("Delete this category? Products in it will become uncategorized.")) return;
    const res = await fetch(`/api/admin/categories/${catId}`, { method: "DELETE" });
    if (!res.ok) { toast.error("Could not delete category"); return; }
    toast.success("Category deleted");
    refresh();
  }

  const topLevel = categories;

  return (
    <div>
      <h1 className="text-2xl font-bold mb-6">Categories</h1>

      <form onSubmit={createCategory} className="card p-4 flex flex-wrap gap-2 items-end mb-6">
        <div className="flex-1 min-w-[200px]">
          <label className="block text-xs font-medium mb-1">New category name</label>
          <input className="input-field" value={name} onChange={(e) => setName(e.target.value)} placeholder="e.g. Electronics" />
        </div>
        <div className="flex-1 min-w-[200px]">
          <label className="block text-xs font-medium mb-1">Parent (optional)</label>
          <select className="input-field" value={parentId} onChange={(e) => setParentId(e.target.value)}>
            <option value="">No parent (top level)</option>
            {topLevel.map((c) => (
              <option key={c.id} value={c.id}>{c.name}</option>
            ))}
          </select>
        </div>
        <button type="submit" disabled={saving || !name.trim()} className="btn-accent disabled:opacity-50">
          {saving ? "Adding…" : "Add category"}
        </button>
      </form>

      {loading ? (
        <p className="text-muted text-sm">Loading…</p>
      ) : (
        <div className="card divide-y divide-border overflow-hidden">
          {topLevel.map((cat) => (
            <div key={cat.id}>
              <div className="flex items-center justify-between gap-4 p-4">
                <div className="flex items-center gap-3">
                  <div className="w-10 h-10 rounded-md bg-surface border border-border overflow-hidden shrink-0">
                    {cat.icon_url && (
                      // eslint-disable-next-line @next/next/no-img-element
                      <img src={resolveImageUrl(cat.icon_url)} alt="" className="w-full h-full object-cover" />
                    )}
                  </div>
                  <p className="font-medium">{cat.name}</p>
                  {!cat.is_active && <span className="text-[10px] bg-ink/10 text-muted px-2 py-0.5 rounded-full">inactive</span>}
                </div>
                <div className="flex gap-2 shrink-0">
                  <label className="text-xs py-1.5 px-3 rounded-md border border-border hover:bg-surface cursor-pointer flex items-center gap-1">
                    <Upload size={12} />
                    {uploadingIconFor === cat.id ? "Uploading…" : "Icon"}
                    <input
                      type="file"
                      accept="image/jpeg,image/png,image/webp"
                      className="hidden"
                      disabled={uploadingIconFor === cat.id}
                      onChange={(e) => {
                        const file = e.target.files?.[0];
                        e.target.value = "";
                        if (file) uploadIcon(cat.id, file);
                      }}
                    />
                  </label>
                  <button onClick={() => toggleActive(cat)} className="text-xs py-1.5 px-3 rounded-md border border-border hover:bg-surface">
                    {cat.is_active ? "Deactivate" : "Activate"}
                  </button>
                  <button onClick={() => remove(cat.id)} className="p-1.5 rounded-md border border-danger text-danger hover:bg-danger/5">
                    <Trash2 size={14} />
                  </button>
                </div>
              </div>
              {cat.children && cat.children.length > 0 && (
                <div className="pl-8 pb-2 space-y-1">
                  {cat.children.map((child) => (
                    <div key={child.id} className="flex items-center justify-between gap-4 py-1.5 pr-4 text-sm">
                      <div className="flex items-center gap-2 min-w-0">
                        <div className="w-7 h-7 rounded-md bg-surface border border-border overflow-hidden shrink-0">
                          {child.icon_url && (
                            // eslint-disable-next-line @next/next/no-img-element
                            <img src={resolveImageUrl(child.icon_url)} alt="" className="w-full h-full object-cover" />
                          )}
                        </div>
                        <span className="text-muted truncate">› {child.name}</span>
                      </div>
                      <div className="flex items-center gap-2 shrink-0">
                        <label className="text-xs py-1 px-2 rounded-md border border-border hover:bg-surface cursor-pointer flex items-center gap-1">
                          <Upload size={11} />
                          {uploadingIconFor === child.id ? "…" : "Icon"}
                          <input
                            type="file"
                            accept="image/jpeg,image/png,image/webp"
                            className="hidden"
                            disabled={uploadingIconFor === child.id}
                            onChange={(e) => {
                              const file = e.target.files?.[0];
                              e.target.value = "";
                              if (file) uploadIcon(child.id, file);
                            }}
                          />
                        </label>
                        <button onClick={() => remove(child.id)} className="p-1 rounded-md border border-danger text-danger hover:bg-danger/5">
                          <Trash2 size={12} />
                        </button>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          ))}
          {topLevel.length === 0 && (
            <div className="p-10 text-center text-muted text-sm">No categories yet.</div>
          )}
        </div>
      )}
      <Pagination page={page} totalPages={totalPages} onPageChange={setPage} />
    </div>
  );
}
