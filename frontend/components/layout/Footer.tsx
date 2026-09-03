import Link from "next/link";
import Image from "next/image";

const COLUMNS = [
  {
    title: "Get to Know Us",
    links: [
      { label: "About Ekshop", href: "/about" },
      { label: "Careers", href: "/careers" },
      { label: "Blog", href: "/blog" },
    ],
  },
  {
    title: "Make Money with Us",
    links: [
      { label: "Sell on Ekshop", href: "/register/plan" },
      { label: "Become a Verified Seller", href: "/register/plan" },
      { label: "Seller Dashboard", href: "/dashboard" },
    ],
  },
  {
    title: "Shop with Confidence",
    links: [
      { label: "Secure Checkout with Paystack", href: "/checkout" },
      { label: "Order Tracking", href: "/orders" },
      { label: "Delivery Areas", href: "/products" },
    ],
  },
  {
    title: "Let Us Help You",
    links: [
      { label: "Your Account", href: "/account" },
      { label: "Returns & Orders", href: "/orders" },
      { label: "Wishlist", href: "/wishlist" },
    ],
  },
  {
    title: "Legal",
    links: [
      { label: "Terms of Service", href: "/terms" },
      { label: "Privacy Policy", href: "/privacy" },
      { label: "Refund Policy", href: "/refund-policy" },
    ],
  },
];

export default function Footer() {
  return (
    <footer className="bg-navy text-white/80 mt-8">
      <div className="max-w-7xl mx-auto px-6 py-10 grid grid-cols-2 md:grid-cols-5 gap-8">
        {COLUMNS.map((col) => (
          <div key={col.title}>
            <h3 className="text-white font-semibold text-sm mb-3">{col.title}</h3>
            <ul className="space-y-2">
              {col.links.map((link) => (
                <li key={link.label}>
                  <Link href={link.href} className="text-xs hover:underline hover:text-white transition-colors">
                    {link.label}
                  </Link>
                </li>
              ))}
            </ul>
          </div>
        ))}
      </div>

      <div className="border-t border-white/10">
        <div className="max-w-7xl mx-auto px-6 py-6 flex flex-col items-center gap-3">
          <Image
            src="/logo.webp"
            alt="Ekshop"
            width={100}
            height={34}
            className="object-contain h-9 w-auto rounded-full opacity-90"
          />
          <p className="text-xs text-white/50 text-center">
            &copy; {new Date().getFullYear()} Ekshop.store, Inc. or its affiliates. Kenya&apos;s Marketplace.
          </p>
        </div>
      </div>
    </footer>
  );
}
