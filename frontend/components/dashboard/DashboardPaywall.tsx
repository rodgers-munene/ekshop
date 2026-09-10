"use client";

import { usePathname } from "next/navigation";
import { Subscription, SubscriptionPlan } from "@/types/interface";
import { formatKES } from "@/lib/utils";
import PlanPicker from "./PlanPicker";

// Longest-prefix match, so /dashboard/products/new still reads as "Products".
const SECTIONS: [string, string][] = [
  ["/dashboard/products", "Products"],
  ["/dashboard/orders", "Orders"],
  ["/dashboard/billing", "Billing"],
  ["/dashboard/settings", "Settings"],
  ["/dashboard", "Your dashboard"],
];

function sectionName(pathname: string | null): string {
  if (!pathname) return "Your dashboard";
  return SECTIONS.find(([prefix]) => pathname.startsWith(prefix))?.[1] ?? "Your dashboard";
}

/**
 * Shown in place of every dashboard page while a seller's first subscription
 * payment is outstanding.
 *
 * The real enforcement is server-side — an unpaid seller's token only opens
 * their own profile, shop, subscription and the renew endpoint (see
 * dependencies/auth.py). This is the explanation of that, not the mechanism,
 * so it can afford to be welcoming rather than a hard error.
 */
export default function DashboardPaywall({
  subscription,
  plans,
  shopName,
}: {
  subscription: Subscription;
  plans: SubscriptionPlan[];
  shopName: string;
}) {
  const section = sectionName(usePathname());

  return (
    <div className="max-w-2xl mx-auto py-8">
      <div className="card p-6 md:p-8">
        <p className="text-xs font-semibold uppercase tracking-wide text-muted mb-2">
          {section} · Locked
        </p>
        <h1 className="text-2xl font-bold mb-2">Activate your shop to start selling</h1>
        <p className="text-muted text-sm mb-6">
          Your account is ready and your email is confirmed. {section} unlocks as soon as
          your first payment goes through — along with your storefront, product listings
          and orders.
        </p>

        <div className="rounded-lg border border-border bg-surface p-4 mb-6">
          <div className="flex items-baseline justify-between gap-3">
            <span className="text-sm text-muted">Chosen plan</span>
            <span className="font-semibold">{subscription.plan.name}</span>
          </div>
          <div className="flex items-baseline justify-between gap-3 mt-1">
            <span className="text-sm text-muted">Shop</span>
            <span className="font-semibold">{shopName}</span>
          </div>
          <div className="flex items-baseline justify-between gap-3 mt-1">
            <span className="text-sm text-muted">Due now</span>
            <span className="font-semibold">
              {formatKES(subscription.plan.price_monthly)}
            </span>
          </div>
        </div>

        <p className="text-sm font-medium mb-3">Confirm your plan and pay</p>
        <PlanPicker
          plans={plans}
          currentPlanCode={subscription.plan.code}
          currentInterval={subscription.billing_interval}
          defaultLabel="Pay & activate shop"
        />

        <p className="text-xs text-muted mt-6">
          You can switch plan or billing period here before paying — nothing is charged
          until you confirm on the payment page.
        </p>
      </div>
    </div>
  );
}
