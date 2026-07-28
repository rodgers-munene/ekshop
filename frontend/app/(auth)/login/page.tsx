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

  const {
    register,
    handleSubmit,
    formState: { errors },
  } = useForm<LoginForm>({
    resolver: zodResolver(loginSchema),
  });

  async function onSubmit(data: LoginForm) {
    setLoading(true);
    try {
      const res = await fetch("/api/auth", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ action: "login", ...data }),
      });

      const json = await res.json();

      if (!res.ok) {
        toast.error(json.detail ?? "Login failed");
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
              disabled={loading}
              className="btn-accent w-full disabled:opacity-50"
            >
              {loading ? "Signing in..." : "Sign in"}
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
