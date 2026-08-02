"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { toast } from "sonner";
import { useCartStore } from "@/store/cartStore";

export default function PaymentStatusCheck({ orderGroupId }: { orderGroupId: string }) {
  const router = useRouter();
  const clearCart = useCartStore((state) => state.clearCart);
  const [checking, setChecking] = useState(false);

  const check = async () => {
    setChecking(true);
    try {
      const res = await fetch(`/api/paystack/verify-order/${orderGroupId}`);
      const data = await res.json().catch(() => ({}));
      if (res.ok && data.status === "success") {
        clearCart();
        toast.success("Payment confirmed!");
        router.refresh();
      } else if (res.ok && data.status === "failed") {
        toast.error("Payment failed. Please try again.");
      } else if (res.status === 404) {
        toast("No M-Pesa/card payment found yet for this order.");
      } else {
        toast("Still pending on Paystack's side. Try again in a moment.");
      }
    } catch {
      toast.error("Could not check payment status. Try again.");
    } finally {
      setChecking(false);
    }
  };

  return (
    <div className="card p-4 mb-6 flex items-center justify-between gap-4 bg-amber/10 border-amber/30">
      <p className="text-sm text-ink">
        Already paid but it&apos;s still showing pending? This can happen if the payment page
        didn&apos;t redirect back after you completed it on your phone.
      </p>
      <button onClick={check} disabled={checking} className="btn-accent whitespace-nowrap disabled:opacity-60">
        {checking ? "Checking…" : "I've paid — check status"}
      </button>
    </div>
  );
}
