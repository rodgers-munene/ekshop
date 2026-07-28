"use client";

import { Suspense, useEffect, useRef, useState } from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";

type Status = "verifying" | "success" | "error";

function VerifyEmailInner() {
  const searchParams = useSearchParams();
  const token = searchParams.get("token");
  const [status, setStatus] = useState<Status>(token ? "verifying" : "error");
  const started = useRef(false);

  useEffect(() => {
    if (!token || started.current) return;
    started.current = true;

    (async () => {
      try {
        const res = await fetch("/api/auth", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ action: "verify-email", token }),
        });
        setStatus(res.ok ? "success" : "error");
      } catch {
        setStatus("error");
      }
    })();
  }, [token]);

  return (
    <div className="min-h-screen flex items-center justify-center px-6">
      <div className="w-full max-w-sm text-center">
        <Link href="/" className="text-2xl font-bold inline-block mb-8">
          EK<span className="text-amber">SHOP</span>
        </Link>

        {status === "verifying" && (
          <>
            <h1 className="text-2xl font-bold mb-2">Verifying your email…</h1>
            <p className="text-muted text-sm">This will just take a moment.</p>
          </>
        )}

        {status === "success" && (
          <>
            <h1 className="text-2xl font-bold mb-2">Email verified 🎉</h1>
            <p className="text-muted text-sm mb-6">Your account is active. You can sign in now.</p>
            <Link href="/login" className="btn-accent inline-block">Sign in →</Link>
          </>
        )}

        {status === "error" && (
          <>
            <h1 className="text-2xl font-bold mb-2">Verification link invalid</h1>
            <p className="text-muted text-sm mb-6">
              This link may have expired or already been used. Try signing in; if your
              account still needs verifying, request a new link.
            </p>
            <Link href="/login" className="text-amber underline underline-offset-2 text-sm">Back to sign in</Link>
          </>
        )}
      </div>
    </div>
  );
}

export default function VerifyEmailPage() {
  return (
    <Suspense fallback={null}>
      <VerifyEmailInner />
    </Suspense>
  );
}
