import { serverFetch } from "@/lib/server-api";
import { AdminOverview } from "@/types/interface";
import AdminOverviewClient from "./AdminOverviewClient";

export default async function AdminOverviewPage() {
  const overview = await serverFetch<AdminOverview>("/admin/stats/overview?period=month&days=14").catch(
    () => null,
  );

  if (!overview) {
    return <p className="text-muted text-sm">Could not load stats.</p>;
  }

  return <AdminOverviewClient initial={overview} />;
}