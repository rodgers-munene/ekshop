import { serverFetch } from "@/lib/server-api";
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
import AdminAnalyticsClient from "./AdminAnalyticsClient";

export default async function AdminAnalyticsPage() {
  const [overview, merchants, sales, retention, operations, cart, merchantMaster, orderControl, customerRecovery, supplyDemand, marginLeakage] = await Promise.all([
    serverFetch<AdminOverview>("/admin/stats/overview?period=month").catch(() => null),
    serverFetch<MerchantActivityMetrics>("/admin/metrics/merchants?period=month").catch(() => null),
    serverFetch<SalesDemandMetrics>("/admin/metrics/sales?period=month").catch(() => null),
    serverFetch<CustomerRetentionMetrics>("/admin/metrics/retention?period=month").catch(() => null),
    serverFetch<OperationsDeliveryMetrics>("/admin/metrics/operations?period=month").catch(() => null),
    serverFetch<CartAbandonmentMetrics>("/admin/metrics/cart?period=month").catch(() => null),
    serverFetch<MerchantMasterHealth[]>("/admin/metrics/merchant-master-health?period=month").catch(() => null),
    serverFetch<OrderControlTowerRow[]>("/admin/metrics/order-control-tower?period=month").catch(() => null),
    serverFetch<CustomerRecoveryRow[]>("/admin/metrics/customer-recovery?period=month").catch(() => null),
    serverFetch<SupplyDemandRow[]>("/admin/metrics/supply-demand?period=month").catch(() => null),
    serverFetch<MarginLeakageMetrics>("/admin/metrics/margin-leakage?period=month").catch(() => null),
  ]);

  return (
    <AdminAnalyticsClient
      overview={overview}
      merchants={merchants}
      sales={sales}
      retention={retention}
      operations={operations}
      cart={cart}
      merchantMaster={merchantMaster}
      orderControl={orderControl}
      customerRecovery={customerRecovery}
      supplyDemand={supplyDemand}
      marginLeakage={marginLeakage}
    />
  );
}