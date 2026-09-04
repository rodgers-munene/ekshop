"use client";

import { Suspense, useEffect, useRef, useState } from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import RenewButton from "@/components/dashboard/RenewButton";

type Status = "checking" | "pending" | "active" | "failed";

const POLL_INTERVAL_MS = 3000;
const MAX_POLLS = 20;

export default function RenewalPaymentStatusPage() {
  return (
    <Suspense fallback={null}>
      <RenewalPaymentStatusPageInner />
    </Suspense>
  );
}

function RenewalPaymentStatusPageInner() {
  const searchParams = useSearchParams();
  const reference = searchParams.get("ref");

  const [status, setStatus] = useState<Status>(() => (reference ? "checking" : "failed"));
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

  return (
    <div className="min-h-[60vh] flex items-center justify-center px-6">
      <div className="w-full max-w-sm text-center">
        {status === "checking" || status === "pending" ? (
          <>
            <h2 className="text-2xl font-bold mb-2">Confirming your payment…</h2>
            <p className="text-muted text-sm mb-6">
              We&apos;re confirming your payment with Paystack. This usually takes a few seconds.
            </p>
          </>
        ) : status === "active" ? (
          <>
            <h2 className="text-2xl font-bold mb-2">Your shop is active again!</h2>
            <p className="text-muted text-sm mb-6">Payment confirmed. Your subscription has been renewed.</p>
            <Link href="/dashboard/billing" className="btn-accent inline-block">Back to billing →</Link>
          </>
        ) : (
          <>
            <h2 className="text-2xl font-bold mb-2">Payment not confirmed</h2>
            <p className="text-muted text-sm mb-6">
              We couldn&apos;t confirm your payment. If you closed the Paystack checkout early, you can try again.
            </p>
            <RenewButton />
          </>
        )}
      </div>
    </div>
  );
}
