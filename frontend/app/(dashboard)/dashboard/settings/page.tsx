import { serverFetch } from "@/lib/server-api";
import { Shop } from "@/types/interface";
import ShopSettingsForm from "@/components/dashboard/ShopSettingsForm";

export default async function DashboardSettingsPage() {
  const shop = await serverFetch<Shop>("/shops/me").catch(() => null);
  if (!shop) return null;

  return (
    <div>
      <h1 className="text-2xl font-bold mb-6">Shop settings</h1>
      <ShopSettingsForm shop={shop} />
    </div>
  );
}
