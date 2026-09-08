import { serverFetch } from "@/lib/server-api";
import { Subscription, SubscriptionPlan } from "@/types/interface";
import { formatKES } from "@/lib/utils";
import PlanPicker from "@/components/dashboard/PlanPicker";

const STATUS_COPY: Record<Subscription["status"], { label: string; tone: string }> = {
  active: { label: "Active", tone: "text-success" },
  past_due: { label: "Payment overdue", tone: "text-danger" },
  cancelled: { label: "Suspended", tone: "text-danger" },
  pending_payment: { label: "Awaiting payment", tone: "text-progress" },
  trialing: { label: "Trial", tone: "text-info" },
};

function formatDate(iso: string | null) {
  if (!iso) return "-";
  return new Date(iso).toLocaleDateString("en-KE", { day: "numeric", month: "long", year: "numeric" });
}

function daysLeft(iso: string | null): number {
  if (!iso) return 0;
  const ms = new Date(iso).getTime() - Date.now();
  return Math.max(0, Math.ceil(ms / (1000 * 60 * 60 * 24)));
}

export default async function BillingPage() {
  const [subscription, plans] = await Promise.all([
    serverFetch<Subscription>("/subscriptions/me").catch(() => null),
    serverFetch<SubscriptionPlan[]>("/subscriptions/plans").catch(() => []),
  ]);

  if (!subscription) {
    return (
      <div className="card p-6">
        <h1 className="text-xl font-bold mb-2">Billing</h1>
        <p className="text-muted text-sm">No subscription found for your shop.</p>
      </div>
    );
  }

  // "active" in the DB but never actually paid for — a one-time grace window
  // given to shops that predate the subscription system, so they aren't
  // enforced on day one. Shown as its own state rather than "Active".
  const isGracePeriod = subscription.status === "active" && subscription.awaiting_first_payment;

  const statusCopy = isGracePeriod
    ? { label: "Pending activation", tone: "text-progress" }
    : STATUS_COPY[subscription.status];
  const needsRenewal = subscription.status !== "active";
  const remaining = daysLeft(subscription.current_period_end);

  const buttonLabel = isGracePeriod ? "Activate now" : needsRenewal ? "Renew now" : "Renew early";

  let helpText: string;
  if (isGracePeriod) {
    helpText = `You have ${remaining} day${remaining === 1 ? "" : "s"} left to activate your ${subscription.plan.name} plan before it's enforced — activate now to lock it in, no need to wait.`;
  } else if (subscription.status === "cancelled") {
    helpText = "Your shop is suspended and hidden from Ekshop until you renew.";
  } else if (subscription.status === "past_due") {
    helpText = "Renew now to avoid your shop being taken down.";
  } else {
    helpText = "Renew early any time to extend your subscription — no need to wait for it to run out.";
  }

  return (
    <div className="space-y-6">
      <h1 className="text-xl font-bold">Billing</h1>

      <div className="card p-6 space-y-4">
        <div className="flex items-center justify-between">
          <span className="text-sm text-muted">Plan</span>
          <span className="font-semibold">{subscription.plan.name}</span>
        </div>
        <div className="flex items-center justify-between">
          <span className="text-sm text-muted">Price</span>
          <span className="font-semibold">
            {subscription.billing_interval === "annual" && subscription.plan.price_yearly
              ? `${formatKES(subscription.plan.price_yearly)} / year`
              : `${formatKES(subscription.plan.price_monthly)} / month`}
          </span>
        </div>
        <div className="flex items-center justify-between">
          <span className="text-sm text-muted">Status</span>
          <span className={`font-semibold ${statusCopy.tone}`}>{statusCopy.label}</span>
        </div>
        <div className="flex items-center justify-between">
          <span className="text-sm text-muted">
            {isGracePeriod ? "Activate by" : needsRenewal ? "Was due" : "Renews on"}
          </span>
          <span className="font-semibold">{formatDate(subscription.current_period_end)}</span>
        </div>

        <div className="pt-2 border-t border-border">
          <p className="text-sm text-muted mb-3">{helpText}</p>
          <PlanPicker
            plans={plans}
            currentPlanCode={subscription.plan.code}
            currentInterval={subscription.billing_interval}
            defaultLabel={buttonLabel}
          />
        </div>
      </div>
    </div>
  );
}
