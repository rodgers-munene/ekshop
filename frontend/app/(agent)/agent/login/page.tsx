"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { useForm } from "react-hook-form";
import { z } from "zod";
import { zodResolver } from "@hookform/resolvers/zod";
import { toast } from "sonner";

const loginSchema = z.object({
  email: z.string().email("Enter a valid email"),
  password: z.string().min(1, "Password is required"),
});

type LoginForm = z.infer<typeof loginSchema>;

export default function AgentLoginPage() {
  const router = useRouter();
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
      const res = await fetch("/api/agent/auth", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ action: "login", ...data }),
      });

      const json = await res.json();

      if (!res.ok) {
        toast.error(json.detail ?? "Login failed");
        return;
      }

      toast.success(`Welcome back, ${json.agent.name}!`);
      router.push("/agent/deliveries");
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
            Delivery agent<br />portal.
          </h1>
          <p className="text-white/70 text-lg">
            View your assigned deliveries and keep buyers updated.
          </p>
        </div>
        <p className="text-sm text-white/50">© {new Date().getFullYear()} Ekshop</p>
      </div>

      {/* Right: form */}
      <div className="flex-1 flex items-center justify-center px-6 py-12">
        <div className="w-full max-w-sm">
          <h2 className="text-3xl font-bold mb-1">Agent sign in</h2>
          <p className="text-muted text-sm mb-8">
            Enter the credentials provided by your admin.
          </p>

          <form onSubmit={handleSubmit(onSubmit)} className="space-y-6">

            {/* Email */}
            <div>
              <label className="block text-sm font-medium mb-1">Email</label>
              <input
                type="email"
                {...register("email")}
                className="input-field"
                placeholder="agent@example.com"
              />
              {errors.email && (
                <p className="text-danger text-xs mt-1">{errors.email.message}</p>
              )}
            </div>

            {/* Password */}
            <div>
              <label className="block text-sm font-medium mb-1">Password</label>
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
