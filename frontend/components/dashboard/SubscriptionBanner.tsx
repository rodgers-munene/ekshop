import Link from "next/link";
import { Subscription } from "@/types/interface";

export default function SubscriptionBanner({ subscription }: { subscription: Subscription }) {
  if (subscription.status !== "past_due" && subscription.status !== "cancelled") return null;

  const isCancelled = subscription.status === "cancelled";

  return (
    <div className={`px-4 py-3 text-sm text-white flex items-center justify-between gap-3 ${isCancelled ? "bg-danger" : "bg-progress"}`}>
      <span>
        {isCancelled
          ? "Your shop is suspended and hidden from Ekshop — renew now to reactivate it."
          : "Your subscription payment is overdue — renew now to avoid your shop being suspended."}
      </span>
      <Link href="/dashboard/billing" className="underline font-semibold whitespace-nowrap">
        Go to billing
      </Link>
    </div>
  );
}
