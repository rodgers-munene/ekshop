import { redirect } from "next/navigation";
import { serverFetch } from "@/lib/server-api";
import { User, Shop, Subscription } from "@/types/interface";
import DashboardSidebar from "@/components/dashboard/DashboardSidebar";
import DashboardHeader from "@/components/dashboard/DashboardHeader";
import ShopOnboardingForm from "@/components/dashboard/ShopOnboardingForm";
import SubscriptionBanner from "@/components/dashboard/SubscriptionBanner";

export default async function DashboardLayout({ children }: { children: React.ReactNode }) {
  const user = await serverFetch<User>("/users/me").catch(() => null);
  if (!user) redirect("/login");
  if (user.role !== "seller") redirect("/");

  const shop = await serverFetch<Shop>("/shops/me").catch(() => null);

  if (!shop) {
    return (
      <div className="min-h-screen bg-surface flex items-center justify-center px-4 py-12">
        <ShopOnboardingForm />
      </div>
    );
  }

  const subscription = await serverFetch<Subscription>("/subscriptions/me").catch(() => null);

  return (
    <div className="min-h-screen bg-surface flex flex-col">
      <DashboardHeader user={user} shop={shop} />
      {subscription && <SubscriptionBanner subscription={subscription} />}
      <div className="flex flex-1 flex-col md:flex-row">
        <DashboardSidebar />
        <main className="flex-1 px-4 md:px-8 py-6 max-w-6xl mx-auto w-full">{children}</main>
      </div>
    </div>
  );
}
