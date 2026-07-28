"use client";

import { Suspense, useEffect, useRef } from "react";
import { useRouter, useSearchParams, usePathname } from "next/navigation";
import { toast } from "sonner";

export default function PaystackReturnHandler() {
  return (
    <Suspense fallback={null}>
      <PaystackReturnHandlerInner />
    </Suspense>
  );
}

function PaystackReturnHandlerInner() {
  const router = useRouter();
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const reference = searchParams.get("paystack_ref");
  const handled = useRef(false);

  useEffect(() => {
    if (!reference || handled.current) return;
    handled.current = true;

    (async () => {
      try {
        const res = await fetch(`/api/paystack/verify?reference=${encodeURIComponent(reference)}`);
        const data = await res.json();
        if (res.ok && data.status === "success") {
          toast.success("Payment confirmed!");
        } else if (res.ok && data.status === "failed") {
          toast.error("Payment failed. Please try again.");
        } else {
          toast("Payment is still processing. We'll update this page shortly.");
        }
      } catch {
        toast.error("Could not confirm payment status. Refresh to check again.");
      } finally {
        router.replace(pathname);
        router.refresh();
      }
    })();
  }, [reference, router, pathname]);

  return null;
}
