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

function addDays(date: Date, days: number): Date {
  const result = new Date(date);
  result.setDate(result.getDate() + days);
  return result;
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

  const plan = plans.find((p) => p.code === subscription.plan.code) ?? subscription.plan;
  const isAnnual = subscription.billing_interval === "annual";
  const price = isAnnual && plan.price_yearly ? plan.price_yearly : plan.price_monthly;
  const today = new Date();
  const trialEnd = subscription.current_period_end ? new Date(subscription.current_period_end) : addDays(today, 30);
  const nextCharge = addDays(trialEnd, 0);
  const remaining = daysLeft(subscription.current_period_end);

  // "active" in the DB but never actually paid for — a one-time grace window
  // given to shops that predate the subscription system, so they aren't
  // enforced on day one. Shown as its own state rather than "Active".
  const isGracePeriod = subscription.status === "active" && subscription.awaiting_first_payment;

  const statusCopy = isGracePeriod
    ? { label: "Pending activation", tone: "text-progress" }
    : STATUS_COPY[subscription.status];
  const needsRenewal = subscription.status !== "active";
  const buttonLabel = isGracePeriod
    ? "Activate now"
    : subscription.status === "trialing"
      ? "Subscribe now"
      : needsRenewal
        ? "Renew now"
        : "Renew early";

  let helpText: string;
  if (subscription.status === "trialing") {
    helpText = `Your ${subscription.plan.name} plan is in a ${plan.trial_days || 30}-day free trial. Subscribe before ${formatDate(subscription.current_period_end)} to keep your shop live.`;
  } else if (isGracePeriod) {
    helpText = `You have ${remaining} day${remaining === 1 ? "" : "s"} left to activate your ${subscription.plan.name} plan before it's enforced — activate now to lock it in, no need to wait.`;
  } else if (subscription.status === "cancelled") {
    helpText = "Your shop is suspended and hidden from Ekshop until you renew.";
  } else if (subscription.status === "past_due") {
    helpText = "Renew now to avoid your shop being taken down.";
  } else {
    helpText = "Renew early any time to extend your subscription — no need to wait for it to run out.";
  }

  if (subscription.status === "trialing") {
    return (
      <div className="max-w-5xl mx-auto">
        <div className="flex items-center justify-between mb-8">
          <div>
            <h1 className="text-2xl font-bold">Try {plan.name} for free</h1>
            <p className="text-sm text-muted mt-1">Free {plan.trial_days || 30}-day trial, cancel any time</p>
          </div>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* Left column - plan selection */}
          <div className="lg:col-span-2 space-y-6">
            <div className="card p-6 space-y-4">
              <div className="inline-flex rounded-lg border border-border p-1 bg-surface">
                {(["monthly", "annual"] as const).map((option) => (
                  <button
                    key={option}
                    type="button"
                    className={`px-4 py-2 text-sm rounded-md transition-colors ${
                      (option === "annual" ? isAnnual : !isAnnual) ? "bg-amber text-ink font-semibold" : "text-muted"
                    }`}
                  >
                    {option === "monthly" ? "Monthly" : "Yearly"}
                  </button>
                ))}
              </div>

              <div className="grid gap-4 sm:grid-cols-2">
                <div className={`rounded-lg border-2 p-5 ${isAnnual ? "border-amber" : "border-border"}`}>
                  <div className="flex items-center justify-between mb-2">
                    <span className="font-semibold text-lg">{plan.name}</span>
                    {isAnnual && plan.price_yearly && (
                      <span className="text-xs bg-success/15 text-success px-2 py-1 rounded-full font-medium">
                        Best value - Save KES {Number(plan.price_monthly) * 12 - Number(plan.price_yearly)}
                      </span>
                    )}
                  </div>
                  <div className="text-3xl font-bold">
                    {formatKES(price)}
                    <span className="text-sm font-normal text-muted"> / {isAnnual ? "year" : "month"}</span>
                  </div>
                  <div className="text-sm text-muted mt-2">
                    {plan.max_products ? `Up to ${plan.max_products} products` : "Unlimited products"}
                  </div>
                </div>
              </div>

              <div className="space-y-3">
                <div className="flex items-start gap-3">
                  <div className="w-6 h-6 rounded-full bg-success/15 text-success flex items-center justify-center text-xs font-bold flex-shrink-0 mt-0.5">✓</div>
                  <p className="text-sm text-muted">Free {plan.trial_days || 30}-day trial, cancel any time</p>
                </div>
                <div className="flex items-start gap-3">
                  <div className="w-6 h-6 rounded-full bg-success/15 text-success flex items-center justify-center text-xs font-bold flex-shrink-0 mt-0.5">✓</div>
                  <p className="text-sm text-muted">We&apos;ll remind you before your trial ends</p>
                </div>
              </div>
            </div>
          </div>

          {/* Right column - timeline */}
          <div className="space-y-6">
            <div className="card p-6 space-y-6">
              <div className="flex items-start gap-3">
                <div className="w-8 h-8 rounded-full bg-success/15 text-success flex items-center justify-center flex-shrink-0">
                  <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" /></svg>
                </div>
                <div>
                  <p className="text-sm font-semibold">Today</p>
                  <p className="text-xs text-muted">Get free access to all of {plan.name}</p>
                </div>
              </div>

              <div className="ml-4 border-l-2 border-border h-8" />

              <div className="flex items-start gap-3">
                <div className="w-8 h-8 rounded-full bg-amber/15 text-amber flex items-center justify-center flex-shrink-0">
                  <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 17h5l-1.405-1.405A2.032 2.032 0 0118 14.158V11a6.002 6.002 0 00-4-5.659V5a2 2 0 10-4 0v.341C7.67 6.165 6 8.388 6 11v3.159c0 .538-.214 1.055-.595 1.436L4 17h5m6 0v1a3 3 0 11-6 0v-1m6 0H9" /></svg>
                </div>
                <div>
                  <p className="text-sm font-semibold">{trialEnd.toLocaleDateString("en-KE", { day: "numeric", month: "short", year: "numeric" })}</p>
                  <p className="text-xs text-muted">We&apos;ll remind you that your trial is about to end</p>
                </div>
              </div>

              <div className="ml-4 border-l-2 border-border h-8" />

              <div className="flex items-start gap-3">
                <div className="w-8 h-8 rounded-full bg-amber/15 text-amber flex items-center justify-center flex-shrink-0">
                  <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8c-1.657 0-3 .895-3 2s1.343 2 3 2 3 .895 3 2-1.343 2-3 2m0-8c1.11 0 2.08.402 2.599 1M12 8V7m0 1v8m0 0v1m0-1c-1.11 0-2.08-.402-2.599-1M21 12a9 9 0 11-18 0 9 9 0 0118 0z" /></svg>
                </div>
                <div>
                  <p className="text-sm font-semibold">{nextCharge.toLocaleDateString("en-KE", { day: "numeric", month: "short", year: "numeric" })}</p>
                  <p className="text-xs text-muted">We&apos;ll automatically renew your plan, unless you cancel beforehand</p>
                </div>
              </div>
            </div>

            <div className="card p-6 space-y-4">
              <div className="flex items-center justify-between">
                <span className="font-semibold">Due today</span>
                <div className="flex items-center gap-2">
                  <span className="text-xs bg-success/15 text-success px-2 py-1 rounded-full font-medium">
                    {plan.trial_days || 30} day free trial
                  </span>
                  <span className="text-xl font-bold">KES 0</span>
                </div>
              </div>
              <div className="flex items-center justify-between text-sm text-muted">
                <span>Next charge {nextCharge.toLocaleDateString("en-KE", { day: "numeric", month: "long", year: "numeric" })}</span>
                <span className="font-semibold text-ink">{formatKES(price)}</span>
              </div>

              <PlanPicker
                plans={plans}
                currentPlanCode={subscription.plan.code}
                currentInterval={subscription.billing_interval}
                defaultLabel={buttonLabel}
              />

              <p className="text-xs text-muted text-center">
                By continuing, you agree to the <a href="/terms" className="underline">Terms of Use</a> applicable to Ekshop and confirm you have read our <a href="/privacy" className="underline">Privacy Policy</a>.
              </p>
            </div>
          </div>
        </div>
      </div>
    );
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
