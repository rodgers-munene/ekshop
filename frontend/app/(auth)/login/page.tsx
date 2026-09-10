"use client";

import { Suspense, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import Link from "next/link";
import { useForm } from "react-hook-form";
import { z } from "zod";
import { zodResolver } from "@hookform/resolvers/zod";
import { toast } from "sonner";
import { useAuthStore } from "@/store/authStore";
import { AuthUser } from "@/store/authStore";

const loginSchema = z.object({
  email: z.string().email("Enter a valid email"),
  password: z.string().min(6, "Password must be at least 6 characters"),
});

type LoginForm = z.infer<typeof loginSchema>;

function LoginPageInner() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const { setUser } = useAuthStore();
  const [loading, setLoading] = useState(false);
  const [resumingPayment, setResumingPayment] = useState(false);
  // Set when login reports the account is unverified, so we can offer a fresh
  // link — verification tokens expire after 24 hours, and for a seller that
  // link is the only route to payment.
  const [unverifiedEmail, setUnverifiedEmail] = useState<string | null>(null);
  const [resending, setResending] = useState(false);

  const {
    register,
    handleSubmit,
    formState: { errors },
  } = useForm<LoginForm>({
    resolver: zodResolver(loginSchema),
  });

  async function resumeSellerPayment(reference: string) {
    setResumingPayment(true);
    try {
      const res = await fetch("/api/paystack/subscription-status", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ reference }),
      });
      const data = await res.json();
      if (res.ok && data.authorization_url) {
        window.location.href = data.authorization_url;
        return;
      }
      toast.error(data.detail ?? "Couldn't resume your payment. Please try registering again or contact support.");
    } catch {
      toast.error("Couldn't resume your payment. Please try registering again or contact support.");
    } finally {
      setResumingPayment(false);
    }
  }

  async function resendVerification(email: string) {
    setResending(true);
    try {
      const res = await fetch("/api/auth", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ action: "resend-verification", email }),
      });
      const data = await res.json().catch(() => ({}));
      toast.success(data.message ?? "If that account still needs verifying, we've sent a new link");
    } catch {
      toast.error("Couldn't send a new link. Try again in a moment.");
    } finally {
      setResending(false);
    }
  }

  async function onSubmit(data: LoginForm) {
    setLoading(true);
    setUnverifiedEmail(null);
    try {
      const res = await fetch("/api/auth", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ action: "login", ...data }),
      });

      const json = await res.json();

      if (!res.ok) {
        const detail = json.detail;
        if (detail && typeof detail === "object" && detail.code === "seller_payment_pending") {
          if (detail.reference) {
            toast.message("Taking you back to complete your registration payment…");
            await resumeSellerPayment(detail.reference);
          } else {
            toast.error(detail.message ?? "Your registration payment hasn't been confirmed yet.");
          }
          return;
        }
        if (typeof detail === "string" && detail.toLowerCase().includes("verify your email")) {
          setUnverifiedEmail(data.email);
          toast.error(detail);
          return;
        }
        toast.error(typeof detail === "string" ? detail : "Login failed");
        return;
      }

      setUser(json.user as AuthUser);
      toast.success(`Welcome back, ${json.user.first_name}!`);

      const next = searchParams.get("next");
      if (next) {
        router.push(next);
      } else if (json.user.role === "seller" || json.user.role === "admin") {
        router.push("/dashboard");
      } else {
        router.push("/");
      }
    } catch {
      toast.error("Something went wrong. Try again.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="min-h-screen flex">

      {/* Left: decorative panel */}
      <div className="hidden lg:flex w-1/2 bg-navy text-white flex-col justify-between p-12">
        <span className="text-2xl font-bold">
          EK<span className="text-amber">SHOP</span>
        </span>
        <div>
          <h1 className="text-5xl font-bold leading-tight mb-4">
            Kenya&apos;s marketplace,<br />at your fingertips.
          </h1>
          <p className="text-white/70 text-lg">
            Thousands of sellers. One seamless experience.
          </p>
        </div>
        <p className="text-sm text-white/50">© {new Date().getFullYear()} Ekshop</p>
      </div>

      {/* Right: form */}
      <div className="flex-1 flex items-center justify-center px-6 py-12">
        <div className="w-full max-w-sm">
          <h2 className="text-3xl font-bold mb-1">Sign in</h2>
          <p className="text-muted text-sm mb-8">
            Don&apos;t have an account?{" "}
            <Link href="/register" className="text-amber underline underline-offset-2">
              Create one
            </Link>
          </p>

          {unverifiedEmail && (
            <div className="mb-6 rounded-lg border border-border bg-surface p-4">
              <p className="text-sm font-medium mb-1">Your email isn&apos;t verified yet</p>
              <p className="text-muted text-xs mb-3">
                Check your inbox for the link we sent to <strong>{unverifiedEmail}</strong>.
                Links expire after 24 hours.
              </p>
              <button
                type="button"
                onClick={() => resendVerification(unverifiedEmail)}
                disabled={resending}
                className="text-amber underline underline-offset-2 text-xs disabled:opacity-50"
              >
                {resending ? "Sending…" : "Send me a new link"}
              </button>
            </div>
          )}

          <form onSubmit={handleSubmit(onSubmit)} className="space-y-6">

            {/* Email */}
            <div>
              <label className="block text-sm font-medium mb-1">Email</label>
              <input
                type="email"
                {...register("email")}
                className="input-field"
                placeholder="you@example.com"
              />
              {errors.email && (
                <p className="text-danger text-xs mt-1">{errors.email.message}</p>
              )}
            </div>

            {/* Password */}
            <div>
              <div className="flex items-center justify-between mb-1">
                <label className="block text-sm font-medium">Password</label>
                <Link href="/forgot-password" className="text-xs text-amber underline underline-offset-2">
                  Forgot password?
                </Link>
              </div>
              <input
                type="password"
                {...register("password")}
                className="input-field"
                placeholder="••••••••"
              />
              {errors.password && (
                <p className="text-danger text-xs mt-1">{errors.password.message}</p>
              )}
            </div>

            <button
              type="submit"
              disabled={loading || resumingPayment}
              className="btn-accent w-full disabled:opacity-50"
            >
              {resumingPayment ? "Redirecting to payment..." : loading ? "Signing in..." : "Sign in"}
            </button>
          </form>
        </div>
      </div>
    </div>
  );
}

export default function LoginPage() {
  return (
    <Suspense fallback={null}>
      <LoginPageInner />
    </Suspense>
  );
}
