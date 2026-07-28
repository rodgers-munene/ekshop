"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { toast } from "sonner";
import { Trash2 } from "lucide-react";
import { Category, Product } from "@/types/interface";
import { resolveImageUrl } from "@/lib/utils";

interface VariantRow {
  name: string;
  value: string;
  price_delta: string;
  stock_qty: string;
  sku: string;
}

function flattenCategories(categories: Category[], depth = 0): { id: string; label: string }[] {
  return categories.flatMap((c) => [
    { id: c.id, label: `${"  ".repeat(depth)}${depth > 0 ? "› " : ""}${c.name}` },
    ...flattenCategories(c.children ?? [], depth + 1),
  ]);
}

function slugify(value: string) {
  return value
    .toLowerCase()
    .trim()
    .replace(/[^a-z0-9\s-]/g, "")
    .replace(/\s+/g, "-");
}

export default function ProductForm({
  mode,
  product,
  categories,
}: {
  mode: "create" | "edit";
  product?: Product;
  categories?: Category[];
}) {
  const router = useRouter();
  const [loading, setLoading] = useState(false);

  const [name, setName] = useState(product?.name ?? "");
  const [slug, setSlug] = useState(product?.slug ?? "");
  const [description, setDescription] = useState(product?.description ?? "");
  const [price, setPrice] = useState(product?.price ?? "");
  const [comparePrice, setComparePrice] = useState(product?.compare_price ?? "");
  const [sku, setSku] = useState(product?.sku ?? "");
  const [stockQty, setStockQty] = useState(String(product?.stock_qty ?? "0"));
  const [condition, setCondition] = useState(product?.condition ?? "new");
  const [status, setStatus] = useState(product?.status ?? "draft");
  const [categoryId, setCategoryId] = useState(product?.category_id ?? "");
  const [tags, setTags] = useState((product?.tags ?? []).join(", "));

  const [variants, setVariants] = useState<VariantRow[]>([]);
  const [pendingImages, setPendingImages] = useState<File[]>([]);
  const [existingImages, setExistingImages] = useState(product?.images ?? []);

  const flatCategories = flattenCategories(categories ?? []);

  function addVariantRow() {
    setVariants((v) => [...v, { name: "", value: "", price_delta: "0.00", stock_qty: "0", sku: "" }]);
  }

  function updateVariantRow(index: number, field: keyof VariantRow, value: string) {
    setVariants((v) => v.map((row, i) => (i === index ? { ...row, [field]: value } : row)));
  }

  function removeVariantRow(index: number) {
    setVariants((v) => v.filter((_, i) => i !== index));
  }

  function addPendingFiles(fileList: FileList | null) {
    if (!fileList || fileList.length === 0) return;
    setPendingImages((imgs) => [...imgs, ...Array.from(fileList)]);
  }

  function removePendingImage(index: number) {
    setPendingImages((imgs) => imgs.filter((_, i) => i !== index));
  }

  async function uploadImage(productId: string, file: File, isPrimary: boolean) {
    const formData = new FormData();
    formData.append("file", file);
    formData.append("is_primary", String(isPrimary));
    const res = await fetch(`/api/dashboard/products/${productId}/images`, {
      method: "POST",
      body: formData,
    });
    if (!res.ok) {
      const data = await res.json().catch(() => ({}));
      toast.error(data.detail ?? `Could not upload ${file.name}`);
    }
  }

  async function removeExistingImage(imageId: string) {
    if (!product) return;
    const res = await fetch(`/api/dashboard/products/${product.id}/images/${imageId}`, { method: "DELETE" });
    if (!res.ok) {
      toast.error("Could not remove image");
      return;
    }
    setExistingImages((imgs) => imgs.filter((img) => img.id !== imageId));
  }

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    setLoading(true);
    try {
      if (mode === "create") {
        const payload = {
          category_id: categoryId || null,
          name,
          slug,
          description: description || null,
          price,
          compare_price: comparePrice || null,
          sku: sku || null,
          stock_qty: Number(stockQty) || 0,
          condition,
          status,
          tags: tags ? tags.split(",").map((t) => t.trim()).filter(Boolean) : null,
          variants: variants.length
            ? variants.map((v) => ({
                name: v.name,
                value: v.value,
                price_delta: v.price_delta || "0.00",
                stock_qty: Number(v.stock_qty) || 0,
                sku: v.sku || null,
              }))
            : null,
        };

        const res = await fetch("/api/dashboard/products", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(payload),
        });
        const created = await res.json().catch(() => ({}));
        if (!res.ok) {
          toast.error(created.detail ?? "Could not create product");
          return;
        }

        for (const [i, file] of pendingImages.entries()) {
          await uploadImage(created.id, file, i === 0);
        }

        toast.success("Product created!");
        router.push("/dashboard/products");
        router.refresh();
      } else if (product) {
        const payload = {
          name,
          description: description || null,
          price,
          compare_price: comparePrice || null,
          stock_qty: Number(stockQty) || 0,
          status,
          tags: tags ? tags.split(",").map((t) => t.trim()).filter(Boolean) : null,
        };

        const res = await fetch(`/api/dashboard/products/${product.slug}`, {
          method: "PATCH",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(payload),
        });
        const updated = await res.json().catch(() => ({}));
        if (!res.ok) {
          toast.error(updated.detail ?? "Could not update product");
          return;
        }

        for (const [i, file] of pendingImages.entries()) {
          await uploadImage(product.id, file, existingImages.length === 0 && i === 0);
        }

        for (const v of variants) {
          if (!v.name || !v.value) continue;
          await fetch(`/api/dashboard/products/${product.id}/variants`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
              name: v.name,
              value: v.value,
              price_delta: v.price_delta || "0.00",
              stock_qty: Number(v.stock_qty) || 0,
              sku: v.sku || null,
            }),
          });
        }

        toast.success("Product updated!");
        router.push("/dashboard/products");
        router.refresh();
      }
    } catch {
      toast.error("Something went wrong. Try again.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <form onSubmit={onSubmit} className="space-y-6 max-w-2xl">
      <div className="card p-5 space-y-4">
        <div>
          <label className="block text-sm font-medium mb-1">Product name</label>
          <input
            className="input-field"
            value={name}
            onChange={(e) => {
              setName(e.target.value);
              if (mode === "create") setSlug(slugify(e.target.value));
            }}
            required
          />
        </div>

        {mode === "create" && (
          <div>
            <label className="block text-sm font-medium mb-1">URL slug</label>
            <input className="input-field" value={slug} onChange={(e) => setSlug(e.target.value)} required />
          </div>
        )}

        <div>
          <label className="block text-sm font-medium mb-1">Description</label>
          <textarea className="input-field" rows={4} value={description} onChange={(e) => setDescription(e.target.value)} />
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          <div>
            <label className="block text-sm font-medium mb-1">Price (KES)</label>
            <input className="input-field" value={price} onChange={(e) => setPrice(e.target.value)} required />
          </div>
          <div>
            <label className="block text-sm font-medium mb-1">Compare-at price</label>
            <input className="input-field" value={comparePrice} onChange={(e) => setComparePrice(e.target.value)} />
          </div>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          <div>
            <label className="block text-sm font-medium mb-1">Stock quantity</label>
            <input type="number" className="input-field" value={stockQty} onChange={(e) => setStockQty(e.target.value)} />
          </div>
          <div>
            <label className="block text-sm font-medium mb-1">Status</label>
            <select className="input-field" value={status} onChange={(e) => setStatus(e.target.value)}>
              <option value="draft">Draft</option>
              <option value="active">Active</option>
              <option value="paused">Paused</option>
            </select>
          </div>
        </div>

        {mode === "create" && (
          <>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <div>
                <label className="block text-sm font-medium mb-1">SKU</label>
                <input className="input-field" value={sku} onChange={(e) => setSku(e.target.value)} />
              </div>
              <div>
                <label className="block text-sm font-medium mb-1">Condition</label>
                <select className="input-field" value={condition} onChange={(e) => setCondition(e.target.value)}>
                  <option value="new">New</option>
                  <option value="used">Used</option>
                  <option value="refurbished">Refurbished</option>
                </select>
              </div>
            </div>

            <div>
              <label className="block text-sm font-medium mb-1">Category</label>
              <select className="input-field" value={categoryId} onChange={(e) => setCategoryId(e.target.value)}>
                <option value="">No category</option>
                {flatCategories.map((c) => (
                  <option key={c.id} value={c.id}>{c.label}</option>
                ))}
              </select>
            </div>
          </>
        )}

        <div>
          <label className="block text-sm font-medium mb-1">Tags (comma separated)</label>
          <input className="input-field" value={tags} onChange={(e) => setTags(e.target.value)} placeholder="handmade, eco-friendly" />
        </div>
      </div>

      {/* Images */}
      <div className="card p-5">
        <h2 className="font-semibold mb-3">Images</h2>
        <p className="text-xs text-muted mb-3">JPEG, PNG or WebP, up to 5MB each. First image is the primary photo.</p>

        {(existingImages.length > 0 || pendingImages.length > 0) && (
          <div className="grid grid-cols-3 sm:grid-cols-4 gap-2 mb-3">
            {existingImages.map((img) => (
              <div key={img.id} className="relative">
                {/* eslint-disable-next-line @next/next/no-img-element */}
                <img src={resolveImageUrl(img.url)} alt="" className="w-full aspect-square object-cover rounded border border-border" />
                <button
                  type="button"
                  onClick={() => removeExistingImage(img.id)}
                  className="absolute top-1 right-1 bg-white/90 rounded-full p-1 shadow-sm"
                >
                  <Trash2 size={12} className="text-danger" />
                </button>
              </div>
            ))}
            {pendingImages.map((file, i) => (
              <div key={i} className="relative">
                {/* eslint-disable-next-line @next/next/no-img-element */}
                <img src={URL.createObjectURL(file)} alt="" className="w-full aspect-square object-cover rounded border border-border" />
                <button
                  type="button"
                  onClick={() => removePendingImage(i)}
                  className="absolute top-1 right-1 bg-white/90 rounded-full p-1 shadow-sm"
                >
                  <Trash2 size={12} className="text-danger" />
                </button>
              </div>
            ))}
          </div>
        )}

        <label className="btn-navy inline-block cursor-pointer">
          Choose images
          <input
            type="file"
            accept="image/jpeg,image/png,image/webp"
            multiple
            className="hidden"
            onChange={(e) => {
              addPendingFiles(e.target.files);
              e.target.value = "";
            }}
          />
        </label>
      </div>

      {/* Variants */}
      <div className="card p-5">
        <h2 className="font-semibold mb-1">Variants</h2>
        <p className="text-xs text-muted mb-3">
          {mode === "edit" && product?.variants?.length
            ? "Existing variants can't be edited yet. Only new ones can be added."
            : "Optional, e.g. size or color."}
        </p>

        {mode === "edit" && product?.variants && product.variants.length > 0 && (
          <ul className="text-sm mb-3 space-y-1">
            {product.variants.map((v) => (
              <li key={v.id} className="bg-surface rounded px-3 py-1.5">
                {v.name}: {v.value} {v.stock_qty ? `(${v.stock_qty} in stock)` : ""}
              </li>
            ))}
          </ul>
        )}

        {variants.map((row, i) => (
          <div key={i} className="grid grid-cols-2 sm:grid-cols-5 gap-2 mb-2 sm:items-center">
            <input className="input-field" placeholder="Name (e.g. Size)" value={row.name} onChange={(e) => updateVariantRow(i, "name", e.target.value)} />
            <input className="input-field" placeholder="Value (e.g. M)" value={row.value} onChange={(e) => updateVariantRow(i, "value", e.target.value)} />
            <input className="input-field" placeholder="Price delta" value={row.price_delta} onChange={(e) => updateVariantRow(i, "price_delta", e.target.value)} />
            <input className="input-field" placeholder="Stock" value={row.stock_qty} onChange={(e) => updateVariantRow(i, "stock_qty", e.target.value)} />
            <button type="button" onClick={() => removeVariantRow(i)} className="col-span-2 sm:col-span-1 text-danger text-xs justify-self-start">
              Remove
            </button>
          </div>
        ))}

        <button type="button" onClick={addVariantRow} className="text-amber text-sm underline underline-offset-2">
          + Add variant
        </button>
      </div>

      <button type="submit" disabled={loading} className="btn-accent disabled:opacity-50">
        {loading ? "Saving..." : mode === "create" ? "Create product" : "Save changes"}
      </button>
    </form>
  );
}
