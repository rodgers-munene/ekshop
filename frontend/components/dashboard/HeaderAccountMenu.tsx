"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { ChevronDown, LogOut, Settings, User as UserIcon } from "lucide-react";
import { useAuthStore } from "@/store/authStore";
import { resolveImageUrl } from "@/lib/utils";
import { User } from "@/types/interface";

export default function HeaderAccountMenu({ user }: { user: User }) {
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

  const initials = `${user.first_name?.[0] ?? ""}${user.last_name?.[0] ?? ""}`.toUpperCase();

  return (
    <div className="relative group">
      <button className="flex items-center gap-2 pl-1 pr-2 py-1 rounded-full hover:bg-white/10 transition-colors">
        <span className="w-8 h-8 rounded-full bg-navy-light ring-1 ring-white/10 text-white text-xs font-bold flex items-center justify-center overflow-hidden shrink-0">
          {user.avatar_url ? (
            // eslint-disable-next-line @next/next/no-img-element
            <img src={resolveImageUrl(user.avatar_url)} alt="" className="w-full h-full object-cover" />
          ) : initials ? (
            initials
          ) : (
            <UserIcon size={14} />
          )}
        </span>
        <span className="hidden md:flex flex-col items-start leading-tight text-left">
          <span className="text-sm font-semibold text-white">{user.first_name} {user.last_name}</span>
          <span className="text-[11px] text-white/60">{user.email}</span>
        </span>
        <ChevronDown size={14} className="text-white/60" />
      </button>

      <div className="absolute right-0 top-full mt-1 w-56 bg-white text-ink rounded-md shadow-lg border border-border hidden group-hover:block z-50 overflow-hidden">
        <div className="px-4 py-3 border-b border-border">
          <p className="text-sm font-semibold truncate">{user.first_name} {user.last_name}</p>
          <p className="text-xs text-muted truncate">{user.email}</p>
        </div>
        <Link href="/dashboard/settings" className="flex items-center gap-2 px-4 py-2 text-sm hover:bg-surface">
          <Settings size={14} /> Shop settings
        </Link>
        <button
          onClick={handleLogout}
          className="w-full flex items-center gap-2 text-left px-4 py-2 text-sm hover:bg-surface border-t border-border text-danger"
        >
          <LogOut size={14} /> Logout
        </button>
      </div>
    </div>
  );
}
