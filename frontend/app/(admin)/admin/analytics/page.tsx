import { serverFetch } from "@/lib/server-api";
import {
  MerchantActivityMetrics,
  SalesDemandMetrics,
  CustomerRetentionMetrics,
  OperationsDeliveryMetrics,
} from "@/types/interface";
import AdminAnalyticsClient from "./AdminAnalyticsClient";

export default async function AdminAnalyticsPage() {
  const [merchants, sales, retention, operations] = await Promise.all([
    serverFetch<MerchantActivityMetrics>("/admin/metrics/merchants?days=7").catch(() => null),
    serverFetch<SalesDemandMetrics>("/admin/metrics/sales?days=30").catch(() => null),
    serverFetch<CustomerRetentionMetrics>("/admin/metrics/retention?days=30").catch(() => null),
    serverFetch<OperationsDeliveryMetrics>("/admin/metrics/operations?days=30").catch(() => null),
  ]);

  return (
    <AdminAnalyticsClient merchants={merchants} sales={sales} retention={retention} operations={operations} />
  );
}
