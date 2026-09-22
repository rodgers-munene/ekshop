"use client";

import { useEffect, useState } from "react";
import { formatKES } from "@/lib/utils";
import StatCard from "@/components/dashboard/StatCard";
import PeriodFilter, { PeriodKey } from "@/components/dashboard/PeriodFilter";
import StatDrillDown from "@/components/admin/StatDrillDown";
import RevenueLeakageMonitor from "@/components/admin/RevenueLeakageMonitor";
import {
  DrillSpec,
  ordersSpec,
  merchantMasterSpec,
  orderTowerSpec,
  customerRecoverySpec,
  abandonedSpec,
} from "@/components/admin/drillColumns";
import {
  MarginLeakageMetrics,
  MerchantActivityMetrics,
  SalesDemandMetrics,
  CustomerRetentionMetrics,
  OperationsDeliveryMetrics,
  CartAbandonmentMetrics,
  MerchantMasterHealth,
  OrderControlTowerRow,
  CustomerRecoveryRow,
  SupplyDemandRow,
  AdminOverview,
} from "@/types/interface";

type Section = "overview" | "merchants" | "sales" | "retention" | "operations" | "cart" | "merchant-master" | "order-control" | "customer-recovery" | "supply-demand" | "margin";

const SECTIONS: { key: Section; label: string }[] = [
  { key: "overview", label: "Overview" },
  { key: "margin", label: "Revenue Leakage & Margin" },
  { key: "merchants", label: "Merchant Activity" },
  { key: "merchant-master", label: "Merchant Master Health" },
  { key: "order-control", label: "Order Control Tower" },
  { key: "customer-recovery", label: "Customer Recovery" },
  { key: "supply-demand", label: "Supply Demand Matrix" },
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
  merchantMaster: initMerchantMaster,
  orderControl: initOrderControl,
  customerRecovery: initCustomerRecovery,
  supplyDemand: initSupplyDemand,
  marginLeakage: initMarginLeakage,
  overview: initOverview,
}: {
  merchants: MerchantActivityMetrics | null;
  sales: SalesDemandMetrics | null;
  retention: CustomerRetentionMetrics | null;
  operations: OperationsDeliveryMetrics | null;
  cart: CartAbandonmentMetrics | null;
  merchantMaster: MerchantMasterHealth[] | null;
  orderControl: OrderControlTowerRow[] | null;
  customerRecovery: CustomerRecoveryRow[] | null;
  supplyDemand: SupplyDemandRow[] | null;
  marginLeakage: MarginLeakageMetrics | null;
  overview: AdminOverview | null;
}) {
  const [period, setPeriod] = useState<PeriodKey>("month");
  const [section, setSection] = useState<Section>("overview");
  const [refreshing, setRefreshing] = useState(false);
  const [drill, setDrill] = useState<DrillSpec | null>(null);
  const [merchants, setMerchants] = useState(initMerchants);
  const [sales, setSales] = useState(initSales);
  const [retention, setRetention] = useState(initRetention);
  const [operations, setOperations] = useState(initOperations);
  const [cart, setCart] = useState(initCart);
  const [merchantMaster, setMerchantMaster] = useState<MerchantMasterHealth[] | null>(initMerchantMaster);
  const [orderControl, setOrderControl] = useState<OrderControlTowerRow[] | null>(initOrderControl);
  const [customerRecovery, setCustomerRecovery] = useState<CustomerRecoveryRow[] | null>(initCustomerRecovery);
  const [supplyDemand, setSupplyDemand] = useState<SupplyDemandRow[] | null>(initSupplyDemand);
  const [marginLeakage, setMarginLeakage] = useState<MarginLeakageMetrics | null>(initMarginLeakage);
  const [overview, setOverview] = useState<AdminOverview | null>(initOverview);

  useEffect(() => {
    let cancelled = false;
    const asObj = (v: unknown) =>
      v && typeof v === "object" && !Array.isArray(v) ? (v as object) : null;
    const asArr = (v: unknown) => (Array.isArray(v) ? v : null);

    async function load() {
      setRefreshing(true);
      try {
        const [m, s, r, o, c, mm, oc, cr, sd, ov, ml] = await Promise.all([
          fetch(`/api/admin/metrics/merchants?period=${period}`).then((r) => r.ok ? r.json() : Promise.resolve(null)).then((d) => (d && typeof d === "object" ? d : null)),
          fetch(`/api/admin/metrics/sales?period=${period}`).then((r) => r.ok ? r.json() : Promise.resolve(null)).then((d) => (d && typeof d === "object" ? d : null)),
          fetch(`/api/admin/metrics/retention?period=${period}`).then((r) => r.ok ? r.json() : Promise.resolve(null)).then((d) => (d && typeof d === "object" ? d : null)),
          fetch(`/api/admin/metrics/operations?period=${period}`).then((r) => r.ok ? r.json() : Promise.resolve(null)).then((d) => (d && typeof d === "object" ? d : null)),
          fetch(`/api/admin/metrics/cart?period=${period}`).then((r) => r.ok ? r.json() : Promise.resolve(null)).then((d) => (d && typeof d === "object" ? d : null)),
          fetch(`/api/admin/metrics/merchant-master-health?period=${period}`).then((r) => r.ok ? r.json() : Promise.resolve(null)).then((d) => Array.isArray(d) ? d : null),
          fetch(`/api/admin/metrics/order-control-tower?period=${period}`).then((r) => r.ok ? r.json() : Promise.resolve(null)).then((d) => Array.isArray(d) ? d : null),
          fetch(`/api/admin/metrics/customer-recovery?period=${period}`).then((r) => r.ok ? r.json() : Promise.resolve(null)).then((d) => Array.isArray(d) ? d : null),
          fetch(`/api/admin/metrics/supply-demand?period=${period}`).then((r) => r.ok ? r.json() : Promise.resolve(null)).then((d) => Array.isArray(d) ? d : null),
          fetch(`/api/admin/stats/overview?period=${period}`).then((r) => r.ok ? r.json() : Promise.resolve(null)).then((d) => (d && typeof d === "object" && d.metrics ? d : null)),
          fetch(`/api/admin/metrics/margin-leakage?period=${period}`).then((r) => r.ok ? r.json() : Promise.resolve(null)).then((d) => (d && typeof d === "object" ? d : null)),
        ]);
        if (!cancelled) {
          setMerchants(m);
          setSales(s);
          setRetention(r);
          setOperations(o);
          setCart(c);
          setMerchantMaster(mm);
          setOrderControl(oc);
          setCustomerRecovery(cr);
          setSupplyDemand(sd);
          setMarginLeakage(ml);
          setOverview(ov);
        }
      } finally {
        if (!cancelled) setRefreshing(false);
      }
    }

    load();
    return () => {
      cancelled = true;
    };
  }, [period, setRefreshing]);

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

      {refreshing && <Skeleton />}

      {!refreshing && section === "overview" && overview && (
        <div className="space-y-6">
          <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
            <StatCard label="Total users" value={overview.totals.total_users} />
            <StatCard label="Total buyers" value={overview.totals.total_buyers} />
            <StatCard label="Total sellers" value={overview.totals.total_sellers} />
            <StatCard label="Total shops" value={overview.totals.total_shops} />
            <StatCard label="Pending verification" value={overview.totals.shops_pending_verification} />
            <StatCard label="Total products" value={overview.totals.total_products} />
            <StatCard label="Total orders" value={overview.totals.total_orders} />
            <StatCard label="GMV" value={formatKES(overview.totals.revenue_total)} />
          </div>

          <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
            <StatCard label="Period revenue" value={formatKES(overview.metrics.revenue)} />
            <StatCard label="Period orders" value={overview.metrics.orders} />
            <StatCard label="Avg. order value" value={formatKES(overview.metrics.average_order_value)} />
            <StatCard label="New users" value={overview.metrics.new_users} />
            <StatCard label="New buyers" value={overview.metrics.new_buyers} />
            <StatCard label="New sellers" value={overview.metrics.new_sellers} />
            <StatCard label="New shops" value={overview.metrics.new_shops} />
            <StatCard label="New products" value={overview.metrics.new_products} />
            <StatCard label="Cart abandonment rate" value={`${overview.metrics.cart_abandonment_rate}%`} />
          </div>

          {marginLeakage && <RevenueLeakageMonitor data={marginLeakage} />}
        </div>
      )}

      {!refreshing && section === "merchants" && (
        merchants ? (
          <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
            <StatCard label="Active merchants (7d)" value={merchants.active_merchants_7d} onClick={() => setDrill(merchantMasterSpec(merchantMaster ?? []))} hint="Open Merchant Master" />
            <StatCard label="Active merchants (30d)" value={merchants.active_merchants_30d} onClick={() => setDrill(merchantMasterSpec(merchantMaster ?? []))} hint="Open Merchant Master" />
            <StatCard label="Merchants receiving orders" value={merchants.merchants_receiving_orders} onClick={() => setDrill(merchantMasterSpec(merchantMaster ?? []))} hint="Open Merchant Master" />
            <StatCard label="Merchants processing orders" value={merchants.merchants_processing_orders} onClick={() => setDrill(merchantMasterSpec(merchantMaster ?? []))} hint="Open Merchant Master" />
            <StatCard label="Merchants with zero activity" value={merchants.merchants_zero_activity} onClick={() => setDrill(merchantMasterSpec(merchantMaster ?? []))} hint="Open Merchant Master" />
            <StatCard label="Sellers logged in" value={merchants.sellers_logged_in} onClick={() => setDrill(merchantMasterSpec(merchantMaster ?? []))} hint="Open Merchant Master" />
            <StatCard label="Products updated" value={merchants.products_updated} onClick={() => setDrill(merchantMasterSpec(merchantMaster ?? []))} hint="Open Merchant Master" />
            <StatCard label="Avg. transactions / merchant" value={merchants.avg_transactions_per_merchant} onClick={() => setDrill(merchantMasterSpec(merchantMaster ?? []))} hint="Open Merchant Master" />
          </div>
        ) : <p className="text-muted text-sm">Could not load merchant metrics.</p>
      )}

      {!refreshing && section === "merchant-master" && (
        merchantMaster ? (
          <div className="card overflow-hidden">
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead className="text-xs text-muted border-b bg-surface">
                  <tr>
                    <th className="text-left py-2 px-3">Merchant</th>
                    <th className="text-left py-2 px-3">Location</th>
                    <th className="text-left py-2 px-3">Stage</th>
                    <th className="text-right py-2 px-3">Activity</th>
                    <th className="text-right py-2 px-3">Catalogue</th>
                    <th className="text-right py-2 px-3">Demand</th>
                    <th className="text-right py-2 px-3">Reliability</th>
                    <th className="text-right py-2 px-3">Growth</th>
                    <th className="text-right py-2 px-3">Health</th>
                    <th className="text-left py-2 px-3">Tier</th>
                    <th className="text-left py-2 px-3">Last Login</th>
                    <th className="text-right py-2 px-3">Orders 30d</th>
                    <th className="text-right py-2 px-3">Dispatch Hrs</th>
                    <th className="text-right py-2 px-3">Cancel %</th>
                    <th className="text-right py-2 px-3">Response Min</th>
                    <th className="text-left py-2 px-3">Next Action</th>
                    <th className="text-left py-2 px-3">Owner</th>
                  </tr>
                </thead>
                <tbody>
                  {merchantMaster.map((row, idx) => (
                    <tr key={idx} className="border-b last:border-0">
                      <td className="py-2 px-3 font-medium">{row.merchant}</td>
                      <td className="py-2 px-3">{row.location}</td>
                      <td className="py-2 px-3">{row.stage}</td>
                      <td className="py-2 px-3 text-right tabular-nums">{row.activity}</td>
                      <td className="py-2 px-3 text-right tabular-nums">{row.catalogue}</td>
                      <td className="py-2 px-3 text-right tabular-nums">{row.demand}</td>
                      <td className="py-2 px-3 text-right tabular-nums">{row.reliability}</td>
                      <td className="py-2 px-3 text-right tabular-nums">{row.growth}</td>
                      <td className="py-2 px-3 text-right tabular-nums font-bold">{row.health}</td>
                      <td className="py-2 px-3">{row.health_tier}</td>
                      <td className="py-2 px-3">{row.last_login ? new Date(row.last_login).toLocaleDateString() : "—"}</td>
                      <td className="py-2 px-3 text-right tabular-nums">{row.orders_30d}</td>
                      <td className="py-2 px-3 text-right tabular-nums">{row.dispatch_hrs}</td>
                      <td className="py-2 px-3 text-right tabular-nums">{row.cancel_pct}</td>
                      <td className="py-2 px-3 text-right tabular-nums">{row.response_min}</td>
                      <td className="py-2 px-3">{row.next_action}</td>
                      <td className="py-2 px-3">{row.owner}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        ) : <p className="text-muted text-sm">Could not load merchant master health.</p>
      )}

      {!refreshing && section === "order-control" && (
        orderControl ? (
          <div className="card overflow-hidden">
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead className="text-xs text-muted border-b bg-surface">
                  <tr>
                    <th className="text-left py-2 px-3">Order ID</th>
                    <th className="text-left py-2 px-3">Received</th>
                    <th className="text-left py-2 px-3">Merchant</th>
                    <th className="text-left py-2 px-3">Customer</th>
                    <th className="text-left py-2 px-3">Ack Time</th>
                    <th className="text-left py-2 px-3">Accepted</th>
                    <th className="text-left py-2 px-3">Ready Time</th>
                    <th className="text-left py-2 px-3">Rider Assigned</th>
                    <th className="text-left py-2 px-3">Pickup Time</th>
                    <th className="text-left py-2 px-3">Delivered Time</th>
                    <th className="text-right py-2 px-3">Dispatch Hrs</th>
                    <th className="text-right py-2 px-3">Delivery Hrs</th>
                    <th className="text-left py-2 px-3">Status</th>
                    <th className="text-left py-2 px-3">Exception / Owner</th>
                  </tr>
                </thead>
                <tbody>
                  {orderControl.map((row) => (
                    <tr key={row.order_id} className="border-b last:border-0">
                      <td className="py-2 px-3 font-mono text-xs">{row.order_id.slice(0, 8)}...</td>
                      <td className="py-2 px-3">{new Date(row.received).toLocaleString()}</td>
                      <td className="py-2 px-3">{row.merchant}</td>
                      <td className="py-2 px-3">{row.customer}</td>
                      <td className="py-2 px-3">{row.ack_time ? new Date(row.ack_time).toLocaleString() : "—"}</td>
                      <td className="py-2 px-3">{row.accepted ? "Yes" : "No"}</td>
                      <td className="py-2 px-3">{row.ready_time ? new Date(row.ready_time).toLocaleString() : "—"}</td>
                      <td className="py-2 px-3">{row.rider_assigned ? row.rider_assigned.slice(0, 8) : "—"}</td>
                      <td className="py-2 px-3">{row.pickup_time ? new Date(row.pickup_time).toLocaleString() : "—"}</td>
                      <td className="py-2 px-3">{row.delivered_time ? new Date(row.delivered_time).toLocaleString() : "—"}</td>
                      <td className="py-2 px-3 text-right tabular-nums">{row.dispatch_hrs}</td>
                      <td className="py-2 px-3 text-right tabular-nums">{row.delivery_hrs}</td>
                      <td className="py-2 px-3">{row.status}</td>
                      <td className="py-2 px-3">{row.exception_owner}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        ) : <p className="text-muted text-sm">Could not load order control tower.</p>
      )}

      {!refreshing && section === "customer-recovery" && (
        customerRecovery ? (
          <div className="card overflow-hidden">
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead className="text-xs text-muted border-b bg-surface">
                  <tr>
                    <th className="text-left py-2 px-3">Customer</th>
                    <th className="text-left py-2 px-3">Segment</th>
                    <th className="text-left py-2 px-3">Last Activity</th>
                    <th className="text-right py-2 px-3">Cart Value</th>
                    <th className="text-left py-2 px-3">Issue / Trigger</th>
                    <th className="text-left py-2 px-3">Contact Date</th>
                    <th className="text-left py-2 px-3">Channel</th>
                    <th className="text-left py-2 px-3">Response</th>
                    <th className="text-left py-2 px-3">Recovered Order?</th>
                    <th className="text-left py-2 px-3">Next Action</th>
                  </tr>
                </thead>
                <tbody>
                  {customerRecovery.map((row, idx) => (
                    <tr key={idx} className="border-b last:border-0">
                      <td className="py-2 px-3 font-medium">{row.customer}</td>
                      <td className="py-2 px-3">{row.segment}</td>
                      <td className="py-2 px-3">{row.last_activity ? new Date(row.last_activity).toLocaleString() : "—"}</td>
                      <td className="py-2 px-3 text-right tabular-nums">{formatKES(row.cart_value)}</td>
                      <td className="py-2 px-3">{row.issue_trigger}</td>
                      <td className="py-2 px-3">{row.contact_date ? new Date(row.contact_date).toLocaleDateString() : "—"}</td>
                      <td className="py-2 px-3">{row.channel}</td>
                      <td className="py-2 px-3">{row.response}</td>
                      <td className="py-2 px-3">{row.recovered_order ? "Yes" : "No"}</td>
                      <td className="py-2 px-3">{row.next_action}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        ) : <p className="text-muted text-sm">Could not load customer recovery data.</p>
      )}

      {!refreshing && section === "supply-demand" && (
        supplyDemand ? (
          <div className="card overflow-hidden">
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead className="text-xs text-muted border-b bg-surface">
                  <tr>
                    <th className="text-left py-2 px-3">Category / Area</th>
                    <th className="text-right py-2 px-3">Searches / Views</th>
                    <th className="text-right py-2 px-3">Cart Adds</th>
                    <th className="text-right py-2 px-3">Orders</th>
                    <th className="text-right py-2 px-3">Active Shops</th>
                    <th className="text-right py-2 px-3">Products Live</th>
                    <th className="text-right py-2 px-3">Demand Score</th>
                    <th className="text-right py-2 px-3">Supply Score</th>
                    <th className="text-right py-2 px-3">Gap</th>
                    <th className="text-left py-2 px-3">Action</th>
                  </tr>
                </thead>
                <tbody>
                  {supplyDemand.map((row, idx) => (
                    <tr key={idx} className="border-b last:border-0">
                      <td className="py-2 px-3 font-medium">{row.category_area}</td>
                      <td className="py-2 px-3 text-right tabular-nums">{row.searches_views}</td>
                      <td className="py-2 px-3 text-right tabular-nums">{row.cart_adds}</td>
                      <td className="py-2 px-3 text-right tabular-nums">{row.orders}</td>
                      <td className="py-2 px-3 text-right tabular-nums">{row.active_shops}</td>
                      <td className="py-2 px-3 text-right tabular-nums">{row.products_live}</td>
                      <td className="py-2 px-3 text-right tabular-nums">{row.demand_score}</td>
                      <td className="py-2 px-3 text-right tabular-nums">{row.supply_score}</td>
                      <td className={`py-2 px-3 text-right tabular-nums font-bold ${row.gap > 0 ? "text-success" : row.gap < 0 ? "text-danger" : ""}`}>{row.gap}</td>
                      <td className="py-2 px-3">{row.action}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        ) : <p className="text-muted text-sm">Could not load supply demand matrix.</p>
      )}

      {!refreshing && section === "sales" && (
        sales ? (
          <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
            <StatCard label="Total orders" value={sales.total_orders} onClick={() => setDrill(ordersSpec(period))} hint="Paid order groups" />
            <StatCard label="GMV" value={formatKES(sales.gmv)} onClick={() => setDrill(ordersSpec(period))} hint="Paid order groups" />
            <StatCard label="Average order value" value={formatKES(sales.average_order_value)} onClick={() => setDrill(ordersSpec(period))} hint="Paid order groups" />
            <StatCard label="New customers" value={sales.new_customers} onClick={() => setDrill(customerRecoverySpec(customerRecovery ?? []))} hint="Customers to follow up" />
            <StatCard label="Repeat customers" value={sales.repeat_customers} onClick={() => setDrill(customerRecoverySpec(customerRecovery ?? []))} hint="Customers to follow up" />
            <StatCard label="Customer acquisition rate" value={`${sales.customer_acquisition_rate}%`} onClick={() => setDrill(customerRecoverySpec(customerRecovery ?? []))} hint="Customers to follow up" />
            <StatCard label="Cart abandonment rate" value={`${sales.cart_abandonment_rate}%`} onClick={() => setDrill(orderTowerSpec(orderControl ?? []))} hint="Order control tower" />
            <StatCard label="Order cancellation rate" value={`${sales.order_cancellation_rate}%`} onClick={() => setDrill(orderTowerSpec(orderControl ?? []))} hint="Order control tower" />
          </div>
        ) : <p className="text-muted text-sm">Could not load sales metrics.</p>
      )}

      {!refreshing && section === "retention" && (
        retention ? (
          <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
            <StatCard label="New customers" value={retention.new_customers} onClick={() => setDrill(customerRecoverySpec(customerRecovery ?? []))} hint="Customer recovery rows" />
            <StatCard label="Returning customers" value={retention.returning_customers} onClick={() => setDrill(customerRecoverySpec(customerRecovery ?? []))} hint="Customer recovery rows" />
            <StatCard label="Repeat purchase rate" value={`${retention.repeat_purchase_rate}%`} onClick={() => setDrill(customerRecoverySpec(customerRecovery ?? []))} hint="Customer recovery rows" />
            <StatCard label="Churn rate" value={`${retention.churn_rate}%`} onClick={() => setDrill(customerRecoverySpec(customerRecovery ?? []))} hint="Customer recovery rows" />
            <StatCard label="30-day retention" value={`${retention.retention_30d}%`} onClick={() => setDrill(customerRecoverySpec(customerRecovery ?? []))} hint="Customer recovery rows" />
            <StatCard label="Orders per customer" value={retention.orders_per_customer} onClick={() => setDrill(customerRecoverySpec(customerRecovery ?? []))} hint="Customer recovery rows" />
            <StatCard label="Avg. days between purchases" value={retention.avg_days_between_purchases} onClick={() => setDrill(customerRecoverySpec(customerRecovery ?? []))} hint="Customer recovery rows" />
            <StatCard label="Customer complaints" value={retention.customer_complaints} onClick={() => setDrill(customerRecoverySpec(customerRecovery ?? []))} hint="Customer recovery rows" />
          </div>
        ) : <p className="text-muted text-sm">Could not load retention metrics.</p>
      )}

      {!refreshing && section === "operations" && (
        operations ? (
          <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
            <StatCard label="Orders received" value={operations.orders_received} onClick={() => setDrill(orderTowerSpec(orderControl ?? []))} hint="Order control tower" />
            <StatCard label="Orders accepted" value={operations.orders_accepted} onClick={() => setDrill(orderTowerSpec(orderControl ?? []))} hint="Order control tower" />
            <StatCard label="Orders fulfilled" value={operations.orders_fulfilled} onClick={() => setDrill(orderTowerSpec(orderControl ?? []))} hint="Order control tower" />
            <StatCard label="Orders cancelled" value={operations.orders_cancelled} onClick={() => setDrill(orderTowerSpec(orderControl ?? []))} hint="Order control tower" />
            <StatCard label="Avg. dispatch time" value={`${operations.avg_dispatch_time_hours}h`} onClick={() => setDrill(orderTowerSpec(orderControl ?? []))} hint="Order control tower" />
            <StatCard label="Avg. delivery time" value={`${operations.avg_delivery_time_hours}h`} onClick={() => setDrill(orderTowerSpec(orderControl ?? []))} hint="Order control tower" />
            <StatCard
              label="On-time delivery %"
              value={operations.on_time_delivery_rate === null ? "—" : `${operations.on_time_delivery_rate}%`}
              onClick={() => setDrill(orderTowerSpec(orderControl ?? []))}
              hint="Order control tower"
            />
            <StatCard label="Failed deliveries" value={operations.failed_deliveries} onClick={() => setDrill(orderTowerSpec(orderControl ?? []))} hint="Order control tower" />
            <StatCard label="Rider utilization" value={operations.rider_utilization} onClick={() => setDrill(orderTowerSpec(orderControl ?? []))} hint="Order control tower" />
            <StatCard label="Delivery revenue" value={formatKES(operations.delivery_revenue)} onClick={() => setDrill(orderTowerSpec(orderControl ?? []))} hint="Order control tower" />
          </div>
        ) : <p className="text-muted text-sm">Could not load operations metrics.</p>
      )}

      {!refreshing && section === "cart" && (
        cart ? (
          <div className="space-y-8">
            <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
              <StatCard label="Carts touched" value={cart.carts_touched} onClick={() => setDrill(orderTowerSpec(orderControl ?? []))} hint="Order control tower" />
              <StatCard label="Converted to order" value={cart.converted_carts} onClick={() => setDrill(ordersSpec(period))} hint="Paid order groups" />
              <StatCard label="Abandoned carts" value={cart.abandoned_carts} onClick={() => setDrill(abandonedSpec(cart.abandoned_products))} hint="Abandoned products" />
              <StatCard label="Cart abandonment rate" value={`${cart.cart_abandonment_rate}%`} onClick={() => setDrill(abandonedSpec(cart.abandoned_products))} hint="Abandoned products" />
              <StatCard label="Abandoned items" value={cart.abandoned_units} onClick={() => setDrill(abandonedSpec(cart.abandoned_products))} hint="Abandoned products" />
              <StatCard label="Revenue at risk" value={formatKES(cart.at_risk_revenue)} onClick={() => setDrill(abandonedSpec(cart.abandoned_products))} hint="Abandoned products" />
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

      <StatDrillDown
        open={!!drill}
        onClose={() => setDrill(null)}
        title={drill?.title}
        subtitle={drill?.subtitle}
        queryUrl={drill?.queryUrl}
        rows={drill?.rows}
        columns={drill?.columns ?? []}
        rowKey={drill?.rowKey ?? ((_r, i) => i)}
        emptyText={drill?.emptyText}
        href={drill?.href}
        hrefLabel={drill?.hrefLabel}
      />
    </div>
  );
}