"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { useForm } from "react-hook-form";
import { z } from "zod";
import { zodResolver } from "@hookform/resolvers/zod";
import { toast } from "sonner";

const schema = z.object({
  name: z.string().min(2, "Shop name is required"),
  slug: z
    .string()
    .min(2, "Slug is required")
    .regex(/^[a-z0-9-]+$/, "Lowercase letters, numbers and hyphens only"),
  description: z.string().optional(),
  county: z.string().optional(),
  town: z.string().optional(),
  phone: z.string().optional(),
});

type ShopForm = z.infer<typeof schema>;

function slugify(value: string) {
  return value
    .toLowerCase()
    .trim()
    .replace(/[^a-z0-9\s-]/g, "")
    .replace(/\s+/g, "-");
}

export default function ShopOnboardingForm() {
  const router = useRouter();
  const [loading, setLoading] = useState(false);

  const {
    register,
    handleSubmit,
    setValue,
    formState: { errors },
  } = useForm<ShopForm>({ resolver: zodResolver(schema) });

  async function onSubmit(data: ShopForm) {
    setLoading(true);
    try {
      const res = await fetch("/api/dashboard/shop", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(data),
      });
      const json = await res.json().catch(() => ({}));
      if (!res.ok) {
        toast.error(json.detail ?? "Could not create shop");
        return;
      }
      toast.success("Shop created!");
      router.refresh();
    } catch {
      toast.error("Something went wrong. Try again.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="card w-full max-w-md p-6">
      <h1 className="text-xl font-bold mb-1">Set up your shop</h1>
      <p className="text-muted text-sm mb-6">You need a shop before you can access the seller dashboard.</p>

      <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
        <div>
          <label className="block text-sm font-medium mb-1">Shop name</label>
          <input
            {...register("name", {
              onChange: (e) => setValue("slug", slugify(e.target.value)),
            })}
            className="input-field"
            placeholder="Mama Njeri's Boutique"
          />
          {errors.name && <p className="text-danger text-xs mt-1">{errors.name.message}</p>}
        </div>

        <div>
          <label className="block text-sm font-medium mb-1">Shop URL</label>
          <input {...register("slug")} className="input-field" placeholder="mama-njeris-boutique" />
          {errors.slug && <p className="text-danger text-xs mt-1">{errors.slug.message}</p>}
        </div>

        <div>
          <label className="block text-sm font-medium mb-1">Description</label>
          <textarea {...register("description")} className="input-field" rows={3} placeholder="What do you sell?" />
        </div>

        <div className="grid grid-cols-2 gap-4">
          <div>
            <label className="block text-sm font-medium mb-1">County</label>
            <input {...register("county")} className="input-field" placeholder="Nairobi" />
          </div>
          <div>
            <label className="block text-sm font-medium mb-1">Town</label>
            <input {...register("town")} className="input-field" placeholder="Westlands" />
          </div>
        </div>

        <div>
          <label className="block text-sm font-medium mb-1">Phone</label>
          <input type="tel" {...register("phone")} className="input-field" placeholder="0712 345 678" />
        </div>

        <button type="submit" disabled={loading} className="btn-accent w-full disabled:opacity-50 mt-2">
          {loading ? "Creating shop..." : "Create shop"}
        </button>
      </form>
    </div>
  );
}
