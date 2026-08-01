import Link from "next/link";
import { ArrowLeft, BadgeCheck, MapPin, Star, Store } from "lucide-react";
import { resolveImageUrl } from "@/lib/utils";
import { Shop, User } from "@/types/interface";
import HeaderAccountMenu from "./HeaderAccountMenu";
import NotificationBell from "@/components/layout/NotificationBell";

export default function DashboardHeader({ user, shop }: { user: User; shop: Shop }) {
  return (
    <header className="bg-navy border-b border-white/10">
      <div className="px-4 md:px-8 py-2 flex flex-wrap items-center justify-between gap-4">
        <div className="flex items-center gap-2.5 min-w-0">
          <div className="w-8 h-8 rounded-lg overflow-hidden bg-navy-light ring-1 ring-white/10 shrink-0 flex items-center justify-center">
            {shop.logo_url ? (
              // eslint-disable-next-line @next/next/no-img-element
              <img src={resolveImageUrl(shop.logo_url)} alt={shop.name} className="w-full h-full object-cover" />
            ) : (
              <Store size={15} className="text-white" />
            )}
          </div>
          <div className="min-w-0">
            <div className="flex items-center gap-1.5">
              <p className="font-bold text-white text-sm truncate">{shop.name}</p>
              {shop.is_verified && <BadgeCheck size={13} className="text-info shrink-0" />}
            </div>
            <div className="flex items-center gap-3 text-xs text-white/60">
              {shop.county && (
                <span className="flex items-center gap-1">
                  <MapPin size={11} /> {shop.county}
                </span>
              )}
              <span className="flex items-center gap-1">
                <Star size={11} className="text-amber" fill="currentColor" />
                {parseFloat(shop.rating_avg || "0").toFixed(1)} ({shop.rating_count})
              </span>
            </div>
          </div>
        </div>

        <div className="flex items-center gap-4 shrink-0">
          <Link
            href={`/shops/${shop.slug}`}
            className="hidden sm:flex items-center gap-1.5 text-sm font-medium text-white/80 hover:text-amber transition-colors"
          >
            <ArrowLeft size={15} />
            Back to shop
          </Link>
          <NotificationBell iconClassName="text-white" />
          <HeaderAccountMenu user={user} />
        </div>
      </div>
    </header>
  );
}
