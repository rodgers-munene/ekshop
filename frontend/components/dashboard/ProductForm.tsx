"use client";

import { useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { toast } from "sonner";
import { ChevronDown, ImagePlus, Loader2, Trash2 } from "lucide-react";
import { Category, Product } from "@/types/interface";
import { resolveImageUrl } from "@/lib/utils";
import { prepareImageForUpload } from "@/lib/image";

interface VariantRow {
  name: string;
  value: string;
  price_delta: string;
  stock_qty: string;
  sku: string;
}

interface PendingImage {
  key: string;
  previewUrl: string;
  name: string;
  /** Resizing starts the moment a photo is picked, so the slow part happens
      while the seller is still typing rather than after they hit save. */
  ready: Promise<File>;
}

// Three at a time keeps a phone connection saturated without putting every
// photo behind one slow request, which is what made a five-photo listing feel
// like it had hung.
const UPLOAD_CONCURRENCY = 3;

function flattenCategories(categories: Category[], depth = 0): { id: string; label: string }[] {
  return categories.flatMap((c) => [
    { id: c.id, label: `${"  ".repeat(depth)}${depth > 0 ? "› " : ""}${c.name}` },
    ...flattenCategories(c.children ?? [], depth + 1),
  ]);
}

/** A collapsed group of fields most listings never need to touch. */
function MoreOptions({ children }: { children: React.ReactNode }) {
  return (
    <details className="card group">
      <summary className="flex items-center justify-between gap-2 p-5 cursor-pointer list-none">
        <div>
          <h2 className="font-semibold">More options</h2>
          <p className="text-xs text-muted mt-0.5">
            Sale price, SKU, condition, tags and variants — all optional.
          </p>
        </div>
        <ChevronDown size={18} className="text-muted shrink-0 transition-transform group-open:rotate-180" />
      </summary>
      <div className="px-5 pb-5 space-y-4 border-t border-border pt-4">{children}</div>
    </details>
  );
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
  const [saving, setSaving] = useState<"active" | "draft" | "edit" | null>(null);
  const [uploadProgress, setUploadProgress] = useState<{ done: number; total: number } | null>(null);

  const [name, setName] = useState(product?.name ?? "");
  const [description, setDescription] = useState(product?.description ?? "");
  const [price, setPrice] = useState(product?.price ?? "");
  const [comparePrice, setComparePrice] = useState(product?.compare_price ?? "");
  const [sku, setSku] = useState(product?.sku ?? "");
  const [stockQty, setStockQty] = useState(String(product?.stock_qty ?? "1"));
  const [condition, setCondition] = useState(product?.condition ?? "new");
  const [status, setStatus] = useState(product?.status ?? "active");
  const [categoryId, setCategoryId] = useState(product?.category_id ?? "");
  const [tags, setTags] = useState((product?.tags ?? []).join(", "));

  const [variants, setVariants] = useState<VariantRow[]>([]);
  const [pendingImages, setPendingImages] = useState<PendingImage[]>([]);
  const [existingImages, setExistingImages] = useState(product?.images ?? []);

  const flatCategories = flattenCategories(categories ?? []);

  // Previews are object URLs; they leak until revoked, and a seller adding and
  // removing photos on a phone can churn through a lot of them.
  const previewUrls = useRef(new Set<string>());
  useEffect(() => {
    const urls = previewUrls.current;
    return () => urls.forEach((url) => URL.revokeObjectURL(url));
  }, []);

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
    const added = Array.from(fileList).map((file, i) => {
      const previewUrl = URL.createObjectURL(file);
      previewUrls.current.add(previewUrl);
      return {
        key: `${Date.now()}-${i}-${file.name}`,
        previewUrl,
        name: file.name,
        ready: prepareImageForUpload(file),
      };
    });
    setPendingImages((imgs) => [...imgs, ...added]);
  }

  function removePendingImage(key: string) {
    setPendingImages((imgs) => {
      const target = imgs.find((img) => img.key === key);
      if (target) {
        URL.revokeObjectURL(target.previewUrl);
        previewUrls.current.delete(target.previewUrl);
      }
      return imgs.filter((img) => img.key !== key);
    });
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
      toast.error(data.detail ? `${file.name}: ${data.detail}` : `Could not upload ${file.name}`);
      return false;
    }
    return true;
  }

  // Uploads every pending image and returns how many failed.
  async function uploadPendingImages(productId: string, hasExistingPrimary: boolean) {
    if (pendingImages.length === 0) return 0;

    setUploadProgress({ done: 0, total: pendingImages.length });
    const files = await Promise.all(pendingImages.map((img) => img.ready));

    let done = 0;
    let failed = 0;
    let index = 0;
    let primaryTaken = hasExistingPrimary;

    function tick() {
      done++;
      setUploadProgress({ done, total: files.length });
    }

    // The primary photo is claimed one at a time so two parallel uploads can't
    // both think they're first — and so a failure on photo 1 doesn't leave the
    // product with no primary image at all.
    while (!primaryTaken && index < files.length) {
      const ok = await uploadImage(productId, files[index], true);
      index++;
      tick();
      if (ok) primaryTaken = true;
      else failed++;
    }

    const queue = files.slice(index);
    let next = 0;
    await Promise.all(
      Array.from({ length: Math.min(UPLOAD_CONCURRENCY, queue.length) }, async () => {
        while (next < queue.length) {
          const file = queue[next++];
          if (!(await uploadImage(productId, file, false))) failed++;
          tick();
        }
      }),
    );

    setUploadProgress(null);
    return failed;
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

  async function submit(intent: "active" | "draft" | "edit") {
    if (!name.trim()) { toast.error("Give the product a name"); return; }
    if (!price.trim()) { toast.error("Set a price"); return; }

    setSaving(intent);
    try {
      if (mode === "create") {
        const payload = {
          category_id: categoryId || null,
          name,
          description: description || null,
          price,
          compare_price: comparePrice || null,
          sku: sku || null,
          stock_qty: Number(stockQty) || 0,
          condition,
          status: intent === "draft" ? "draft" : "active",
          tags: tags ? tags.split(",").map((t) => t.trim()).filter(Boolean) : null,
          variants: variants.length
            ? variants
                .filter((v) => v.name && v.value)
                .map((v) => ({
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

        const failed = await uploadPendingImages(created.id, false);
        if (failed > 0) {
          toast.warning(`Saved, but ${failed} of ${pendingImages.length} photos failed to upload. Edit the product to try again.`);
        } else if (intent === "draft") {
          toast.success("Saved to Drafts — publish it when you're ready.");
        } else {
          toast.success("Product is live!");
        }
        router.push(intent === "draft" ? "/dashboard/products?status=draft" : "/dashboard/products");
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

        const failed = await uploadPendingImages(product.id, existingImages.length > 0);

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

        if (failed > 0) {
          toast.warning(`Updated, but ${failed} of ${pendingImages.length} photos failed to upload.`);
        } else {
          toast.success("Product updated!");
        }
        router.push("/dashboard/products");
        router.refresh();
      }
    } catch {
      toast.error("Something went wrong. Try again.");
    } finally {
      setSaving(null);
      setUploadProgress(null);
    }
  }

  const busy = saving !== null;
  const photoCount = existingImages.length + pendingImages.length;

  return (
    <form
      onSubmit={(e) => {
        e.preventDefault();
        submit(mode === "create" ? "active" : "edit");
      }}
      className="space-y-4 max-w-2xl pb-28"
    >
      {/* Photos first — it's the slow step, and starting it early means the
          resize finishes while the rest of the form is being filled in. */}
      <div className="card p-5">
        <h2 className="font-semibold mb-1">Photos</h2>
        <p className="text-xs text-muted mb-3">
          The first photo is the one buyers see in search. Big photos are shrunk automatically.
        </p>

        <div className="grid grid-cols-3 sm:grid-cols-4 gap-2">
          {existingImages.map((img) => (
            <div key={img.id} className="relative">
              {/* eslint-disable-next-line @next/next/no-img-element */}
              <img src={resolveImageUrl(img.url)} alt="" className="w-full aspect-square object-cover rounded border border-border" />
              <button
                type="button"
                onClick={() => removeExistingImage(img.id)}
                aria-label="Remove photo"
                className="absolute top-1 right-1 bg-white/90 rounded-full p-1 shadow-sm active:scale-90 transition-transform"
              >
                <Trash2 size={12} className="text-danger" />
              </button>
            </div>
          ))}
          {pendingImages.map((img) => (
            <div key={img.key} className="relative">
              {/* eslint-disable-next-line @next/next/no-img-element */}
              <img src={img.previewUrl} alt="" className="w-full aspect-square object-cover rounded border border-border" />
              <button
                type="button"
                onClick={() => removePendingImage(img.key)}
                aria-label="Remove photo"
                className="absolute top-1 right-1 bg-white/90 rounded-full p-1 shadow-sm active:scale-90 transition-transform"
              >
                <Trash2 size={12} className="text-danger" />
              </button>
            </div>
          ))}

          <label className="flex flex-col items-center justify-center gap-1 aspect-square rounded border-2 border-dashed border-border text-muted cursor-pointer hover:border-amber hover:text-amber transition-colors">
            <ImagePlus size={20} />
            <span className="text-[11px] font-medium">Add photo</span>
            <input
              type="file"
              accept="image/*"
              multiple
              className="hidden"
              onChange={(e) => {
                addPendingFiles(e.target.files);
                e.target.value = "";
              }}
            />
          </label>
        </div>

        {photoCount === 0 && (
          <p className="text-xs text-amber mt-3">Listings with photos sell far more — add at least one.</p>
        )}
      </div>

      {/* The four things every listing actually needs. */}
      <div className="card p-5 space-y-4">
        <div>
          <label className="block text-sm font-medium mb-1">What are you selling?</label>
          <input
            className="input-field"
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder="e.g. Smocha + Chips + Soda Combo"
            required
          />
        </div>

        <div className="grid grid-cols-2 gap-4">
          <div>
            <label className="block text-sm font-medium mb-1">Price (KES)</label>
            <input
              className="input-field"
              inputMode="decimal"
              value={price}
              onChange={(e) => setPrice(e.target.value)}
              placeholder="200"
              required
            />
          </div>
          <div>
            <label className="block text-sm font-medium mb-1">How many in stock?</label>
            <input
              type="number"
              inputMode="numeric"
              min={0}
              className="input-field"
              value={stockQty}
              onChange={(e) => setStockQty(e.target.value)}
            />
          </div>
        </div>

        {mode === "create" && (
          <div>
            <label className="block text-sm font-medium mb-1">
              Category <span className="text-muted font-normal">(helps buyers find it)</span>
            </label>
            <select className="input-field" value={categoryId} onChange={(e) => setCategoryId(e.target.value)}>
              <option value="">Choose a category</option>
              {flatCategories.map((c) => (
                <option key={c.id} value={c.id}>{c.label}</option>
              ))}
            </select>
          </div>
        )}

        {mode === "edit" && (
          <div>
            <label className="block text-sm font-medium mb-1">Status</label>
            <select className="input-field" value={status} onChange={(e) => setStatus(e.target.value)}>
              <option value="active">Live — buyers can see it</option>
              <option value="draft">Draft — only you can see it</option>
              <option value="paused">Paused — hidden for now</option>
            </select>
          </div>
        )}
      </div>

      <MoreOptions>
        <div>
          <label className="block text-sm font-medium mb-1">Description</label>
          <textarea
            className="input-field"
            rows={4}
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            placeholder="Size, what's included, delivery notes…"
          />
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          <div>
            <label className="block text-sm font-medium mb-1">Was-price</label>
            <input
              className="input-field"
              inputMode="decimal"
              value={comparePrice}
              onChange={(e) => setComparePrice(e.target.value)}
              placeholder="Shown crossed out"
            />
          </div>
          {mode === "create" && (
            <div>
              <label className="block text-sm font-medium mb-1">Condition</label>
              <select className="input-field" value={condition} onChange={(e) => setCondition(e.target.value)}>
                <option value="new">New</option>
                <option value="used">Used</option>
                <option value="refurbished">Refurbished</option>
              </select>
            </div>
          )}
        </div>

        {mode === "create" && (
          <div>
            <label className="block text-sm font-medium mb-1">SKU</label>
            <input className="input-field" value={sku} onChange={(e) => setSku(e.target.value)} placeholder="Your own stock code" />
          </div>
        )}

        <div>
          <label className="block text-sm font-medium mb-1">Tags (comma separated)</label>
          <input className="input-field" value={tags} onChange={(e) => setTags(e.target.value)} placeholder="handmade, eco-friendly" />
        </div>

        <div className="pt-2 border-t border-border">
          <h3 className="text-sm font-medium mb-1">Variants</h3>
          <p className="text-xs text-muted mb-3">
            {mode === "edit" && product?.variants?.length
              ? "Existing variants can't be edited yet. Only new ones can be added."
              : "Only if the same product comes in sizes or colours."}
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
      </MoreOptions>

      {/* Pinned to the bottom so the save button is always a thumb away, rather
          than behind a scroll past every optional field. */}
      <div className="fixed bottom-0 left-0 right-0 z-20 bg-white/95 backdrop-blur border-t border-border px-4 py-3">
        <div className="max-w-2xl mx-auto flex items-center gap-3">
          <button
            type="submit"
            disabled={busy}
            className="btn-accent flex-1 disabled:opacity-60 disabled:cursor-wait"
          >
            {busy && <Loader2 size={15} className="animate-spin" />}
            {uploadProgress
              ? `Uploading photo ${uploadProgress.done + 1} of ${uploadProgress.total}…`
              : saving
                ? "Saving…"
                : mode === "create"
                  ? "Publish product"
                  : "Save changes"}
          </button>

          {mode === "create" && (
            <button
              type="button"
              disabled={busy}
              onClick={() => submit("draft")}
              className="btn-outline shrink-0 text-sm px-4! disabled:opacity-60"
            >
              Save draft
            </button>
          )}
        </div>
      </div>
    </form>
  );
}
