"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useCartStore } from "@/store/cartStore";
import { formatKES, resolveImageUrl, decodeHtml } from "@/lib/utils";
import LocationPicker from "@/components/geo/LocationPicker";
import { UserAddress } from "@/types/interface";

export default function CartPage() {
  const { items, updateQuantity, removeItem, clearCart, totalPrice } = useCartStore();
  const [addresses, setAddresses] = useState<UserAddress[]>([]);
  const [selectedAddressId, setSelectedAddressId] = useState<string>("");
  const [mapOpen, setMapOpen] = useState(false);
  const [pinSaving, setPinSaving] = useState(false);

  useEffect(() => {
    fetch("/api/account/addresses")
      .then((r) => r.json().catch(() => []))
      .then((data: UserAddress[]) => {
        setAddresses(data ?? []);
        const def = data.find((a) => a.is_default) ?? data[0];
        if (def) setSelectedAddressId(def.id);
      });
  }, []);

  const selectedAddress = addresses.find((a) => a.id === selectedAddressId);

  async function updateAddressPin(sel: { lat: number; lng: number; sublocation?: string | null }) {
    if (!selectedAddressId) return;
    setPinSaving(true);
    try {
      const res = await fetch(`/api/account/addresses/${selectedAddressId}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ lat: sel.lat, lng: sel.lng, sublocation: sel.sublocation ?? "" }),
      });
      if (!res.ok) throw new Error();
      setAddresses((prev) =>
        prev.map((a) =>
          a.id === selectedAddressId ? { ...a, lat: sel.lat, lng: sel.lng, sublocation: sel.sublocation ?? "" } : a
        )
      );
      setMapOpen(false);
    } catch {
      // ignore
    } finally {
      setPinSaving(false);
    }
  }

  if (items.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center py-32 text-center px-4">
        <p className="text-3xl font-extrabold mb-3">Your cart is empty</p>
        <p className="text-muted text-sm mb-8">
          Looks like you haven&apos;t added anything yet.
        </p>
        <Link href="/products" className="btn-accent">
          Start Shopping
        </Link>
      </div>
    );
  }

  return (
    <div className="w-full mx-auto px-4 md:px-6 py-6">
      <div className="flex items-baseline justify-between mb-4">
        <h1 className="text-2xl font-bold">
          Your Cart ({items.length} {items.length === 1 ? "item" : "items"})
        </h1>
        <button
          onClick={clearCart}
          className="text-xs text-muted hover:text-ink underline underline-offset-2 transition-colors"
        >
          Clear all
        </button>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">

        {/* Cart items */}
        <div className="lg:col-span-2 card flex flex-col gap-0 overflow-hidden">
          {items.map((item, index) => (
            <div
              key={`${item.product_id}-${item.variant_id ?? ""}`}
              className={`flex gap-4 p-4 ${index !== items.length - 1 ? "border-b border-border" : ""}`}
            >
              {/* Image */}
              <Link href={`/products/${item.product_slug}`} className="shrink-0">
                <div className="w-24 h-24 bg-surface overflow-hidden rounded-lg">
                  {item.product_image ? (
                    <img
                      src={resolveImageUrl(item.product_image)}
                      alt={item.product_name}
                      className="w-full h-full object-cover"
                    />
                  ) : (
                    <div className="w-full h-full flex items-center justify-center text-muted text-xl">
                      🛍️
                    </div>
                  )}
                </div>
              </Link>

              {/* Details */}
              <div className="flex-1 min-w-0 flex flex-col justify-between">
                <div>
                  <p className="text-xs text-muted mb-0.5">{decodeHtml(item.shop_name)}</p>
                  <Link
                    href={`/products/${item.product_slug}`}
                    className="font-semibold text-sm leading-tight hover:text-amber transition-colors line-clamp-2"
                  >
                    {decodeHtml(item.product_name)}
                  </Link>
                </div>

                <div className="flex items-center justify-between mt-3">
                  {/* Quantity controls */}
                  <div className="flex items-center border border-border rounded-full overflow-hidden">
                    <button
                      onClick={() =>
                        item.quantity > 1
                          ? updateQuantity(item.product_id, item.quantity - 1, item.variant_id)
                          : removeItem(item.product_id, item.variant_id)
                      }
                      className="px-3 py-1 text-sm hover:bg-surface transition-colors"
                    >
                      −
                    </button>
                    <span className="px-3 py-1 text-sm border-x border-border min-w-10 text-center">
                      {item.quantity}
                    </span>
                    <button
                      onClick={() =>
                        updateQuantity(item.product_id, item.quantity + 1, item.variant_id)
                      }
                      className="px-3 py-1 text-sm hover:bg-surface transition-colors"
                    >
                      +
                    </button>
                  </div>

                  {/* Line total + remove */}
                  <div className="flex items-center gap-4">
                    <span className="font-bold text-sm text-ink">
                      {formatKES(item.unit_price * item.quantity)}
                    </span>
                    <button
                      onClick={() => removeItem(item.product_id, item.variant_id)}
                      className="text-xs text-muted hover:text-danger transition-colors"
                    >
                      Remove
                    </button>
                  </div>
                </div>
              </div>
            </div>
          ))}
        </div>

        {/* Order summary */}
        <div className="lg:col-span-1">
          <div className="card p-6 flex flex-col gap-4 lg:sticky lg:top-20">
            <h2 className="text-lg font-bold border-b border-border pb-3">
              Order Summary
            </h2>

            <div className="flex justify-between text-sm">
              <span className="text-muted">Subtotal</span>
              <span className="font-medium">{formatKES(totalPrice())}</span>
            </div>

            <div className="flex justify-between text-sm">
              <span className="text-muted">Delivery</span>
              <span className="text-muted italic">Calculated at checkout</span>
            </div>

            <div className="flex justify-between font-bold border-t border-border pt-3">
              <span>Total</span>
              <span className="text-ink text-lg">{formatKES(totalPrice())}</span>
            </div>

            {addresses.length > 0 && (
              <div className="space-y-2">
                <label className="block text-xs font-medium text-muted">Deliver to</label>
                <select
                  value={selectedAddressId}
                  onChange={(e) => setSelectedAddressId(e.target.value)}
                  className="w-full rounded-lg border border-border bg-bg px-3 py-2 text-sm"
                >
                  {addresses.map((addr) => (
                    <option key={addr.id} value={addr.id}>
                      {addr.first_name} {addr.last_name} — {addr.county}
                    </option>
                  ))}
                </select>
                {selectedAddress && !selectedAddress.lat && (
                  <button
                    type="button"
                    onClick={() => setMapOpen(true)}
                    className="flex items-center gap-2 text-xs text-amber hover:underline pt-1"
                  >
                    Pin delivery location on map
                  </button>
                )}
                {selectedAddress?.lat && selectedAddress.sublocation && (
                  <p className="text-xs text-green-600">Pinned: {selectedAddress.sublocation}</p>
                )}
              </div>
            )}

            <Link
              href="/checkout"
              className="btn-accent w-full mt-2"
            >
              Proceed to Checkout →
            </Link>

            <Link
              href="/products"
              className="w-full text-center py-2 text-xs text-muted hover:text-ink underline underline-offset-2 transition-colors"
            >
              Continue Shopping
            </Link>
          </div>
        </div>

      </div>

      {mapOpen && selectedAddressId && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4" onClick={() => setMapOpen(false)}>
          <div className="w-full max-w-2xl" onClick={(e) => e.stopPropagation()}>
            <p className="mb-2 text-center text-sm font-medium text-white">
              Drop the pin where our rider should deliver — switch between Satellite and Streets
            </p>
            <LocationPicker
              initial={
                selectedAddress?.lat != null && selectedAddress.lng != null
                  ? { lat: selectedAddress.lat, lng: selectedAddress.lng }
                  : undefined
              }
              onCancel={() => setMapOpen(false)}
              onConfirm={(sel) => {
                if (!pinSaving) updateAddressPin(sel);
              }}
            />
          </div>
        </div>
      )}
    </div>
  );
}
