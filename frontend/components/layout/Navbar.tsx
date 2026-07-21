"use client";

import Link from "next/link";
import Image from "next/image";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { ShoppingCart, User, Search } from "lucide-react";
import { useAuthStore } from "@/store/authStore";
import { useCartStore } from "@/store/cartStore";
import { AnimatePresence, motion } from "motion/react"

export default function Navbar() {
  const router = useRouter();
  const { user, isAuthenticated, clearUser } = useAuthStore();
  const totalItems = useCartStore((state) => state.totalItems);
  const [searchPlaceholder, setSearchPlaceholder] = useState("Fashion")
  const [query, setQuery] = useState("");
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    setMounted(true);
  }, []);

  const placeholders = [
  "Search for products...",
  "Find wireless headphones",
  "Shop today's best deals",
  "Search for sneakers",
  "Discover new arrivals",
  "Find products under KSh 1,000",
  "Search for laptops",
  "Explore top-rated items",
  "Shop home essentials",
  "Looking for something special?"
];

  function handleSearch(e: React.FormEvent) {
    e.preventDefault();
    if (query.trim()) {
      router.push(`/products?q=${encodeURIComponent(query.trim())}`);
    }
  }


  useEffect(() => {
    let currentIndex = 0;

    const updatePlaceholder = setInterval( () => {
        let nextIndex;

        do {
            nextIndex = Math.floor(Math.random() * placeholders.length)
        }while( nextIndex === currentIndex)

        currentIndex = nextIndex;

        setSearchPlaceholder(placeholders[currentIndex])

    }, 5000)

    return () => clearInterval(updatePlaceholder)

  }, [])

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
    <header className="bg-navy text-white sticky top-0 z-50">
      <div className="w-full mx-auto px-4 h-16 flex items-center gap-4 md:gap-6">

        {/* Logo */}
        <Link href="/" className="shrink-0">
          <Image
            src="/logo.webp"
            alt="Ekshop"
            width={120}
            height={40}
            className="object-contain h-11 w-auto rounded-full"
          />
        </Link>

        {/* Search */}
        <form onSubmit={handleSearch} className="flex-1 max-w-2xl flex items-center rounded-md overflow-hidden">
          <div className="relative flex-1 bg-white">
            <input
            type="text"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            className="w-full px-3 py-2.5 bg-transparent text-sm text-ink outline-none"
          />
          {!query && (
            <AnimatePresence mode="wait">
                <motion.span
                key={searchPlaceholder}
                initial={{ y: 15, opacity: 0 }}
                animate={{ y: 0, opacity: 1 }}
                exit={{ y: -15, opacity: 0 }}
                transition={{ duration: 0.3 }}
                className="absolute left-3 top-1/2 -translate-y-1/2 pointer-events-none text-gray-400"
                >
                    {searchPlaceholder}
                </motion.span>
            </AnimatePresence>
          )}
          </div>
          <button
            type="submit"
            aria-label="Search"
            className="px-4 py-2.5 bg-amber hover:bg-amber-hover text-ink transition-colors"
          >
            <Search size={18} />
          </button>
        </form>

        {/* Right actions */}
        <div className="flex items-center gap-5 shrink-0 ml-auto">

          {/* Account */}
          {mounted && isAuthenticated ? (
            <div className="relative group">
              <button className="flex flex-col items-start text-xs leading-tight">
                <span className="text-white/70">Hello, {user?.first_name}</span>
                <span className="flex items-center gap-1 font-semibold">
                  <User size={16} /> Account
                </span>
              </button>
              {/* Dropdown */}
              <div className="absolute right-0 top-full mt-1 w-48 bg-white text-ink rounded-md shadow-lg border border-border hidden group-hover:block z-50 overflow-hidden">
                <Link href="/account" className="block px-4 py-2 text-sm hover:bg-surface">
                  My Account
                </Link>
                <Link href="/orders" className="block px-4 py-2 text-sm hover:bg-surface">
                  My Orders
                </Link>
                <Link href="/wishlist" className="block px-4 py-2 text-sm hover:bg-surface">
                  Wishlist
                </Link>
                {(user?.role === "seller" || user?.role === "admin") && (
                  <Link href="/dashboard" className="block px-4 py-2 text-sm hover:bg-surface border-t border-border">
                    Seller Dashboard
                  </Link>
                )}
                <button
                  onClick={handleLogout}
                  className="w-full text-left px-4 py-2 text-sm hover:bg-surface border-t border-border"
                >
                  Logout
                </button>
              </div>
            </div>
          ) : (
            <Link href="/login" className="flex flex-col items-start text-xs leading-tight">
              <span className="text-white/70">Hello, Sign in</span>
              <span className="font-semibold">Account</span>
            </Link>
          )}

          <Link href="/orders" className="hidden md:flex flex-col items-start text-xs leading-tight">
            <span className="text-white/70">Returns</span>
            <span className="font-semibold">& Orders</span>
          </Link>

          {/* Cart */}
          <Link href="/cart" className="relative flex items-end gap-1">
            <ShoppingCart size={26} />
            {mounted && totalItems() > 0 && (
              <span className="absolute -top-2 -right-2 bg-amber text-ink text-xs font-bold w-5 h-5 rounded-full flex items-center justify-center">
                {totalItems()}
              </span>
            )}
            <span className="hidden md:inline text-sm font-semibold">Cart</span>
          </Link>
        </div>
      </div>
    </header>
  );
}
