"use client";

import { use } from "react";
import Link from "next/link";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import {
  ArrowLeft,
  BadgeCheck,
  Calendar,
  Loader2,
  Mail,
  MapPin,
  Package,
  Phone,
  Star,
} from "lucide-react";
import { AdminShopDetail } from "@/types/interface";
import { formatKES, resolveImageUrl, decodeHtml } from "@/lib/utils";
import ActionButton from "@/components/admin/ActionButton";

const STATUS_STYLES: Record<string, string> = {
  pending: "bg-amber/15 text-amber",
  active: "bg-success/10 text-success",
  suspended: "bg-danger/10 text-danger",
};

function date(value?: string | null) {
  if (!value) return "—";
  return new Date(value).toLocaleDateString("en-KE", {
    day: "numeric",
    month: "short",
    year: "numeric",
  });
}

function Field({ label, value, icon: Icon }: { label: string; value: React.ReactNode; icon?: typeof Mail }) {
  return (
    <div className="min-w-0">
      <p className="text-xs text-muted mb-0.5">{label}</p>
      <p className="text-sm font-medium flex items-center gap-1.5 break-words">
        {Icon && <Icon size={13} className="text-muted shrink-0" />}
        {value || "—"}
      </p>
    </div>
  );
}

export default function AdminSellerDetailPage({ params }: { params: Promise<{ shopId: string }> }) {
  const { shopId } = use(params);
  const queryClient = useQueryClient();

  const { data, isPending, isError } = useQuery({
    queryKey: ["admin", "shop", shopId],
    queryFn: async (): Promise<AdminShopDetail> => {
      const res = await fetch(`/api/admin/shops/${shopId}`);
      if (!res.ok) throw new Error("Could not load seller");
      return res.json();
    },
  });

  function refresh() {
    queryClient.invalidateQueries({ queryKey: ["admin", "shop", shopId] });
    queryClient.invalidateQueries({ queryKey: ["admin", "shops"] });
  }

  async function act(action: "verify" | "suspend" | "feature", success: string) {
    const res = await fetch(`/api/admin/shops/${shopId}/${action}`, { method: "PATCH" });
    if (!res.ok) { toast.error(`Could not ${action} shop`); return false; }
    toast.success(success);
    refresh();
    return true;
  }

  if (isPending) {
    return (
      <div className="flex items-center justify-center py-20">
        <Loader2 size={22} className="animate-spin text-muted" />
      </div>
    );
  }

  if (isError || !data) {
    return (
      <div className="card p-10 text-center">
        <p className="text-sm text-muted mb-4">Could not load this seller.</p>
        <Link href="/admin/sellers" className="text-amber text-sm underline underline-offset-2">
          Back to sellers
        </Link>
      </div>
    );
  }

  const { shop, owner, subscription } = data;
  const ownerName = owner ? `${owner.first_name} ${owner.last_name}`.trim() : null;

  return (
    <div>
      <Link
        href="/admin/sellers"
        className="inline-flex items-center gap-1.5 text-sm text-muted hover:text-ink mb-4"
      >
        <ArrowLeft size={15} /> Sellers
      </Link>

      {/* Header */}
      <div className="card p-5 mb-4">
        <div className="flex flex-col gap-4 md:flex-row md:items-start md:justify-between">
          <div className="flex items-start gap-3 min-w-0">
            <div className="w-12 h-12 rounded-full bg-surface flex items-center justify-center text-lg font-bold text-muted shrink-0 overflow-hidden">
              {shop.logo_url ? (
                // eslint-disable-next-line @next/next/no-img-element
                <img src={resolveImageUrl(shop.logo_url)} alt="" className="w-full h-full object-cover" />
              ) : (
                decodeHtml(shop.name).charAt(0)
              )}
            </div>
            <div className="min-w-0">
              <div className="flex items-center gap-1.5 flex-wrap">
                <h1 className="text-xl font-bold break-words">{decodeHtml(shop.name)}</h1>
                {shop.is_verified && <BadgeCheck size={16} className="text-info shrink-0" />}
                {shop.is_featured && <Star size={15} className="text-amber fill-current shrink-0" />}
              </div>
              <div className="flex flex-wrap items-center gap-2 mt-1.5 text-xs text-muted">
                {shop.status && (
                  <span className={`px-2 py-0.5 rounded-full font-medium capitalize ${STATUS_STYLES[shop.status] ?? "bg-surface"}`}>
                    {shop.status}
                  </span>
                )}
                <span>/{shop.slug}</span>
                <span>· Joined {date(shop.created_at)}</span>
              </div>
            </div>
          </div>

          <div className="flex flex-wrap gap-2 shrink-0">
            {!shop.is_verified && (
              <ActionButton variant="accent" pendingLabel="Verifying…" onAction={() => act("verify", "Shop verified")}>
                Verify
              </ActionButton>
            )}
            <ActionButton
              pendingLabel="Saving…"
              onAction={() => act("feature", shop.is_featured ? "Shop unfeatured" : "Shop featured")}
            >
              {shop.is_featured ? "Unfeature" : "Feature"}
            </ActionButton>
            <ActionButton
              variant="danger"
              pendingLabel="Suspending…"
              confirm="Suspend this shop? The seller will no longer be able to sell."
              onAction={() => act("suspend", "Shop suspended")}
            >
              Suspend
            </ActionButton>
            <Link
              href={`/shops/${shop.slug}`}
              target="_blank"
              className="inline-flex items-center text-xs font-medium py-1.5 px-3 rounded-md border border-border text-muted hover:bg-ink/5"
            >
              View storefront
            </Link>
          </div>
        </div>

        {data.description && (
          <p className="text-sm text-muted mt-4 pt-4 border-t border-border whitespace-pre-line">
            {decodeHtml(data.description)}
          </p>
        )}
      </div>

      {/* Numbers */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3 mb-4">
        {[
          { label: "Revenue", value: formatKES(data.revenue) },
          { label: "Orders", value: data.total_orders },
          { label: "Products", value: `${data.active_products} live / ${data.total_products}` },
          { label: "Rating", value: `${parseFloat(shop.rating_avg || "0").toFixed(1)} (${shop.rating_count})` },
        ].map((stat) => (
          <div key={stat.label} className="card p-4">
            <p className="text-xs text-muted mb-1">{stat.label}</p>
            <p className="text-lg font-bold">{stat.value}</p>
          </div>
        ))}
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4 mb-4">
        {/* Owner */}
        <div className="card p-5">
          <h2 className="font-semibold mb-4">Seller</h2>
          {owner ? (
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <Field label="Name" value={ownerName} />
              <Field label="Account status" value={<span className="capitalize">{owner.status}</span>} />
              <Field
                label="Email"
                icon={Mail}
                value={<a href={`mailto:${owner.email}`} className="hover:text-amber break-all">{owner.email}</a>}
              />
              <Field
                label="Phone"
                icon={Phone}
                value={owner.phone ? <a href={`tel:${owner.phone}`} className="hover:text-amber">{owner.phone}</a> : null}
              />
              <Field label="Signed up" icon={Calendar} value={date(owner.created_at)} />
              <Field label="Last login" icon={Calendar} value={date(owner.last_login_at)} />
            </div>
          ) : (
            <p className="text-sm text-muted">No account linked to this shop.</p>
          )}
        </div>

        {/* Shop & billing */}
        <div className="card p-5">
          <h2 className="font-semibold mb-4">Shop &amp; billing</h2>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <Field
              label="Location"
              icon={MapPin}
              value={[data.exact_location, shop.town, shop.county].filter(Boolean).join(", ")}
            />
            <Field label="Shop phone" icon={Phone} value={data.phone} />
            <Field
              label="Plan"
              value={
                subscription ? (
                  <span>
                    {subscription.plan_name ?? "—"}
                    <span className="text-muted font-normal"> · {subscription.billing_interval}</span>
                  </span>
                ) : (
                  "No subscription"
                )
              }
            />
            <Field
              label="Billing status"
              value={
                subscription ? (
                  <span className="capitalize">
                    {subscription.status.replace("_", " ")}
                    {subscription.awaiting_first_payment && (
                      <span className="ml-1.5 text-[10px] uppercase tracking-wide text-amber font-semibold">
                        unpaid
                      </span>
                    )}
                  </span>
                ) : null
              }
            />
            <Field label="Renews / expires" icon={Calendar} value={date(subscription?.current_period_end)} />
            <Field
              label="Product allowance"
              value={
                subscription?.max_products != null
                  ? `${data.active_products} of ${subscription.max_products} used`
                  : subscription
                    ? "Unlimited"
                    : null
              }
            />
            <Field
              label="Payout methods"
              value={data.payment_methods.length ? data.payment_methods.join(", ") : "None set"}
            />
            <Field label="Drafts" value={`${data.draft_products} unpublished`} />
          </div>
        </div>
      </div>

      {/* Recent products */}
      <div className="card p-5">
        <h2 className="font-semibold mb-4 flex items-center gap-2">
          <Package size={16} className="text-muted" /> Latest products
        </h2>
        {data.recent_products.length === 0 ? (
          <p className="text-sm text-muted">This seller hasn&apos;t listed anything yet.</p>
        ) : (
          <ul className="divide-y divide-border -mx-5">
            {data.recent_products.map((product) => (
              <li key={product.id} className="flex items-center gap-3 px-5 py-3">
                <div className="w-10 h-10 rounded bg-surface overflow-hidden shrink-0">
                  {product.images?.[0] && (
                    // eslint-disable-next-line @next/next/no-img-element
                    <img
                      src={resolveImageUrl(product.images[0].url)}
                      alt=""
                      className="w-full h-full object-cover"
                    />
                  )}
                </div>
                <div className="min-w-0 flex-1">
                  <p className="text-sm font-medium truncate">{decodeHtml(product.name)}</p>
                  <p className="text-xs text-muted">
                    {formatKES(product.price)} · {product.stock_qty} in stock
                  </p>
                </div>
                <span className="text-xs font-medium px-2 py-0.5 rounded-full bg-surface capitalize shrink-0">
                  {product.status}
                </span>
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  );
}
