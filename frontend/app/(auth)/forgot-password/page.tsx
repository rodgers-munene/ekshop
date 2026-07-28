"use client";

import { useState } from "react";
import Link from "next/link";
import { useForm } from "react-hook-form";
import { z } from "zod";
import { zodResolver } from "@hookform/resolvers/zod";

const schema = z.object({
  email: z.string().email("Enter a valid email"),
});

type ForgotPasswordForm = z.infer<typeof schema>;

export default function ForgotPasswordPage() {
  const [loading, setLoading] = useState(false);
  const [sent, setSent] = useState(false);

  const {
    register,
    handleSubmit,
    formState: { errors },
  } = useForm<ForgotPasswordForm>({ resolver: zodResolver(schema) });

  async function onSubmit(data: ForgotPasswordForm) {
    setLoading(true);
    try {
      await fetch("/api/auth", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ action: "forgot-password", ...data }),
      });
      // Always show the same confirmation, regardless of whether the email exists.
      setSent(true);
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

        {sent ? (
          <>
            <h1 className="text-2xl font-bold mb-2">Check your inbox</h1>
            <p className="text-muted text-sm mb-6">
              If that email is registered, a password reset link is on its way.
            </p>
            <Link href="/login" className="text-amber underline underline-offset-2 text-sm">Back to sign in</Link>
          </>
        ) : (
          <>
            <h1 className="text-2xl font-bold mb-1">Forgot your password?</h1>
            <p className="text-muted text-sm mb-8">Enter your email and we&apos;ll send you a reset link.</p>

            <form onSubmit={handleSubmit(onSubmit)} className="space-y-6">
              <div>
                <label className="block text-sm font-medium mb-1">Email</label>
                <input type="email" {...register("email")} className="input-field" placeholder="you@example.com" />
                {errors.email && <p className="text-danger text-xs mt-1">{errors.email.message}</p>}
              </div>

              <button type="submit" disabled={loading} className="btn-accent w-full disabled:opacity-50">
                {loading ? "Sending..." : "Send reset link"}
              </button>

              <p className="text-center text-sm text-muted">
                <Link href="/login" className="text-amber underline underline-offset-2">Back to sign in</Link>
              </p>
            </form>
          </>
        )}
      </div>
    </div>
  );
}
