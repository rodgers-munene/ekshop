"use client";

import { Suspense, useState } from "react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { useForm } from "react-hook-form";
import { z } from "zod";
import { zodResolver } from "@hookform/resolvers/zod";
import { toast } from "sonner";

const schema = z
  .object({
    password: z.string().min(8, "Password must be at least 8 characters"),
    confirm: z.string(),
  })
  .refine((data) => data.password === data.confirm, {
    message: "Passwords don't match",
    path: ["confirm"],
  });

type ResetPasswordForm = z.infer<typeof schema>;

function ResetPasswordInner() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const token = searchParams.get("token");
  const [loading, setLoading] = useState(false);

  const {
    register,
    handleSubmit,
    formState: { errors },
  } = useForm<ResetPasswordForm>({ resolver: zodResolver(schema) });

  async function onSubmit(data: ResetPasswordForm) {
    if (!token) return;
    setLoading(true);
    try {
      const res = await fetch("/api/auth", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ action: "reset-password", token, new_password: data.password }),
      });
      const json = await res.json().catch(() => ({}));
      if (!res.ok) {
        toast.error(json.detail ?? "Could not reset password");
        return;
      }
      toast.success("Password updated. Please sign in.");
      router.push("/login");
    } catch {
      toast.error("Something went wrong. Try again.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="min-h-screen flex items-center justify-center px-6">
      <div className="w-full max-w-sm">
        <Link href="/" className="text-2xl font-bold inline-block mb-8">
          EK<span className="text-amber">SHOP</span>
        </Link>

        {!token ? (
          <>
            <h1 className="text-2xl font-bold mb-2">Invalid reset link</h1>
            <p className="text-muted text-sm mb-6">This link is missing its token. Request a new one.</p>
            <Link href="/forgot-password" className="text-amber underline underline-offset-2 text-sm">
              Request a new link
            </Link>
          </>
        ) : (
          <>
            <h1 className="text-2xl font-bold mb-1">Set a new password</h1>
            <p className="text-muted text-sm mb-8">Choose a new password for your account.</p>

            <form onSubmit={handleSubmit(onSubmit)} className="space-y-6">
              <div>
                <label className="block text-sm font-medium mb-1">New password</label>
                <input type="password" {...register("password")} className="input-field" placeholder="••••••••" />
                {errors.password && <p className="text-danger text-xs mt-1">{errors.password.message}</p>}
              </div>

              <div>
                <label className="block text-sm font-medium mb-1">Confirm password</label>
                <input type="password" {...register("confirm")} className="input-field" placeholder="••••••••" />
                {errors.confirm && <p className="text-danger text-xs mt-1">{errors.confirm.message}</p>}
              </div>

              <button type="submit" disabled={loading} className="btn-accent w-full disabled:opacity-50">
                {loading ? "Saving..." : "Reset password"}
              </button>
            </form>
          </>
        )}
      </div>
    </div>
  );
}

export default function ResetPasswordPage() {
  return (
    <Suspense fallback={null}>
      <ResetPasswordInner />
    </Suspense>
  );
}
