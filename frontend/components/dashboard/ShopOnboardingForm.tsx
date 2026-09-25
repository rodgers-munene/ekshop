"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { useForm } from "react-hook-form";
import { z } from "zod";
import { zodResolver } from "@hookform/resolvers/zod";
import { toast } from "sonner";
import { Crosshair, MapPin } from "lucide-react";
import LocationPicker from "@/components/geo/LocationPicker";

const schema = z.object({
  name: z.string().min(2, "Shop name is required"),
  slug: z
    .string()
    .min(2, "Slug is required")
    .regex(/^[a-z0-9-]+$/, "Lowercase letters, numbers and hyphens only"),
  description: z.string().optional(),
  county: z.string().min(2, "County is required"),
  town: z.string().optional(),
  phone: z.string().optional(),
  lat: z.number().optional(),
  lng: z.number().optional(),
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
  const [mapOpen, setMapOpen] = useState(false);
  const [detecting, setDetecting] = useState(false);
  const [geoHint, setGeoHint] = useState("");

  const {
    register,
    handleSubmit,
    setValue,
    formState: { errors },
  } = useForm<ShopForm>({ resolver: zodResolver(schema) });

  function applyCounty(sel: { county: string; lat: number; lng: number; addressHint: string }) {
    setValue("county", sel.county, { shouldValidate: true });
    setValue("lat", sel.lat);
    setValue("lng", sel.lng);
    setGeoHint(sel.addressHint);
  }

  function detectLocation() {
    if (!navigator.geolocation) {
      toast.error("Location isn't available on this device. Use the map instead.");
      return;
    }
    setDetecting(true);
    navigator.geolocation.getCurrentPosition(
      async (pos) => {
        setDetecting(false);
        applyCounty({
          county: "",
          lat: pos.coords.latitude,
          lng: pos.coords.longitude,
          addressHint: `${pos.coords.latitude.toFixed(4)}, ${pos.coords.longitude.toFixed(4)}`,
        });
        toast.success("Location detected");
      },
      () => {
        setDetecting(false);
        toast.error("Couldn't get your location. Check browser permission or use the map.");
      },
      { enableHighAccuracy: true, timeout: 10000 }
    );
  }

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

        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          <div>
            <label className="block text-sm font-medium mb-1">County</label>
            <input {...register("county")} className="input-field" placeholder="Nairobi" />
            {errors.county && <p className="text-danger text-xs mt-1">{errors.county.message}</p>}
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

        <div>
          <label className="block text-sm font-medium mb-1">Shop location</label>
          <div className="flex flex-wrap items-center gap-2">
            <button
              type="button"
              onClick={detectLocation}
              disabled={detecting}
              className="flex items-center gap-1.5 rounded-lg border border-border px-3 py-1.5 text-xs font-medium hover:border-amber disabled:opacity-50"
            >
              <Crosshair size={14} className={detecting ? "animate-spin" : ""} />
              {detecting ? "Detecting…" : "Use my location"}
            </button>
            <button
              type="button"
              onClick={() => setMapOpen(true)}
              className="flex items-center gap-1.5 rounded-lg border border-border px-3 py-1.5 text-xs font-medium hover:border-amber"
            >
              <MapPin size={14} />
              Set on map
            </button>
            {geoHint && (
              <span className="text-xs text-ink/70">
                Detected: <strong>{geoHint}</strong>
              </span>
            )}
          </div>
          <input type="hidden" {...register("lat", { valueAsNumber: true })} />
          <input type="hidden" {...register("lng", { valueAsNumber: true })} />
        </div>

        <button type="submit" disabled={loading} className="btn-accent w-full disabled:opacity-50 mt-2">
          {loading ? "Creating shop..." : "Create shop"}
        </button>
      </form>

      {mapOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4" onClick={() => setMapOpen(false)}>
          <div className="w-full max-w-2xl" onClick={(e) => e.stopPropagation()}>
            <p className="mb-2 text-center text-sm font-medium text-white">
              Drop the pin where your shop is located
            </p>
            <LocationPicker
              onCancel={() => setMapOpen(false)}
              onConfirm={(sel) => {
                applyCounty(sel);
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
