"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { useForm } from "react-hook-form";
import { z } from "zod";
import { zodResolver } from "@hookform/resolvers/zod";
import { toast } from "sonner";
import { useAuthStore, AuthUser } from "@/store/authStore";

const schema = z.object({
  first_name: z.string().min(2, "First name is required"),
  last_name: z.string().min(2, "Last name is required"),
  email: z.string().email("Enter a valid email"),
  phone: z.string().min(9, "Enter a valid phone number"),
  county: z.string().min(2, "County is required"),
  password: z.string().min(8, "Password must be at least 8 characters"),
  role: z.enum(["buyer", "seller"]),
});

type RegisterForm = z.infer<typeof schema>;

export default function RegisterPage() {
  const router = useRouter();
  const { setUser } = useAuthStore();
  const [loading, setLoading] = useState(false);

  const { register, handleSubmit, watch, setValue, formState: { errors } } = useForm<RegisterForm>({
    resolver: zodResolver(schema),
    defaultValues: { role: "buyer" },
  });

  const role = watch("role");

  async function onSubmit(data: RegisterForm) {
    setLoading(true);
    try {
      const res = await fetch("/api/auth", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ action: "register", ...data }),
      });
      const json = await res.json();
      if (!res.ok) {
        toast.error(json.detail ?? "Registration failed");
        return;
      }
      setUser(json.user as AuthUser);
      toast.success(`Welcome, ${json.user.first_name}!`);
      router.push(data.role === "seller" ? "/dashboard" : "/");
    } catch {
      toast.error("Something went wrong. Try again.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="min-h-screen flex">
      {/* Left panel */}
      <div className="hidden lg:flex w-1/2 bg-navy text-white flex-col justify-between p-12">
        <span className="text-2xl font-bold">
          EK<span className="text-amber">SHOP</span>
        </span>
        <div>
          <h1 className="text-5xl font-bold leading-tight mb-4">
            Join Kenya&apos;s<br />fastest-growing<br />marketplace.
          </h1>
          <p className="text-white/70 text-lg">Buy from thousands of verified sellers — or become one.</p>
        </div>
        <p className="text-sm text-white/50">© {new Date().getFullYear()} Ekshop</p>
      </div>

      {/* Form */}
      <div className="flex-1 flex items-center justify-center px-6 py-12 overflow-y-auto">
        <div className="w-full max-w-sm">
          <h2 className="text-3xl font-bold mb-1">Create account</h2>
          <p className="text-muted text-sm mb-6">
            Already have one?{" "}
            <Link href="/login" className="text-amber underline underline-offset-2">Sign in</Link>
          </p>

          {/* Role toggle */}
          <div className="flex rounded-lg border border-border overflow-hidden mb-6">
            <button
              type="button"
              onClick={() => setValue("role", "buyer")}
              className={`flex-1 py-2 text-sm font-medium transition-colors ${role === "buyer" ? "bg-navy text-white" : "hover:bg-surface"}`}
            >
              I&apos;m a Buyer
            </button>
            <button
              type="button"
              onClick={() => setValue("role", "seller")}
              className={`flex-1 py-2 text-sm font-medium transition-colors border-l border-border ${role === "seller" ? "bg-navy text-white" : "hover:bg-surface"}`}
            >
              I&apos;m a Seller
            </button>
          </div>

          <form onSubmit={handleSubmit(onSubmit)} className="space-y-5">
            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="block text-sm font-medium mb-1">First name</label>
                <input {...register("first_name")} className="input-field" placeholder="John" />
                {errors.first_name && <p className="text-danger text-xs mt-1">{errors.first_name.message}</p>}
              </div>
              <div>
                <label className="block text-sm font-medium mb-1">Last name</label>
                <input {...register("last_name")} className="input-field" placeholder="Kamau" />
                {errors.last_name && <p className="text-danger text-xs mt-1">{errors.last_name.message}</p>}
              </div>
            </div>

            <div>
              <label className="block text-sm font-medium mb-1">Email</label>
              <input type="email" {...register("email")} className="input-field" placeholder="you@example.com" />
              {errors.email && <p className="text-danger text-xs mt-1">{errors.email.message}</p>}
            </div>

            <div>
              <label className="block text-sm font-medium mb-1">Phone</label>
              <input type="tel" {...register("phone")} className="input-field" placeholder="0712 345 678" />
              {errors.phone && <p className="text-danger text-xs mt-1">{errors.phone.message}</p>}
            </div>

            <div>
              <label className="block text-sm font-medium mb-1">County</label>
              <input {...register("county")} className="input-field" placeholder="Nairobi" />
              {errors.county && <p className="text-danger text-xs mt-1">{errors.county.message}</p>}
            </div>

            <div>
              <label className="block text-sm font-medium mb-1">Password</label>
              <input type="password" {...register("password")} className="input-field" placeholder="••••••••" />
              {errors.password && <p className="text-danger text-xs mt-1">{errors.password.message}</p>}
            </div>

            <button
              type="submit"
              disabled={loading}
              className="btn-accent w-full disabled:opacity-50 mt-2"
            >
              {loading ? "Creating account..." : `Create ${role === "seller" ? "seller" : ""} account`}
            </button>
          </form>
        </div>
      </div>
    </div>
  );
}
