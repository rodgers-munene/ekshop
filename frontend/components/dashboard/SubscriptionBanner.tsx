import Link from "next/link";
import { Subscription } from "@/types/interface";

function daysLeft(iso: string | null): number {
  if (!iso) return 0;
  const ms = new Date(iso).getTime() - Date.now();
  return Math.max(0, Math.ceil(ms / (1000 * 60 * 60 * 24)));
}

export default function SubscriptionBanner({ subscription }: { subscription: Subscription }) {
  if (
    subscription.status !== "past_due" &&
    subscription.status !== "cancelled" &&
    subscription.status !== "trialing"
  )
    return null;

  const isCancelled = subscription.status === "cancelled";
  const isPastDue = subscription.status === "past_due";
  const isTrialing = subscription.status === "trialing";

  let text = "";
  if (isCancelled) {
    text = "Your shop is suspended and hidden from Ekshop — renew now to reactivate it.";
  } else if (isPastDue) {
    text = "Your subscription payment is overdue — renew now to avoid your shop being suspended.";
  } else if (isTrialing) {
    const remaining = daysLeft(subscription.current_period_end);
    text = `Your ${subscription.plan.name} trial ends in ${remaining} day${remaining === 1 ? "" : "s"} — subscribe now to keep your shop live.`;
  }

  return (
    <div
      className={`px-4 py-3 text-sm text-white flex items-center justify-between gap-3 ${
        isCancelled ? "bg-danger" : isTrialing ? "bg-info" : "bg-progress"
      }`}
    >
      <span>{text}</span>
      <Link href="/dashboard/billing" className="underline font-semibold whitespace-nowrap">
        Go to billing
      </Link>
    </div>
  );
}
