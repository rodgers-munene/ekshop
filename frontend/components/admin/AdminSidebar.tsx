"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { LayoutDashboard, Store, Users, FolderTree, Truck, GalleryHorizontal, Tag, Banknote } from "lucide-react";

const LINKS = [
  { href: "/admin", label: "Overview", icon: LayoutDashboard, exact: true },
  { href: "/admin/sellers", label: "Sellers", icon: Store },
  { href: "/admin/users", label: "Users", icon: Users },
  { href: "/admin/categories", label: "Categories", icon: FolderTree },
  { href: "/admin/deliveries", label: "Deliveries", icon: Truck },
  { href: "/admin/delivery-rates", label: "Delivery Rates", icon: Banknote },
  { href: "/admin/hero-slides", label: "Hero Slides", icon: GalleryHorizontal },
  { href: "/admin/deals", label: "Deals", icon: Tag },
];

export default function AdminSidebar() {
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
