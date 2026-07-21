"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { LayoutDashboard, Package, ClipboardList, Store } from "lucide-react";

const LINKS = [
  { href: "/dashboard", label: "Overview", icon: LayoutDashboard, exact: true },
  { href: "/dashboard/products", label: "Products", icon: Package },
  { href: "/dashboard/orders", label: "Orders", icon: ClipboardList },
  { href: "/dashboard/settings", label: "Shop Settings", icon: Store },
];

export default function DashboardSidebar() {
  const pathname = usePathname();

  return (
    <aside className="md:w-56 shrink-0 bg-navy text-white">
      <nav className="flex md:flex-col overflow-x-auto md:overflow-visible pt-2">
        {LINKS.map(({ href, label, icon: Icon, exact }) => {
          const active = exact ? pathname === href : pathname.startsWith(href);
          return (
            <Link
              key={href}
              href={href}
              className={`flex items-center gap-2 px-5 py-3 text-sm whitespace-nowrap transition-colors ${
                active ? "bg-navy-light text-white font-medium" : "text-white/70 hover:bg-navy-light/60"
              }`}
            >
              <Icon size={16} />
              {label}
            </Link>
          );
        })}
      </nav>
    </aside>
  );
}
