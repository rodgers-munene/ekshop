import { serverFetch } from "@/lib/server-api";
import {
  MerchantActivityMetrics,
  SalesDemandMetrics,
  CustomerRetentionMetrics,
  OperationsDeliveryMetrics,
  CartAbandonmentMetrics,
} from "@/types/interface";
import AdminAnalyticsClient from "./AdminAnalyticsClient";

export default async function AdminAnalyticsPage() {
  const [merchants, sales, retention, operations, cart] = await Promise.all([
    serverFetch<MerchantActivityMetrics>("/admin/metrics/merchants?period=month").catch(() => null),
    serverFetch<SalesDemandMetrics>("/admin/metrics/sales?period=month").catch(() => null),
    serverFetch<CustomerRetentionMetrics>("/admin/metrics/retention?period=month").catch(() => null),
    serverFetch<OperationsDeliveryMetrics>("/admin/metrics/operations?period=month").catch(() => null),
    serverFetch<CartAbandonmentMetrics>("/admin/metrics/cart?period=month").catch(() => null),
  ]);

  return (
    <AdminAnalyticsClient
      merchants={merchants}
      sales={sales}
      retention={retention}
      operations={operations}
      cart={cart}
    />
  );
}