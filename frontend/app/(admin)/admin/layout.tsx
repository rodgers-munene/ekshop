import { redirect } from "next/navigation";
import { serverFetch } from "@/lib/server-api";
import { User } from "@/types/interface";
import AdminSidebar from "@/components/admin/AdminSidebar";
import AdminHeader from "@/components/admin/AdminHeader";

export default async function AdminLayout({ children }: { children: React.ReactNode }) {
  const user = await serverFetch<User>("/users/me").catch(() => null);
  if (!user) redirect("/login");
  if (user.role !== "admin") redirect("/");

  return (
    <div className="min-h-screen bg-surface flex flex-col">
      <AdminHeader user={user} />
      <div className="flex flex-1 flex-col md:flex-row">
        <AdminSidebar />
        <main className="flex-1 px-4 md:px-8 py-6 max-w-6xl mx-auto w-full">{children}</main>
      </div>
    </div>
  );
}
