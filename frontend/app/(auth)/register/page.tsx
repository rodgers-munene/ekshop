"use client";

import { Suspense, useState } from "react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { useForm } from "react-hook-form";
import { useQuery } from "@tanstack/react-query";
import { z } from "zod";
import { zodResolver } from "@hookform/resolvers/zod";
import { toast } from "sonner";
import { getSellerPlan } from "@/lib/plans";
import { isValidKenyanPhone, normalizeKenyanPhone } from "@/lib/phone";
import type { County } from "@/types/interface";

// These mirror app/core/validators.py. Letters, spaces, hyphens, apostrophes
// and periods cover real names (Murang'a, Mary-Anne, initials) while keeping
// out the digits, URLs and random punctuation that bot signups arrive with.
const NAME_RE = /^\p{L}[\p{L} '\-.]*$/u;
const SHOP_NAME_RE = /^[\p{L}\p{N} '\-.,&()/]+$/u;

const nameField = (label: string) =>
  z
    .string()
    .trim()
    .min(2, `${label} must be at least 2 characters`)
    .max(50, `${label} must be at most 50 characters`)
    .regex(NAME_RE, `${label} can only contain letters, spaces, hyphens and apostrophes`);

const schema = z
  .object({
    first_name: nameField("First name"),
    last_name: nameField("Last name"),
    email: z.email("Enter a valid email"),
    phone: z
      .string()
      .trim()
      .refine(isValidKenyanPhone, "Enter a valid Kenyan mobile number, e.g. 0712 345 678"),
    county: z.string().min(1, "Select your county"),
    password: z
      .string()
      .min(8, "Password must be at least 8 characters")
      .max(128, "Password must be at most 128 characters"),
    role: z.enum(["buyer", "seller"]),
    shop_name: z.string().optional(),
  })
  .refine((data) => data.role !== "seller" || !!data.shop_name?.trim(), {
    message: "Shop name is required",
    path: ["shop_name"],
  })
  .refine(
    (data) => {
      if (data.role !== "seller") return true;
      const name = data.shop_name?.trim() ?? "";
      return name.length >= 2 && name.length <= 60 && SHOP_NAME_RE.test(name);
    },
    {
      message: "Shop name must be 2-60 characters, letters and numbers only",
      path: ["shop_name"],
    },
  );

type RegisterForm = z.infer<typeof schema>;

export default function RegisterPage() {
  return (
    <Suspense fallback={null}>
      <RegisterPageInner />
    </Suspense>
  );
}

function RegisterPageInner() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const planCode = searchParams.get("plan");
  const selectedPlan = getSellerPlan(planCode);
  const initialRole = searchParams.get("role") === "seller" && selectedPlan ? "seller" : "buyer";

  const [loading, setLoading] = useState(false);
  const [registeredEmail, setRegisteredEmail] = useState<string | null>(null);

  const { register, handleSubmit, watch, setValue, formState: { errors } } = useForm<RegisterForm>({
    resolver: zodResolver(schema),
    defaultValues: { role: initialRole, county: "" },
  });

  const role = watch("role");

  // The 47 counties come from the counties table, the same source the backend
  // validates against, so the two can't drift apart.
  const { data: counties, isError: countiesFailed } = useQuery({
    queryKey: ["geography", "counties"],
    queryFn: () => fetch("/api/geography/counties").then((r) => r.json()) as Promise<County[]>,
    staleTime: Infinity,
  });

  function handleSellerToggle() {
    if (!selectedPlan) {
      router.push("/register/plan");
      return;
    }
    setValue("role", "seller");
  }

  async function onSubmit(data: RegisterForm) {
    if (data.role === "seller" && !selectedPlan) {
      router.push("/register/plan");
      return;
    }

    setLoading(true);
    try {
      const res = await fetch("/api/auth", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          action: "register",
          ...data,
          phone: normalizeKenyanPhone(data.phone) ?? data.phone,
          plan_code: data.role === "seller" ? selectedPlan?.code : undefined,
        }),
      });
      const json = await res.json();
      if (!res.ok) {
        toast.error(typeof json.detail === "string" ? json.detail : "Registration failed");
        return;
      }
      // Both roles stop here now: sellers verify their email before they can
      // reach payment, so there's no Paystack redirect at this step.
      setRegisteredEmail(data.email);
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
          <p className="text-white/70 text-lg">Buy from thousands of verified sellers, or become one.</p>
        </div>
        <p className="text-sm text-white/50">© {new Date().getFullYear()} Ekshop</p>
      </div>

      {/* Form */}
      <div className="flex-1 flex items-center justify-center px-6 py-12 overflow-y-auto">
        <div className="w-full max-w-sm">
        {registeredEmail ? (
          <>
            <h2 className="text-3xl font-bold mb-2">Check your inbox</h2>
            {role === "seller" ? (
              <p className="text-muted text-sm mb-6">
                We sent a verification link to <strong>{registeredEmail}</strong>. Click it to
                confirm your email, then sign in to confirm your plan and activate your
                shop.
              </p>
            ) : (
              <p className="text-muted text-sm mb-6">
                We sent a verification link to <strong>{registeredEmail}</strong>. Click it to
                activate your account, then sign in.
              </p>
            )}
            <Link href="/login" className="btn-accent inline-block">Go to sign in →</Link>
          </>
        ) : (
        <>
          <h2 className="text-3xl font-bold mb-1">Create account</h2>
          <p className="text-muted text-sm mb-6">
            Already have one?{" "}
            <Link href="/login" className="text-amber underline underline-offset-2">Sign in</Link>
          </p>

          {/* Role toggle */}
          <div className="flex rounded-lg border border-border overflow-hidden mb-3">
            <button
              type="button"
              onClick={() => setValue("role", "buyer")}
              className={`flex-1 py-2 text-sm font-medium transition-colors ${role === "buyer" ? "bg-navy text-white" : "hover:bg-surface"}`}
            >
              I&apos;m a Buyer
            </button>
            <button
              type="button"
              onClick={handleSellerToggle}
              className={`flex-1 py-2 text-sm font-medium transition-colors border-l border-border ${role === "seller" ? "bg-navy text-white" : "hover:bg-surface"}`}
            >
              I&apos;m a Seller
            </button>
          </div>

          {role === "seller" && selectedPlan && (
            <p className="text-xs text-muted mb-6">
              Plan: <strong>{selectedPlan.name}</strong> (KES {selectedPlan.price.toLocaleString()}/month) —{" "}
              <Link href="/register/plan" className="text-amber underline underline-offset-2">change plan</Link>
            </p>
          )}

          <form onSubmit={handleSubmit(onSubmit)} className="space-y-5 mt-6">
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
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

            {role === "seller" && (
              <div>
                <label className="block text-sm font-medium mb-1">Shop name</label>
                <input {...register("shop_name")} className="input-field" placeholder="Mama Njeri Fashions" />
                {errors.shop_name && <p className="text-danger text-xs mt-1">{errors.shop_name.message}</p>}
              </div>
            )}

            <div>
              <label className="block text-sm font-medium mb-1">Email</label>
              <input type="email" {...register("email")} className="input-field" placeholder="you@example.com" />
              {errors.email && <p className="text-danger text-xs mt-1">{errors.email.message}</p>}
            </div>

            <div>
              <label className="block text-sm font-medium mb-1">Phone</label>
              <input type="tel" inputMode="tel" {...register("phone")} className="input-field" placeholder="0712 345 678" />
              {errors.phone ? (
                <p className="text-danger text-xs mt-1">{errors.phone.message}</p>
              ) : (
                <p className="text-muted text-xs mt-1">Safaricom, Airtel or Telkom line. Used for orders and M-Pesa.</p>
              )}
            </div>

            <div>
              <label className="block text-sm font-medium mb-1">County</label>
              <select {...register("county")} className="input-field">
                <option value="" disabled>
                  {counties ? "Select your county" : "Loading counties…"}
                </option>
                {counties?.map((c) => (
                  <option key={c.id} value={c.name}>{c.name}</option>
                ))}
              </select>
              {errors.county && <p className="text-danger text-xs mt-1">{errors.county.message}</p>}
              {countiesFailed && (
                <p className="text-danger text-xs mt-1">
                  Couldn&apos;t load the county list. Refresh the page and try again.
                </p>
              )}
            </div>

            <div>
              <label className="block text-sm font-medium mb-1">Password</label>
              <input type="password" {...register("password")} className="input-field" placeholder="••••••••" />
              {errors.password && <p className="text-danger text-xs mt-1">{errors.password.message}</p>}
            </div>

            <p className="text-xs text-muted">
              By creating an account, you agree to Ekshop&apos;s{" "}
              <Link href="/terms" className="text-amber underline underline-offset-2">Terms of Service</Link> and{" "}
              <Link href="/privacy" className="text-amber underline underline-offset-2">Privacy Policy</Link>.
            </p>

            <button
              type="submit"
              disabled={loading}
              className="btn-accent w-full disabled:opacity-50 mt-2"
            >
              {loading
                ? "Please wait..."
                : role === "seller"
                ? "Verify email to continue"
                : "Create account"}
            </button>
          </form>
        </>
        )}
        </div>
      </div>
    </div>
  );
}
