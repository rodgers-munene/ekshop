"use client";

import { Suspense, useEffect, useRef, useState } from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";

type Status = "checking" | "pending" | "active" | "failed";

const POLL_INTERVAL_MS = 3000;
const MAX_POLLS = 20;

export default function PaymentStatusPage() {
  return (
    <Suspense fallback={null}>
      <PaymentStatusPageInner />
    </Suspense>
  );
}

function PaymentStatusPageInner() {
  const searchParams = useSearchParams();
  const reference = searchParams.get("ref");

  const [status, setStatus] = useState<Status>(() => (reference ? "checking" : "failed"));
  const [shopSlug, setShopSlug] = useState<string | null>(null);
  const [retrying, setRetrying] = useState(false);
  const pollCount = useRef(0);

  useEffect(() => {
    if (!reference) return;

    let cancelled = false;
    let intervalId: ReturnType<typeof setInterval> | null = null;

    async function runCheck() {
      try {
        const res = await fetch(`/api/paystack/subscription-status?reference=${encodeURIComponent(reference as string)}`);
        const data = await res.json();
        if (cancelled) return;

        if (!res.ok) {
          setStatus("failed");
          if (intervalId) clearInterval(intervalId);
          return;
        }
        if (data.status === "active") {
          setStatus("active");
          setShopSlug(data.shop_slug ?? null);
          if (intervalId) clearInterval(intervalId);
        } else {
          setStatus("pending");
        }
      } catch {
        if (!cancelled) setStatus("pending");
      }
    }

    runCheck();
    intervalId = setInterval(() => {
      pollCount.current += 1;
      if (pollCount.current >= MAX_POLLS) {
        if (intervalId) clearInterval(intervalId);
        if (!cancelled) setStatus((current) => (current === "active" ? current : "failed"));
        return;
      }
      runCheck();
    }, POLL_INTERVAL_MS);

    return () => {
      cancelled = true;
      if (intervalId) clearInterval(intervalId);
    };
  }, [reference]);

  async function handleRetry() {
    if (!reference) return;
    setRetrying(true);
    try {
      const res = await fetch("/api/paystack/subscription-status", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ reference }),
      });
      const data = await res.json();
      if (res.ok && data.authorization_url) {
        window.location.href = data.authorization_url;
      }
    } finally {
      setRetrying(false);
    }
  }

  return (
    <div className="min-h-screen flex items-center justify-center px-6">
      <div className="w-full max-w-sm text-center">
        <span className="text-2xl font-bold">
          EK<span className="text-amber">SHOP</span>
        </span>

        {status === "checking" || status === "pending" ? (
          <>
            <h2 className="text-2xl font-bold mt-6 mb-2">Activating your shop…</h2>
            <p className="text-muted text-sm mb-6">
              We&apos;re confirming your payment with Paystack. This usually takes a few seconds.
            </p>
          </>
        ) : status === "active" ? (
          <>
            <h2 className="text-2xl font-bold mt-6 mb-2">Your shop is live!</h2>
            <p className="text-muted text-sm mb-6">
              Payment confirmed. You can now sign in and start listing products
              {shopSlug ? ` for ${shopSlug}` : ""}.
            </p>
            <Link href="/login" className="btn-accent inline-block">Sign in →</Link>
          </>
        ) : (
          <>
            <h2 className="text-2xl font-bold mt-6 mb-2">Payment not confirmed</h2>
            <p className="text-muted text-sm mb-6">
              We couldn&apos;t confirm your payment. If you closed the Paystack checkout early, you can try again.
            </p>
            <button
              type="button"
              onClick={handleRetry}
              disabled={retrying || !reference}
              className="btn-accent disabled:opacity-50"
            >
              {retrying ? "Please wait..." : "Retry payment"}
            </button>
          </>
        )}
      </div>
    </div>
  );
}
