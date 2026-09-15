"use client";

import { useEffect, useState } from "react";
import { formatKES } from "@/lib/utils";
import StatCard from "@/components/dashboard/StatCard";
import PeriodFilter, { PeriodKey } from "@/components/dashboard/PeriodFilter";
import {
  MerchantActivityMetrics,
  SalesDemandMetrics,
  CustomerRetentionMetrics,
  OperationsDeliveryMetrics,
  CartAbandonmentMetrics,
} from "@/types/interface";

type Section = "merchants" | "sales" | "retention" | "operations" | "cart";

const SECTIONS: { key: Section; label: string }[] = [
  { key: "merchants", label: "Merchant Activity" },
  { key: "sales", label: "Sales & Demand" },
  { key: "retention", label: "Customer Retention" },
  { key: "operations", label: "Operations & Delivery" },
  { key: "cart", label: "Cart & Products" },
];

function Skeleton() {
  return (
    <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
      {[0, 1, 2, 3, 4, 5, 6, 7].map((i) => (
        <div key={i} className="card p-5 h-[88px] bg-muted/30 animate-pulse" />
      ))}
    </div>
  );
}

export default function AdminAnalyticsClient({
  merchants: initMerchants,
  sales: initSales,
  retention: initRetention,
  operations: initOperations,
  cart: initCart,
}: {
  merchants: MerchantActivityMetrics | null;
  sales: SalesDemandMetrics | null;
  retention: CustomerRetentionMetrics | null;
  operations: OperationsDeliveryMetrics | null;
  cart: CartAbandonmentMetrics | null;
}) {
  const [period, setPeriod] = useState<PeriodKey>("month");
  const [section, setSection] = useState<Section>("merchants");
  const [loading, setLoading] = useState(false);
  const [merchants, setMerchants] = useState(initMerchants);
  const [sales, setSales] = useState(initSales);
  const [retention, setRetention] = useState(initRetention);
  const [operations, setOperations] = useState(initOperations);
  const [cart, setCart] = useState(initCart);

  useEffect(() => {
    setLoading(true);
    Promise.allSettled([
      fetch(`/api/admin/metrics/merchants?period=${period}`).then((r) => r.json()).then(setMerchants),
      fetch(`/api/admin/metrics/sales?period=${period}`).then((r) => r.json()).then(setSales),
      fetch(`/api/admin/metrics/retention?period=${period}`).then((r) => r.json()).then(setRetention),
      fetch(`/api/admin/metrics/operations?period=${period}`).then((r) => r.json()).then(setOperations),
      fetch(`/api/admin/metrics/cart?period=${period}`).then((r) => r.json()).then(setCart),
    ]).finally(() => setLoading(false));
  }, [period]);

  return (
    <div>
      <div className="flex flex-wrap items-center justify-between gap-3 mb-6">
        <div>
          <h1 className="text-2xl font-bold">Analytics</h1>
          <p className="text-sm text-muted">Pick a window — every stat card updates in place.</p>
        </div>
        <PeriodFilter value={period} onChange={setPeriod} />
      </div>

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

      {loading && <Skeleton />}

      {!loading && section === "merchants" && (
        merchants ? (
          <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
            <StatCard label="Active merchants (7d)" value={merchants.active_merchants_7d} />
            <StatCard label="Active merchants (30d)" value={merchants.active_merchants_30d} />
            <StatCard label="Merchants receiving orders" value={merchants.merchants_receiving_orders} />
            <StatCard label="Merchants processing orders" value={merchants.merchants_processing_orders} />
            <StatCard label="Merchants with zero activity" value={merchants.merchants_zero_activity} />
            <StatCard label="Sellers logged in" value={merchants.sellers_logged_in} />
            <StatCard label="Products updated" value={merchants.products_updated} />
            <StatCard label="Avg. transactions / merchant" value={merchants.avg_transactions_per_merchant} />
          </div>
        ) : <p className="text-muted text-sm">Could not load merchant metrics.</p>
      )}

      {!loading && section === "sales" && (
        sales ? (
          <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
            <StatCard label="Total orders" value={sales.total_orders} />
            <StatCard label="GMV" value={formatKES(sales.gmv)} />
            <StatCard label="Average order value" value={formatKES(sales.average_order_value)} />
            <StatCard label="New customers" value={sales.new_customers} />
            <StatCard label="Repeat customers" value={sales.repeat_customers} />
            <StatCard label="Customer acquisition rate" value={`${sales.customer_acquisition_rate}%`} />
            <StatCard label="Cart abandonment rate" value={`${sales.cart_abandonment_rate}%`} />
            <StatCard label="Order cancellation rate" value={`${sales.order_cancellation_rate}%`} />
          </div>
        ) : <p className="text-muted text-sm">Could not load sales metrics.</p>
      )}

      {!loading && section === "retention" && (
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

      {!loading && section === "operations" && (
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

      {!loading && section === "cart" && (
        cart ? (
          <div className="space-y-8">
            <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
              <StatCard label="Carts touched" value={cart.carts_touched} />
              <StatCard label="Converted to order" value={cart.converted_carts} />
              <StatCard label="Abandoned carts" value={cart.abandoned_carts} />
              <StatCard label="Cart abandonment rate" value={`${cart.cart_abandonment_rate}%`} />
              <StatCard label="Abandoned items" value={cart.abandoned_units} />
              <StatCard label="Revenue at risk" value={formatKES(cart.at_risk_revenue)} />
            </div>

            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
              <div className="card p-5">
                <h3 className="font-bold mb-3">Abandoned Products</h3>
                {cart.abandoned_products.length === 0 ? (
                  <p className="text-sm text-muted">No abandoned products in this period.</p>
                ) : (
                  <div className="overflow-x-auto">
                    <table className="w-full text-sm">
                      <thead className="text-xs text-muted border-b">
                        <tr>
                          <th className="text-left py-2">Product</th>
                          <th className="text-right py-2">Units</th>
                          <th className="text-right py-2">At-risk value</th>
                        </tr>
                      </thead>
                      <tbody>
                        {cart.abandoned_products.map((p) => (
                          <tr key={p.product_id ?? p.name} className="border-b last:border-0">
                            <td className="py-2">
                              {p.slug ? (
                                <a href={`/products/${p.slug}`} className="hover:underline">
                                  {p.name}
                                </a>
                              ) : (
                                p.name
                              )}
                            </td>
                            <td className="text-right tabular-nums">{p.units}</td>
                            <td className="text-right tabular-nums">{formatKES(p.at_risk_revenue)}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                )}
              </div>

              <div className="card p-5">
                <h3 className="font-bold mb-3">Top Purchased Products</h3>
                {cart.top_products.length === 0 ? (
                  <p className="text-sm text-muted">No purchases in this period.</p>
                ) : (
                  <div className="overflow-x-auto">
                    <table className="w-full text-sm">
                      <thead className="text-xs text-muted border-b">
                        <tr>
                          <th className="text-left py-2">Product</th>
                          <th className="text-right py-2">Units</th>
                          <th className="text-right py-2">Revenue</th>
                        </tr>
                      </thead>
                      <tbody>
                        {cart.top_products.map((p) => (
                          <tr key={p.product_id ?? p.name} className="border-b last:border-0">
                            <td className="py-2">
                              {p.slug ? (
                                <a href={`/products/${p.slug}`} className="hover:underline">
                                  {p.name}
                                </a>
                              ) : (
                                p.name
                              )}
                            </td>
                            <td className="text-right tabular-nums">{p.units}</td>
                            <td className="text-right tabular-nums">{formatKES(p.revenue)}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                )}
              </div>
            </div>
          </div>
        ) : <p className="text-muted text-sm">Could not load cart metrics.</p>
      )}
    </div>
  );
}