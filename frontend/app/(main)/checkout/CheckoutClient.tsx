"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { toast } from "sonner";
import { useCartStore } from "@/store/cartStore";
import { UserAddress } from "@/types/interface";
import { formatKES, resolveImageUrl as resolveImg } from "@/lib/utils";

type Step = "review" | "address" | "payment" | "pending";

export default function CheckoutClient({ addresses }: { addresses: UserAddress[] }) {
  const router = useRouter();
  const { items, totalPrice, clearCart } = useCartStore();
  const [step, setStep] = useState<Step>("review");
  const [selectedAddressId, setSelectedAddressId] = useState<string>(
    addresses.find((a) => a.is_default)?.id ?? addresses[0]?.id ?? ""
  );
  const [mpesaPhone, setMpesaPhone] = useState("");
  const [loading, setLoading] = useState(false);

  const subtotal = totalPrice();
  const deliveryFee = 150;
  const total = subtotal + deliveryFee;

  async function placeOrder() {
    if (!selectedAddressId) { toast.error("Select a delivery address"); return; }
    if (!mpesaPhone.trim()) { toast.error("Enter your M-Pesa phone number"); return; }

    setLoading(true);
    try {
      // 1. Create order
      const orderRes = await fetch("/api/checkout", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ address_id: selectedAddressId }),
      });
      const orderJson = await orderRes.json();
      if (!orderRes.ok) { toast.error(orderJson.detail ?? "Failed to place order"); return; }

      // 2. Trigger M-Pesa STK push
      const mpesaRes = await fetch("/api/mpesa", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ order_group_id: orderJson.id, phone: mpesaPhone.trim() }),
      });
      const mpesaJson = await mpesaRes.json();
      if (!mpesaRes.ok) { toast.error(mpesaJson.detail ?? "M-Pesa request failed"); return; }

      clearCart();
      setStep("pending");
    } catch {
      toast.error("Something went wrong. Try again.");
    } finally {
      setLoading(false);
    }
  }

  if (items.length === 0 && step !== "pending") {
    router.replace("/cart");
    return null;
  }

  if (step === "pending") {
    return (
      <div className="min-h-[60vh] flex flex-col items-center justify-center text-center px-4 py-16">
        <div className="text-5xl mb-4">📱</div>
        <h2 className="text-2xl font-extrabold mb-2">Check your phone</h2>
        <p className="text-muted text-sm max-w-xs mb-6">
          An M-Pesa prompt has been sent to <strong>{mpesaPhone}</strong>. Enter your PIN to complete payment.
        </p>
        <button onClick={() => router.push("/orders")} className="btn-accent">
          View My Orders →
        </button>
      </div>
    );
  }

  return (
    <div className="w-full max-w-5xl mx-auto px-4 md:px-6 py-6">
      <h1 className="text-2xl font-bold mb-6">Checkout</h1>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">

        {/* Left — steps */}
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
                    <p className="text-sm font-medium line-clamp-1">{item.product_name}</p>
                    <p className="text-xs text-muted">{item.shop_name} · qty {item.quantity}</p>
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

          {/* Step 3: M-Pesa */}
          <section className="card overflow-hidden">
            <div className="px-5 py-3 border-b border-border bg-surface">
              <h2 className="font-semibold">3. Pay with M-Pesa</h2>
            </div>
            <div className="p-4">
              <p className="text-xs text-muted mb-3">Enter the M-Pesa number to receive the payment prompt.</p>
              <input
                type="tel"
                value={mpesaPhone}
                onChange={(e) => setMpesaPhone(e.target.value)}
                placeholder="e.g. 0712 345 678"
                className="input-field max-w-xs"
              />
            </div>
          </section>
        </div>

        {/* Right — summary */}
        <div className="lg:col-span-1">
          <div className="card p-6 flex flex-col gap-4 lg:sticky lg:top-20">
            <h2 className="text-lg font-bold border-b border-border pb-3">Summary</h2>
            <div className="flex justify-between text-sm">
              <span className="text-muted">Subtotal</span>
              <span>{formatKES(subtotal)}</span>
            </div>
            <div className="flex justify-between text-sm">
              <span className="text-muted">Delivery</span>
              <span>{formatKES(deliveryFee)}</span>
            </div>
            <div className="flex justify-between font-bold border-t border-border pt-3">
              <span>Total</span>
              <span className="text-ink text-lg">{formatKES(total)}</span>
            </div>
            <button
              onClick={placeOrder}
              disabled={loading || !selectedAddressId || !mpesaPhone.trim()}
              className="btn-accent w-full disabled:opacity-40 mt-2"
            >
              {loading ? "Processing..." : "Pay with M-Pesa →"}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
