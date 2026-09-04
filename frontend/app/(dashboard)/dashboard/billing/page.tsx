import { serverFetch } from "@/lib/server-api";
import { Subscription } from "@/types/interface";
import { formatKES } from "@/lib/utils";
import RenewButton from "@/components/dashboard/RenewButton";

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

export default async function BillingPage() {
  const subscription = await serverFetch<Subscription>("/subscriptions/me").catch(() => null);

  if (!subscription) {
    return (
      <div className="card p-6">
        <h1 className="text-xl font-bold mb-2">Billing</h1>
        <p className="text-muted text-sm">No subscription found for your shop.</p>
      </div>
    );
  }

  const statusCopy = STATUS_COPY[subscription.status];
  const needsRenewal = subscription.status !== "active";

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
          <span className="font-semibold">{formatKES(subscription.plan.price_monthly)} / month</span>
        </div>
        <div className="flex items-center justify-between">
          <span className="text-sm text-muted">Status</span>
          <span className={`font-semibold ${statusCopy.tone}`}>{statusCopy.label}</span>
        </div>
        <div className="flex items-center justify-between">
          <span className="text-sm text-muted">
            {needsRenewal ? "Was due" : "Renews on"}
          </span>
          <span className="font-semibold">{formatDate(subscription.current_period_end)}</span>
        </div>

        {needsRenewal && (
          <div className="pt-2 border-t border-border">
            <p className="text-sm text-muted mb-3">
              {subscription.status === "cancelled"
                ? "Your shop is suspended and hidden from Ekshop until you renew."
                : "Renew now to avoid your shop being taken down."}
            </p>
            <RenewButton />
          </div>
        )}
      </div>
    </div>
  );
}
