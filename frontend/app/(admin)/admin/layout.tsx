import { redirect } from "next/navigation";
import { Metadata } from "next";
import { serverFetch, ServerFetchError } from "@/lib/server-api";
import { User } from "@/types/interface";
import AdminSidebar from "@/components/admin/AdminSidebar";
import AdminHeader from "@/components/admin/AdminHeader";
import AdminSessionGuard from "@/components/admin/AdminSessionGuard";
import PresenceHeartbeat from "@/components/PresenceHeartbeat";

export const metadata: Metadata = {
  robots: { index: false, follow: false },
};

export default async function AdminLayout({ children }: { children: React.ReactNode }) {
  let user: User | null = null;
  let status = 0;
  try {
    user = await serverFetch<User>("/users/me");
  } catch (error) {
    status = error instanceof ServerFetchError ? error.status : 0;
  }

  // 401 means the session itself is gone, so say so on the sign-in screen. Any
  // other failure is reported as an ordinary sign-in request rather than a lie
  // about an expired session.
  if (!user) redirect(status === 401 ? "/login?reason=expired&next=/admin" : "/login");
  if (user.role !== "admin") redirect("/");

  return (
    <div className="min-h-screen bg-surface flex flex-col">
      {/* Reports this tab as in-use. Presence is what makes the "active now"
          figure on the analytics page mean anything. */}
      <PresenceHeartbeat />
      {/* Admin sessions end after an hour, and sooner if the admin walks away.
          The guard is what turns that into a sign-in prompt. */}
      <AdminSessionGuard />
      <AdminHeader user={user} />
      <div className="flex flex-1 flex-col md:flex-row">
        <AdminSidebar />
        <main className="flex-1 px-4 md:px-8 py-6 max-w-6xl mx-auto w-full">{children}</main>
      </div>
    </div>
  );
}
