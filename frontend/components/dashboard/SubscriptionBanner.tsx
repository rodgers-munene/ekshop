"use client";

import { useSyncExternalStore } from "react";
import Link from "next/link";
import { X } from "lucide-react";
import { Subscription } from "@/types/interface";

// A dismissed trial notice comes back once for the final days of the trial,
// so a seller who closed it early still sees it before the shop locks.
const FINAL_DAYS = 3;
const DISMISS_EVENT = "ekshop:banner-dismissed";
// Fallback for when localStorage is unavailable, so closing still works until reload.
const dismissedThisSession = new Set<string>();

function daysLeft(iso: string | null): number {
  if (!iso) return 0;
  const ms = new Date(iso).getTime() - Date.now();
  return Math.max(0, Math.ceil(ms / (1000 * 60 * 60 * 24)));
}

function subscribe(callback: () => void) {
  window.addEventListener(DISMISS_EVENT, callback);
  window.addEventListener("storage", callback);
  return () => {
    window.removeEventListener(DISMISS_EVENT, callback);
    window.removeEventListener("storage", callback);
  };
}

function isDismissed(key: string): boolean {
  if (dismissedThisSession.has(key)) return true;
  try {
    return localStorage.getItem(key) === "1";
  } catch {
    return false;
  }
}

export default function SubscriptionBanner({ subscription }: { subscription: Subscription }) {
  const isCancelled = subscription.status === "cancelled";
  const isPastDue = subscription.status === "past_due";
  const isTrialing = subscription.status === "trialing";
  const remaining = daysLeft(subscription.current_period_end);

  const dismissKey = `ekshop_trial_banner_dismissed:${subscription.current_period_end}:${remaining <= FINAL_DAYS ? "final" : "early"}`;
  const dismissed = useSyncExternalStore(
    subscribe,
    () => isTrialing && isDismissed(dismissKey),
    () => false,
  );

  if (!isCancelled && !isPastDue && !isTrialing) return null;
  if (dismissed) return null;

  let text = "";
  if (isCancelled) {
    text = "Your shop is suspended and hidden from Ekshop. Renew now to reactivate it.";
  } else if (isPastDue) {
    text = "Your subscription payment is overdue. Renew now to avoid your shop being suspended.";
  } else {
    text = `Your ${subscription.plan.name} trial ends in ${remaining} day${remaining === 1 ? "" : "s"}. Subscribe now to keep your shop live.`;
  }

  function dismiss() {
    dismissedThisSession.add(dismissKey);
    try {
      localStorage.setItem(dismissKey, "1");
    } catch {
      // storage unavailable: the notice shows again on the next full page load
    }
    window.dispatchEvent(new Event(DISMISS_EVENT));
  }

  return (
    <div
      className={`px-4 py-3 text-sm text-white flex items-center justify-between gap-3 ${
        isCancelled ? "bg-danger" : isTrialing ? "bg-info" : "bg-progress"
      }`}
    >
      <span>{text}</span>
      <div className="flex items-center gap-3">
        <Link href="/dashboard/billing" className="underline font-semibold whitespace-nowrap">
          Go to billing
        </Link>
        {/* Only the trial notice can be closed; overdue and suspended warnings stay until paid. */}
        {isTrialing && (
          <button
            type="button"
            onClick={dismiss}
            className="rounded-md p-1 hover:bg-white/15"
            aria-label="Dismiss"
          >
            <X size={16} />
          </button>
        )}
      </div>
    </div>
  );
}
