"use client";

import { useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import { toast } from "sonner";
import { AlertTriangle, RefreshCw, Smartphone, MapPin } from "lucide-react";
import { useCartStore } from "@/store/cartStore";
import {
  County,
  DeliveryFeePreview,
  GeoSelection,
  SubCounty,
  UserAddress,
  Ward,
} from "@/types/interface";
import { formatKES, resolveImageUrl as resolveImg, decodeHtml } from "@/lib/utils";
import LocationPicker from "@/components/geo/LocationPicker";
import MessageSellerButton from "@/components/MessageSellerButton";

type Step = "review" | "address" | "payment" | "polling";

/**
 * Addresses saved before the ward-level geography tables existed have no ward
 * (migration f4a29b7c1e05 added the column as nullable and never backfilled
 * it). We can't price or route a delivery properly without one, so checkout
 * makes the buyer fill it in first — see CompleteAddressForm below.
 */
function isAddressComplete(addr: UserAddress) {
  return !!addr.ward_id;
}

/**
 * Geography lookups that can legitimately miss. A legacy address may hold a
 * county name the geography table doesn't recognise, and the 404 body is an
 * error object rather than a list — so coerce anything unexpected to an empty
 * array instead of letting `.map` throw.
 */
async function fetchList<T>(url: string): Promise<T[]> {
  const res = await fetch(url);
  if (!res.ok) return [];
  const data = await res.json().catch(() => null);
  return Array.isArray(data) ? data : [];
}

const POLL_INTERVAL_MS = 4000;
// Matches the backend's own grace period before it's willing to actively
// query Safaricom (see _reconcile_mpesa_intent) — querying any sooner tends
// to get a spurious premature result. Past this window we stop auto-polling
// and let the buyer trigger a check manually via "Refresh Status" instead.
const POLL_TIMEOUT_MS = 20000;

export default function CheckoutClient({ addresses: initialAddresses }: { addresses: UserAddress[] }) {
  const router = useRouter();
  const { items, totalPrice, clearCart } = useCartStore();
  const [step, setStep] = useState<Step>("review");
  // Held in state rather than read straight from the prop so completing an
  // address in place updates the list without a round trip through the server.
  const [addresses, setAddresses] = useState(initialAddresses);
  const [selectedAddressId, setSelectedAddressId] = useState<string>(
    addresses.find((a) => a.is_default)?.id ?? addresses[0]?.id ?? ""
  );
  const [loading, setLoading] = useState(false);
  const [deliveryFee, setDeliveryFee] = useState(0);
  const [feeExplanation, setFeeExplanation] = useState<DeliveryFeePreview | null>(null);
  const [feeFailed, setFeeFailed] = useState(false);
  const [resolvedFeeKey, setResolvedFeeKey] = useState("");
  const requestKeyRef = useRef("");

  const [phone, setPhone] = useState("");
  const [orderGroupId, setOrderGroupId] = useState("");
  const [checkoutRequestId, setCheckoutRequestId] = useState("");
  const [pollFailed, setPollFailed] = useState(false);
  const [pollTimedOut, setPollTimedOut] = useState(false);
  const [secondsRemaining, setSecondsRemaining] = useState(POLL_TIMEOUT_MS / 1000);
  const [refreshing, setRefreshing] = useState(false);
  const [refreshMessage, setRefreshMessage] = useState("");
  const phoneTouchedRef = useRef(false);
  const [mapOpen, setMapOpen] = useState(false);
  const [pinSaving, setPinSaving] = useState(false);

  const subtotal = totalPrice();
  const total = subtotal + deliveryFee;

  const selectedAddress = addresses.find((a) => a.id === selectedAddressId) ?? null;
  const addressIncomplete = !!selectedAddress && !isAddressComplete(selectedAddress);

  const shopIds = [...new Set(items.map((item) => item.shop_id))];
  const itemsKey = items.map((item) => `${item.product_id}:${item.quantity}`).sort().join(",");
  // No ward means no quotable fee, so don't ask for one. The ward is part of
  // the key so completing an address re-prices the cart straight away.
  const feeKey =
    selectedAddressId && items.length > 0 && !addressIncomplete
      ? `${selectedAddressId}|${selectedAddress?.ward_id}|${itemsKey}`
      : "";
  const feeLoading = feeKey !== "" && feeKey !== resolvedFeeKey;

  useEffect(() => {
    if (!feeKey) return;
    requestKeyRef.current = feeKey;

    fetch("/api/checkout/delivery-fee-preview", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        address_id: selectedAddressId,
        shop_ids: shopIds,
        items: items.map((item) => ({ product_id: item.product_id, quantity: item.quantity })),
      }),
    })
      .then(async (res) => {
        const data = (await res.json().catch(() => null)) as DeliveryFeePreview | null;
        if (!res.ok || typeof data?.total_delivery_fee !== "string") {
          throw new Error("no fee in response");
        }
        return data;
      })
      .then((data) => {
        if (requestKeyRef.current !== feeKey) return; // a newer request superseded this one
        setDeliveryFee(parseFloat(data.total_delivery_fee));
        setFeeFailed(false);
        // Only the cost-based model can explain itself; the others send nothing
        // and the breakdown line below stays hidden.
        setFeeExplanation(data.band_label ? data : null);
        setResolvedFeeKey(feeKey);
      })
      .catch(() => {
        if (requestKeyRef.current !== feeKey) return;
        // Never show an unpriced delivery as free: checkout charges a fee
        // computed server-side from the cart, so a fabricated Ksh 0 here would
        // bill the buyer more than the total they agreed to.
        setFeeFailed(true);
        setFeeExplanation(null);
        setResolvedFeeKey(feeKey);
      });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [feeKey]);

  // Prefill the payment phone from the selected address, but only until the
  // buyer edits it themselves — the payment phone may differ from the
  // delivery contact.
  useEffect(() => {
    if (phoneTouchedRef.current) return;
    const addr = addresses.find((a) => a.id === selectedAddressId);
    if (addr?.phone) setPhone(addr.phone);
  }, [selectedAddressId, addresses]);

  // An empty cart belongs on the cart page. Navigating from an effect rather
  // than during render, because redirecting mid-render updates the Router
  // while this component is still rendering and React rejects it.
  useEffect(() => {
    if (items.length === 0 && step !== "polling") router.replace("/cart");
  }, [items.length, step, router]);

  // The polling screen replaces the current step in place (no route change),
  // so the browser never resets scroll on its own — without this, a buyer
  // who was scrolled down filling the form would land on a blank viewport.
  useEffect(() => {
    if (step === "polling") window.scrollTo({ top: 0 });
  }, [step]);

  // Poll M-Pesa payment status once STK push has been sent. Ticks every
  // second so the UI can show a live countdown, but only actually hits the
  // status endpoint every POLL_INTERVAL_MS.
  useEffect(() => {
    if (step !== "polling" || !checkoutRequestId) return;

    setSecondsRemaining(POLL_TIMEOUT_MS / 1000);

    let elapsed = 0;
    const timer = setInterval(async () => {
      elapsed += 1000;
      setSecondsRemaining(Math.max(0, Math.round((POLL_TIMEOUT_MS - elapsed) / 1000)));

      if (elapsed % POLL_INTERVAL_MS === 0) {
        try {
          const res = await fetch(`/api/mpesa/status/${checkoutRequestId}`);
          const data = await res.json().catch(() => ({}));

          if (res.ok && data.status === "success") {
            clearInterval(timer);
            clearCart();
            toast.success("Payment confirmed!");
            router.push(`/orders/${orderGroupId}`);
            return;
          }

          if (res.ok && data.status === "failed") {
            clearInterval(timer);
            setPollFailed(true);
            return;
          }
        } catch {
          // transient network error — keep polling until the timeout
        }
      }

      if (elapsed >= POLL_TIMEOUT_MS) {
        clearInterval(timer);
        setPollTimedOut(true);
      }
    }, 1000);

    return () => clearInterval(timer);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [step, checkoutRequestId]);

  async function updateAddressPin(sel: GeoSelection) {
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
      toast.success("Location pinned");
    } catch {
      toast.error("Failed to save location. Try again.");
    } finally {
      setPinSaving(false);
    }
  }

  async function placeOrder() {
    if (!selectedAddressId) { toast.error("Select a delivery address"); return; }
    if (addressIncomplete) { toast.error("Add the ward to your delivery address first"); return; }
    if (feeFailed) { toast.error("We couldn't work out your delivery fee. Reload and try again."); return; }
    if (!phone.trim()) { toast.error("Enter the phone number to pay with"); return; }

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
      setOrderGroupId(orderJson.id);

      await sendStkPush(orderJson.id);
    } catch {
      toast.error("Something went wrong. Try again.");
    } finally {
      setLoading(false);
    }
  }

  async function sendStkPush(targetOrderGroupId: string) {
    setPollFailed(false);
    setPollTimedOut(false);
    setRefreshMessage("");

    const res = await fetch("/api/mpesa", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ order_group_id: targetOrderGroupId, phone }),
    });
    const json = await res.json();
    if (!res.ok) { toast.error(json.detail ?? "Could not start M-Pesa payment"); return; }

    setCheckoutRequestId(json.checkout_request_id);
    setStep("polling");
  }

  async function retry() {
    if (!orderGroupId) return;
    setLoading(true);
    try {
      await sendStkPush(orderGroupId);
    } finally {
      setLoading(false);
    }
  }

  // Manual one-off re-check for the "Refresh Status" button shown after the
  // poller gives up — the buyer may have finished entering their PIN after
  // our poll window closed, so this re-asks without sending a new STK push.
  async function refreshStatus() {
    if (!checkoutRequestId) return;
    setRefreshing(true);
    setRefreshMessage("");
    try {
      const res = await fetch(`/api/mpesa/status/${checkoutRequestId}`);
      const data = await res.json().catch(() => ({}));

      if (res.ok && data.status === "success") {
        clearCart();
        toast.success("Payment confirmed!");
        router.push(`/orders/${orderGroupId}`);
        return;
      }

      if (res.ok && data.status === "failed") {
        setPollTimedOut(false);
        setPollFailed(true);
        return;
      }

      setRefreshMessage("Still waiting for confirmation. Give it a moment and check again.");
    } catch {
      setRefreshMessage("Couldn't check status. Try again.");
    } finally {
      setRefreshing(false);
    }
  }

  if (items.length === 0 && step !== "polling") return null;

  if (step === "polling") {
    const unresolved = pollFailed || pollTimedOut;
    return (
      <div className="min-h-[60vh] flex items-center justify-center px-4 py-16">
        <div className="card w-full max-w-sm p-8 flex flex-col items-center text-center">
          {unresolved ? (
            <>
              <AlertTriangle size={40} className="text-amber mb-4" />
              <h2 className="text-2xl font-extrabold mb-2">We couldn&apos;t confirm your payment</h2>
              <p className="text-muted text-sm mb-2">
                The prompt may have been cancelled, timed out, or could still be processing. Refresh to check the
                latest status, or try again.
              </p>
              {refreshMessage && <p className="text-xs text-muted mb-2">{refreshMessage}</p>}
              <div className="flex flex-col gap-2 w-full mt-4">
                <button
                  onClick={refreshStatus}
                  disabled={refreshing}
                  className="btn-accent disabled:opacity-40 w-full gap-2"
                >
                  <RefreshCw size={16} className={refreshing ? "animate-spin" : ""} />
                  {refreshing ? "Checking…" : "Refresh Status"}
                </button>
                <button onClick={retry} disabled={loading} className="btn-outline disabled:opacity-40 w-full">
                  {loading ? "Retrying…" : "Try again"}
                </button>
              </div>
              <button onClick={() => router.push(`/orders/${orderGroupId}`)} className="text-sm text-muted underline underline-offset-2 mt-3">
                View order
              </button>
            </>
          ) : (
            <>
              <Smartphone size={40} className="text-amber mb-4" />
              <h2 className="text-2xl font-extrabold mb-2">Check your phone</h2>
              <p className="text-muted text-sm mb-2">
                Enter your M-Pesa PIN on the prompt sent to {phone} to complete your payment of {formatKES(total)}.
              </p>
              <p className="text-amber text-sm font-medium">Processing... ({secondsRemaining}s)</p>
            </>
          )}
        </div>
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
              <div className="flex items-center gap-3">
                {items[0]?.shop_id && <MessageSellerButton shopId={items[0].shop_id} />}
                <button onClick={() => router.push("/cart")} className="text-xs text-muted underline">Edit cart</button>
              </div>
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
                      <p className="text-sm font-medium">
                        {addr.first_name} {addr.last_name}
                        {addr.label && <span className="text-xs text-muted ml-1">({addr.label})</span>}
                        {!isAddressComplete(addr) && (
                          <span className="text-[10px] font-semibold uppercase tracking-wide text-amber bg-amber/15 rounded-full px-2 py-0.5 ml-2">
                            Incomplete
                          </span>
                        )}
                      </p>
                      <p className="text-xs text-muted">
                        {[addr.ward?.name, addr.town, addr.county].filter(Boolean).join(", ")}
                        {addr.sublocation ? ` · ${addr.sublocation}` : ""}
                        {" · "}{addr.phone}
                      </p>
                      {addr.id === selectedAddressId && addr.lat && addr.sublocation && (
                        <p className="text-xs text-green-600 mt-0.5">Pinned: {addr.sublocation}</p>
                      )}
                    </div>
                  </label>
                ))
              )}
              {selectedAddress && !selectedAddress.lat && (
                <button type="button" onClick={() => setMapOpen(true)} className="flex items-center gap-2 text-xs text-amber hover:underline pt-1">
                  <MapPin size={14} /> Pin delivery location on map
                </button>
              )}

              {selectedAddress && addressIncomplete && (
                <div className="rounded-lg border border-amber bg-amber/10 p-4">
                  <div className="flex gap-2.5">
                    <AlertTriangle size={18} className="text-amber shrink-0 mt-0.5" />
                    <div>
                      <p className="text-sm font-semibold">This address is missing its ward</p>
                      <p className="text-xs text-muted mt-1 leading-relaxed">
                        We need the ward to work out your delivery fee and get the rider to your door.
                        Add it below and you can carry on — it only takes a moment, and we&apos;ll
                        remember it for next time.
                      </p>
                    </div>
                  </div>
                  <CompleteAddressForm
                    address={selectedAddress}
                    onSaved={(updated) =>
                      setAddresses((prev) => prev.map((a) => (a.id === updated.id ? updated : a)))
                    }
                  />
                </div>
              )}
            </div>
          </section>

          {/* Step 3: Payment */}
          <section className="card overflow-hidden">
            <div className="px-5 py-3 border-b border-border bg-surface">
              <h2 className="font-semibold">3. Payment</h2>
            </div>
            <div className="p-4 space-y-2">
              <p className="text-xs text-muted">
                We&apos;ll send an M-Pesa prompt to this number. Enter your PIN there to complete payment.
              </p>
              <label className="block text-xs font-medium text-muted">M-Pesa phone number</label>
              <input
                type="tel"
                value={phone}
                onChange={(e) => { phoneTouchedRef.current = true; setPhone(e.target.value); }}
                placeholder="07XX XXX XXX"
                className="w-full rounded-lg border border-border bg-bg px-3 py-2 text-sm"
              />
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
            <div>
              <div className="flex justify-between text-sm">
                <span className="text-muted">Delivery</span>
                <span>
                  {addressIncomplete
                    ? <span className="text-amber italic">Add your ward</span>
                    : feeLoading
                      ? <span className="text-muted italic">Calculating…</span>
                      : feeFailed
                        ? <span className="text-danger italic">Unavailable</span>
                        : formatKES(deliveryFee)}
                </span>
              </div>
              {!feeLoading && !addressIncomplete && feeFailed && (
                <p className="text-xs text-danger mt-1.5 leading-relaxed">
                  We couldn&apos;t work out your delivery fee just now. Reload the page to try
                  again — we won&apos;t charge you until we can show you the full total.
                </p>
              )}
              {!feeLoading && !addressIncomplete && !feeFailed && feeExplanation && (
                <p className="text-xs text-muted mt-1.5 leading-relaxed">
                  {feeExplanation.band_label}
                  {Number(feeExplanation.weight_surcharge ?? 0) > 0 && (
                    <> · includes {formatKES(Number(feeExplanation.weight_surcharge))} for{" "}
                    {feeExplanation.billable_weight_kg}kg over the free weight allowance</>
                  )}
                  {shopIds.length > 1 && <> · one delivery covering all {shopIds.length} sellers</>}
                </p>
              )}
            </div>
            <div className="flex justify-between font-bold border-t border-border pt-3">
              <span>Total</span>
              <span className="text-ink text-lg">
                {feeFailed && !addressIncomplete ? "—" : formatKES(total)}
              </span>
            </div>
            <button
              onClick={placeOrder}
              disabled={loading || feeLoading || !selectedAddressId || addressIncomplete || feeFailed}
              className="btn-accent w-full disabled:opacity-40 mt-2"
            >
              {loading ? "Processing..." : "Pay →"}
            </button>
            {addressIncomplete && (
              <p className="text-xs text-amber text-center -mt-2">
                Add the ward to your delivery address to continue.
              </p>
            )}
          </div>
        </div>
      </div>

      {mapOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4" onClick={() => setMapOpen(false)}>
          <div className="w-full max-w-2xl" onClick={(e) => e.stopPropagation()}>
            <p className="mb-2 text-center text-sm font-medium text-white">
              Drop the pin where our rider should deliver — switch between Satellite and Streets
            </p>
            <LocationPicker
              initial={selectedAddress?.lat != null && selectedAddress.lng != null ? { lat: selectedAddress.lat, lng: selectedAddress.lng } : undefined}
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

/**
 * Fills in the ward on an address that predates the geography tables. The
 * county is prefilled but stays editable, because a legacy address may hold a
 * county name that no longer matches the geography table exactly — in which
 * case the sub-county list comes back empty and re-picking is the way out.
 */
function CompleteAddressForm({
  address,
  onSaved,
}: {
  address: UserAddress;
  onSaved: (updated: UserAddress) => void;
}) {
  // Trimmed, because legacy rows hold values like "Nairobi " that 404 the
  // sub-county lookup and match no option in the county select.
  const [county, setCounty] = useState((address.county ?? "").trim());
  const [subcountyId, setSubcountyId] = useState("");
  const [wardId, setWardId] = useState("");
  const [saving, setSaving] = useState(false);

  const { data: counties } = useQuery({
    queryKey: ["geography", "counties"],
    queryFn: () => fetchList<County>("/api/geography/counties"),
  });

  const { data: subcounties } = useQuery({
    queryKey: ["geography", "subcounties", county],
    queryFn: () =>
      fetchList<SubCounty>(`/api/geography/counties/${encodeURIComponent(county)}/subcounties`),
    enabled: !!county,
  });

  const { data: wards } = useQuery({
    queryKey: ["geography", "wards", subcountyId],
    queryFn: () => fetchList<Ward>(`/api/geography/subcounties/${subcountyId}/wards`),
    enabled: !!subcountyId,
  });

  const countyUnmatched = !!county && subcounties?.length === 0;

  async function save() {
    if (!wardId) { toast.error("Select your sub-county and ward"); return; }
    setSaving(true);
    try {
      const res = await fetch(`/api/account/addresses/${address.id}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ county, ward_id: wardId }),
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) { toast.error(data.detail ?? "Could not save the address"); return; }
      toast.success("Address updated");
      onSaved(data as UserAddress);
    } catch {
      toast.error("Could not save the address. Try again.");
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="mt-4 space-y-3">
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
        <div>
          <label className="text-xs font-medium block mb-1">County</label>
          <select
            value={county}
            onChange={(e) => { setCounty(e.target.value); setSubcountyId(""); setWardId(""); }}
            className="input-field"
          >
            <option value="">Select county</option>
            {counties?.map((c) => <option key={c.id} value={c.name}>{c.name}</option>)}
          </select>
        </div>
        <div>
          <label className="text-xs font-medium block mb-1">Sub-county</label>
          <select
            value={subcountyId}
            onChange={(e) => { setSubcountyId(e.target.value); setWardId(""); }}
            className="input-field disabled:opacity-50"
            disabled={!county}
          >
            <option value="">Select sub-county</option>
            {subcounties?.map((s) => <option key={s.id} value={s.id}>{s.name}</option>)}
          </select>
        </div>
        <div>
          <label className="text-xs font-medium block mb-1">Ward</label>
          <select
            value={wardId}
            onChange={(e) => setWardId(e.target.value)}
            className="input-field disabled:opacity-50"
            disabled={!subcountyId}
          >
            <option value="">Select ward</option>
            {wards?.map((w) => <option key={w.id} value={w.id}>{w.name}</option>)}
          </select>
        </div>
      </div>

      {countyUnmatched && (
        <p className="text-xs text-muted">
          We couldn&apos;t find sub-counties for &ldquo;{county}&rdquo;. Pick your county from the
          list above to continue.
        </p>
      )}

      <button onClick={save} disabled={saving || !wardId} className="btn-accent disabled:opacity-40">
        {saving ? "Saving…" : "Save address"}
      </button>
    </div>
  );
}
