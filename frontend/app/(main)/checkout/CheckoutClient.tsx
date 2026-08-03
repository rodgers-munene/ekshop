"use client";

import { useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { toast } from "sonner";
import { useCartStore } from "@/store/cartStore";
import { UserAddress } from "@/types/interface";
import { formatKES, resolveImageUrl as resolveImg, decodeHtml } from "@/lib/utils";

type Step = "review" | "address" | "payment" | "redirecting";

export default function CheckoutClient({ addresses }: { addresses: UserAddress[] }) {
  const router = useRouter();
  const { items, totalPrice } = useCartStore();
  const [step, setStep] = useState<Step>("review");
  const [selectedAddressId, setSelectedAddressId] = useState<string>(
    addresses.find((a) => a.is_default)?.id ?? addresses[0]?.id ?? ""
  );
  const [loading, setLoading] = useState(false);
  const [deliveryFee, setDeliveryFee] = useState(0);
  const [resolvedFeeKey, setResolvedFeeKey] = useState("");
  const requestKeyRef = useRef("");

  const subtotal = totalPrice();
  const total = subtotal + deliveryFee;

  const shopIds = [...new Set(items.map((item) => item.shop_id))];
  const feeKey = selectedAddressId && shopIds.length > 0 ? `${selectedAddressId}|${shopIds.sort().join(",")}` : "";
  const feeLoading = feeKey !== "" && feeKey !== resolvedFeeKey;

  useEffect(() => {
    if (!feeKey) return;
    requestKeyRef.current = feeKey;

    fetch("/api/checkout/delivery-fee-preview", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ address_id: selectedAddressId, shop_ids: shopIds }),
    })
      .then((res) => res.json())
      .then((data) => {
        if (requestKeyRef.current !== feeKey) return; // a newer request superseded this one
        if (typeof data.total_delivery_fee === "string") {
          setDeliveryFee(parseFloat(data.total_delivery_fee));
        }
        setResolvedFeeKey(feeKey);
      })
      .catch(() => {
        if (requestKeyRef.current === feeKey) setResolvedFeeKey(feeKey);
      });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [feeKey]);

  async function placeOrder() {
    if (!selectedAddressId) { toast.error("Select a delivery address"); return; }

    setLoading(true);
    try {
      // 0. Sync the local cart to the server cart so the backend (which
      // checks out from the server-side cart, not the request body) sees
      // the same items the user is looking at.
      await fetch("/api/cart", { method: "DELETE" });
      for (const item of items) {
        const syncRes = await fetch("/api/cart/items", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            product_id: item.product_id,
            variant_id: item.variant_id,
            quantity: item.quantity,
          }),
        });
        if (!syncRes.ok) {
          const syncJson = await syncRes.json().catch(() => ({}));
          toast.error(syncJson.detail ?? "Could not sync your cart. Try again.");
          return;
        }
      }

      // 1. Create order
      const orderRes = await fetch("/api/checkout", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ address_id: selectedAddressId }),
      });
      const orderJson = await orderRes.json();
      if (!orderRes.ok) { toast.error(orderJson.detail ?? "Failed to place order"); return; }

      // 2. Start a Paystack transaction and get the hosted checkout URL
      const paystackRes = await fetch("/api/paystack", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ order_group_id: orderJson.id }),
      });
      const paystackJson = await paystackRes.json();
      if (!paystackRes.ok) { toast.error(paystackJson.detail ?? "Could not start payment"); return; }

      // Cart is intentionally left intact here — it's only cleared once
      // payment is confirmed (see PaystackReturnHandler). If the buyer
      // cancels on Paystack's page, they should still have their items.
      setStep("redirecting");
      window.location.href = paystackJson.authorization_url;
    } catch {
      toast.error("Something went wrong. Try again.");
    } finally {
      setLoading(false);
    }
  }

  if (items.length === 0 && step !== "redirecting") {
    router.replace("/cart");
    return null;
  }

  if (step === "redirecting") {
    return (
      <div className="min-h-[60vh] flex flex-col items-center justify-center text-center px-4 py-16">
        <div className="text-5xl mb-4">💳</div>
        <h2 className="text-2xl font-extrabold mb-2">Taking you to Paystack…</h2>
        <p className="text-muted text-sm max-w-xs mb-6">
          Complete your payment on the secure Paystack checkout page. You&apos;ll be redirected back here once it&apos;s done.
        </p>
      </div>
    );
  }

  return (
    <div className="w-full max-w-5xl mx-auto px-4 md:px-6 py-6">
      <h1 className="text-2xl font-bold mb-6">Checkout</h1>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">

        {/* Left: steps */}
        <div className="lg:col-span-2 space-y-4">

          {/* Step 1: Cart review */}
          <section className="card overflow-hidden">
            <div className="flex items-center justify-between px-5 py-3 border-b border-border bg-surface">
              <h2 className="font-semibold">1. Your Items</h2>
              <button onClick={() => router.push("/cart")} className="text-xs text-muted underline">Edit cart</button>
            </div>
            <div className="divide-y divide-border">
              {items.map((item) => (
                <div key={item.product_id} className="flex gap-3 p-4">
                  <div className="w-14 h-14 shrink-0 bg-surface overflow-hidden rounded-lg">
                    {item.product_image
                      ? <img src={resolveImg(item.product_image)} alt={item.product_name} loading="lazy" className="w-full h-full object-cover" />
                      : <div className="w-full h-full flex items-center justify-center text-lg">🛍️</div>}
                  </div>
                  <div className="flex-1 min-w-0">
                    <p className="text-sm font-medium line-clamp-1">{decodeHtml(item.product_name)}</p>
                    <p className="text-xs text-muted">{decodeHtml(item.shop_name)} · qty {item.quantity}</p>
                  </div>
                  <p className="text-sm font-bold text-ink shrink-0">{formatKES(item.unit_price * item.quantity)}</p>
                </div>
              ))}
            </div>
          </section>

          {/* Step 2: Address */}
          <section className="card overflow-hidden">
            <div className="px-5 py-3 border-b border-border bg-surface">
              <h2 className="font-semibold">2. Delivery Address</h2>
            </div>
            <div className="p-4 space-y-3">
              {addresses.length === 0 ? (
                <p className="text-sm text-muted">No saved addresses. <a href="/account" className="underline">Add one in your account.</a></p>
              ) : (
                addresses.map((addr) => (
                  <label key={addr.id} className={`flex gap-3 p-3 rounded-lg border cursor-pointer transition-colors ${selectedAddressId === addr.id ? "border-amber bg-surface" : "border-border hover:border-ink/30"}`}>
                    <input
                      type="radio"
                      name="address"
                      value={addr.id}
                      checked={selectedAddressId === addr.id}
                      onChange={() => setSelectedAddressId(addr.id)}
                      className="mt-0.5 accent-amber"
                    />
                    <div>
                      <p className="text-sm font-medium">{addr.first_name} {addr.last_name} {addr.label && <span className="text-xs text-muted ml-1">({addr.label})</span>}</p>
                      <p className="text-xs text-muted">{addr.town}, {addr.county} · {addr.phone}</p>
                    </div>
                  </label>
                ))
              )}
            </div>
          </section>

          {/* Step 3: Payment */}
          <section className="card overflow-hidden">
            <div className="px-5 py-3 border-b border-border bg-surface">
              <h2 className="font-semibold">3. Payment</h2>
            </div>
            <div className="p-4">
              <p className="text-xs text-muted">
                You&apos;ll be redirected to Paystack&apos;s secure checkout to pay by card or bank.
              </p>
            </div>
          </section>
        </div>

        {/* Right: summary */}
        <div className="lg:col-span-1">
          <div className="card p-6 flex flex-col gap-4 lg:sticky lg:top-20">
            <h2 className="text-lg font-bold border-b border-border pb-3">Summary</h2>
            <div className="flex justify-between text-sm">
              <span className="text-muted">Subtotal</span>
              <span>{formatKES(subtotal)}</span>
            </div>
            <div className="flex justify-between text-sm">
              <span className="text-muted">Delivery</span>
              <span>{feeLoading ? <span className="text-muted italic">Calculating…</span> : formatKES(deliveryFee)}</span>
            </div>
            <div className="flex justify-between font-bold border-t border-border pt-3">
              <span>Total</span>
              <span className="text-ink text-lg">{formatKES(total)}</span>
            </div>
            <button
              onClick={placeOrder}
              disabled={loading || feeLoading || !selectedAddressId}
              className="btn-accent w-full disabled:opacity-40 mt-2"
            >
              {loading ? "Processing..." : "Pay →"}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
