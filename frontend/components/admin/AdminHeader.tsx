"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { ArrowLeft, LogOut, ShieldCheck } from "lucide-react";
import { useAuthStore } from "@/store/authStore";
import { User } from "@/types/interface";

export default function AdminHeader({ user }: { user: User }) {
  const router = useRouter();
  const clearUser = useAuthStore((s) => s.clearUser);

  async function handleLogout() {
    await fetch("/api/auth", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ action: "logout" }),
    });
    clearUser();
    router.push("/");
  }

  return (
    <header className="bg-navy border-b border-white/10">
      <div className="px-4 md:px-8 py-3.5 flex flex-wrap items-center justify-between gap-4">
        <div className="flex items-center gap-2 text-white">
          <ShieldCheck size={20} className="text-amber" />
          <p className="font-bold">Ekshop Admin</p>
        </div>

        <div className="flex items-center gap-4 shrink-0">
          <Link href="/" className="hidden sm:flex items-center gap-1.5 text-sm font-medium text-white/80 hover:text-amber transition-colors">
            <ArrowLeft size={15} />
            Back to site
          </Link>
          <span className="text-sm text-white/80">{user.first_name} {user.last_name}</span>
          <button onClick={handleLogout} className="flex items-center gap-1.5 text-sm text-white/80 hover:text-danger transition-colors">
            <LogOut size={14} /> Logout
          </button>
        </div>
      </div>
    </header>
  );
}
