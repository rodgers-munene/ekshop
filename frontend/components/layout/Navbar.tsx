"use client";

import Link from "next/link";
import Image from "next/image";
import { useRouter } from "next/navigation";
import { useEffect, useRef, useState, useSyncExternalStore } from "react";
import { useQuery } from "@tanstack/react-query";
import { ShoppingCart, User, Search, Loader2 } from "lucide-react";
import { useAuthStore } from "@/store/authStore";
import { useCartStore } from "@/store/cartStore";
import { AnimatePresence, motion } from "motion/react"
import { Product, ProductListResponse } from "@/types/interface";
import { formatKES, resolveImageUrl, decodeHtml } from "@/lib/utils";
import NotificationBell from "@/components/layout/NotificationBell";

const API_URL = process.env.NEXT_PUBLIC_API_URL;

export default function Navbar() {
  const router = useRouter();
  const { user, isAuthenticated, clearUser } = useAuthStore();
  const totalItems = useCartStore((state) => state.totalItems);
  const [searchPlaceholder, setSearchPlaceholder] = useState("Fashion")
  const [query, setQuery] = useState("");
  const [debouncedQuery, setDebouncedQuery] = useState("");
  const [showSuggestions, setShowSuggestions] = useState(false);
  const searchRef = useRef<HTMLFormElement>(null);
  const mounted = useSyncExternalStore(
    () => () => {},
    () => true,
    () => false
  );

  useEffect(() => {
    const timeout = setTimeout(() => setDebouncedQuery(query.trim()), 300);
    return () => clearTimeout(timeout);
  }, [query]);

  useEffect(() => {
    function handleClickOutside(e: MouseEvent) {
      if (searchRef.current && !searchRef.current.contains(e.target as Node)) {
        setShowSuggestions(false);
      }
    }
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  const { data: suggestions = [], isFetching: suggestionsLoading } = useQuery({
    queryKey: ["search-suggestions", debouncedQuery],
    queryFn: () =>
      fetch(`${API_URL}/products/?q=${encodeURIComponent(debouncedQuery)}&limit=6`)
        .then((r) => r.json())
        .then((data: ProductListResponse) => data.results ?? []),
    enabled: debouncedQuery.length >= 2,
    staleTime: 60_000,
  });

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
      setShowSuggestions(false);
      router.push(`/products?q=${encodeURIComponent(query.trim())}`);
    }
  }

  function goToProduct(product: Product) {
    setShowSuggestions(false);
    setQuery("");
    router.push(`/products/${product.slug}`);
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
      <div className="w-full mx-auto px-3 md:px-4 h-14 md:h-16 flex items-center gap-2 md:gap-6">

        {/* Logo */}
        <Link href="/" className="shrink-0">
          <Image
            src="/logo.webp"
            alt="Ekshop"
            width={120}
            height={40}
            className="object-contain h-8 md:h-11 w-auto rounded-full"
          />
        </Link>

        {/* Search */}
        <form
          ref={searchRef}
          onSubmit={handleSearch}
          className="relative flex-1 min-w-0 max-w-lg"
        >
          <div className="h-9 md:h-10 flex items-stretch rounded-full overflow-hidden ring-1 ring-inset ring-black/5 focus-within:ring-2 focus-within:ring-amber transition-shadow">
            <div className="relative flex-1 bg-white">
              <input
              type="text"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              onFocus={() => setShowSuggestions(true)}
              className="w-full h-full pl-6 md:pl-7 pr-3 bg-transparent text-sm text-ink outline-none"
            />
            {!query && (
              <AnimatePresence mode="wait">
                  <motion.span
                  key={searchPlaceholder}
                  initial={{ y: 15, opacity: 0 }}
                  animate={{ y: 0, opacity: 1 }}
                  exit={{ y: -15, opacity: 0 }}
                  transition={{ duration: 0.3 }}
                  className="absolute left-6 md:left-7 top-1/2 -translate-y-1/2 pointer-events-none text-gray-400 hidden sm:block"
                  >
                      {searchPlaceholder}
                  </motion.span>
              </AnimatePresence>
            )}
            </div>
            <button
              type="submit"
              aria-label="Search"
              className="px-4 md:px-5 flex items-center justify-center bg-amber hover:bg-amber-hover text-ink transition-colors shrink-0"
            >
              <Search size={18} />
            </button>
          </div>

          {/* Suggestions dropdown */}
          {showSuggestions && query.trim().length >= 2 && (
            <div className="absolute left-0 right-0 top-full mt-2 bg-white text-ink rounded-2xl shadow-lg border border-border overflow-hidden z-50 max-h-96 overflow-y-auto">
              {suggestionsLoading ? (
                <div className="flex items-center justify-center gap-2 py-6 text-sm text-muted">
                  <Loader2 size={16} className="animate-spin" /> Searching...
                </div>
              ) : suggestions.length > 0 ? (
                <ul>
                  {suggestions.map((product) => {
                    const img = product.images?.find((i) => i.is_primary) ?? product.images?.[0];
                    return (
                      <li key={product.id}>
                        <button
                          type="button"
                          onClick={() => goToProduct(product)}
                          className="w-full flex items-center gap-3 px-3 py-2 hover:bg-surface text-left transition-colors"
                        >
                          <div className="w-10 h-10 rounded bg-surface shrink-0 overflow-hidden flex items-center justify-center">
                            {img ? (
                              // eslint-disable-next-line @next/next/no-img-element
                              <img src={resolveImageUrl(img.url)} alt="" className="w-full h-full object-cover" />
                            ) : (
                              <Search size={14} className="text-muted" />
                            )}
                          </div>
                          <div className="min-w-0 flex-1">
                            <p className="text-sm truncate">{decodeHtml(product.name)}</p>
                            <p className="text-xs text-muted">{formatKES(product.price)}</p>
                          </div>
                        </button>
                      </li>
                    );
                  })}
                </ul>
              ) : (
                <p className="py-6 text-center text-sm text-muted">No products found</p>
              )}
            </div>
          )}
        </form>

        {/* Right actions */}
        <div className="flex items-center gap-3 md:gap-5 shrink-0 ml-auto">

          {/* Notifications */}
          {mounted && isAuthenticated && <NotificationBell />}

          {/* Account */}
          {mounted && isAuthenticated ? (
            <div className="relative group">
              <button className="hidden sm:flex items-center gap-1.5 text-sm font-semibold">
                <User size={18} /> {user?.first_name}
              </button>
              <button className="sm:hidden flex items-center">
                <User size={22} />
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
                <Link href="/messages" className="block px-4 py-2 text-sm hover:bg-surface">
                  Messages
                </Link>
                {user?.role === "seller" && (
                  <Link href="/dashboard" className="block px-4 py-2 text-sm hover:bg-surface border-t border-border">
                    Seller Dashboard
                  </Link>
                )}
                {user?.role === "admin" && (
                  <Link href="/admin" className="block px-4 py-2 text-sm hover:bg-surface border-t border-border">
                    Admin Panel
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
            <Link href="/login" className="flex items-center gap-1.5 text-sm font-semibold">
              <User size={18} />
              <span className="hidden sm:inline">Sign in</span>
            </Link>
          )}

          {/* Cart */}
          <Link href="/cart" className="relative flex items-center">
            <ShoppingCart size={22} className="md:w-6.5 md:h-6.5" />
            {mounted && totalItems() > 0 && (
              <span className="absolute -top-2 -right-2 bg-amber text-ink text-xs font-bold w-5 h-5 rounded-full flex items-center justify-center">
                {totalItems()}
              </span>
            )}
          </Link>
        </div>
      </div>
    </header>
  );
}
