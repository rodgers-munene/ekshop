"use client";

import { useState } from "react";
import { formatKES } from "@/lib/utils";
import StatCard from "@/components/dashboard/StatCard";
import {
  MerchantActivityMetrics,
  SalesDemandMetrics,
  CustomerRetentionMetrics,
  OperationsDeliveryMetrics,
} from "@/types/interface";

type Section = "merchants" | "sales" | "retention" | "operations";

const SECTIONS: { key: Section; label: string }[] = [
  { key: "merchants", label: "Merchant Activity" },
  { key: "sales", label: "Sales & Demand" },
  { key: "retention", label: "Customer Retention" },
  { key: "operations", label: "Operations & Delivery" },
];

export default function AdminAnalyticsClient({
  merchants,
  sales,
  retention,
  operations,
}: {
  merchants: MerchantActivityMetrics | null;
  sales: SalesDemandMetrics | null;
  retention: CustomerRetentionMetrics | null;
  operations: OperationsDeliveryMetrics | null;
}) {
  const [section, setSection] = useState<Section>("merchants");

  return (
    <div>
      <h1 className="text-2xl font-bold mb-2">Analytics</h1>
      <p className="text-sm text-muted mb-6">
        Merchant activity is a 7-day window; sales, retention, and operations are 30-day windows.
      </p>

      <div className="flex border-b border-border mb-6 overflow-x-auto">
        {SECTIONS.map(({ key, label }) => (
          <button
            key={key}
            onClick={() => setSection(key)}
            className={`px-4 py-2.5 text-sm font-medium whitespace-nowrap transition-colors border-b-2 -mb-px ${
              section === key ? "border-amber text-ink" : "border-transparent text-muted hover:text-ink"
            }`}
          >
            {label}
          </button>
        ))}
      </div>

      {section === "merchants" && (
        merchants ? (
          <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
            <StatCard label="Active merchants (7d)" value={merchants.active_merchants_7d} />
            <StatCard label="Active merchants (30d)" value={merchants.active_merchants_30d} />
            <StatCard label="Merchants receiving orders" value={merchants.merchants_receiving_orders} />
            <StatCard label="Merchants processing orders" value={merchants.merchants_processing_orders} />
            <StatCard label="Merchants with zero activity" value={merchants.merchants_zero_activity} />
            <StatCard label="Sellers logged in (7d)" value={merchants.sellers_logged_in} />
            <StatCard label="Products updated (7d)" value={merchants.products_updated} />
            <StatCard label="Avg. transactions / merchant" value={merchants.avg_transactions_per_merchant} />
          </div>
        ) : <p className="text-muted text-sm">Could not load merchant metrics.</p>
      )}

      {section === "sales" && (
        sales ? (
          <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
            <StatCard label="Total orders (30d)" value={sales.total_orders} />
            <StatCard label="GMV (30d)" value={formatKES(sales.gmv)} />
            <StatCard label="Average order value" value={formatKES(sales.average_order_value)} />
            <StatCard label="New customers" value={sales.new_customers} />
            <StatCard label="Repeat customers" value={sales.repeat_customers} />
            <StatCard label="Customer acquisition rate" value={`${sales.customer_acquisition_rate}%`} />
            <StatCard label="Cart abandonment rate" value={`${sales.cart_abandonment_rate}%`} />
            <StatCard label="Order cancellation rate" value={`${sales.order_cancellation_rate}%`} />
          </div>
        ) : <p className="text-muted text-sm">Could not load sales metrics.</p>
      )}

      {section === "retention" && (
        retention ? (
          <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
            <StatCard label="New customers" value={retention.new_customers} />
            <StatCard label="Returning customers" value={retention.returning_customers} />
            <StatCard label="Repeat purchase rate" value={`${retention.repeat_purchase_rate}%`} />
            <StatCard label="Churn rate" value={`${retention.churn_rate}%`} />
            <StatCard label="30-day retention" value={`${retention.retention_30d}%`} />
            <StatCard label="Orders per customer" value={retention.orders_per_customer} />
            <StatCard label="Avg. days between purchases" value={retention.avg_days_between_purchases} />
            <StatCard label="Customer complaints" value={retention.customer_complaints} />
          </div>
        ) : <p className="text-muted text-sm">Could not load retention metrics.</p>
      )}

      {section === "operations" && (
        operations ? (
          <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
            <StatCard label="Orders received" value={operations.orders_received} />
            <StatCard label="Orders accepted" value={operations.orders_accepted} />
            <StatCard label="Orders fulfilled" value={operations.orders_fulfilled} />
            <StatCard label="Orders cancelled" value={operations.orders_cancelled} />
            <StatCard label="Avg. dispatch time" value={`${operations.avg_dispatch_time_hours}h`} />
            <StatCard label="Avg. delivery time" value={`${operations.avg_delivery_time_hours}h`} />
            <StatCard
              label="On-time delivery %"
              value={operations.on_time_delivery_rate === null ? "—" : `${operations.on_time_delivery_rate}%`}
            />
            <StatCard label="Failed deliveries" value={operations.failed_deliveries} />
            <StatCard label="Rider utilization" value={operations.rider_utilization} />
            <StatCard label="Delivery revenue" value={formatKES(operations.delivery_revenue)} />
          </div>
        ) : <p className="text-muted text-sm">Could not load operations metrics.</p>
      )}
    </div>
  );
}
