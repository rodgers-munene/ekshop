import type { Metadata } from "next";
import Link from "next/link";

export const metadata: Metadata = {
  title: "About Ekshop",
  description: "Learn more about Ekshop, Kenya's marketplace for verified sellers.",
};

export default function AboutPage() {
  return (
    <div className="w-full max-w-3xl mx-auto px-4 md:px-6 py-10">
      <h1 className="text-2xl font-bold mb-2">About Ekshop</h1>
      <p className="text-xs text-muted mb-8">Kenya&apos;s marketplace for verified sellers</p>

      <div className="space-y-6 text-sm leading-relaxed text-ink">
        <section>
          <p>
            Ekshop is an online marketplace built for Kenya, connecting buyers with verified sellers across the
            country. Whether you&apos;re shopping for electronics, fashion, home goods, or supporting a local hustle,
            Ekshop makes it easy to discover products, pay securely with M-Pesa or Paystack, and get your order
            delivered nationwide.
          </p>
        </section>

        <section>
          <h2 className="font-semibold text-base mb-2">What we stand for</h2>
          <ul className="list-disc pl-5 space-y-1">
            <li>Verified sellers you can trust, vetted for quality and reliability</li>
            <li>Secure checkout and transparent pricing</li>
            <li>Nationwide delivery, wherever you are in Kenya</li>
            <li>Tools that help sellers grow, from a simple storefront to Tara POS</li>
          </ul>
        </section>

        <section>
          <h2 className="font-semibold text-base mb-2">Get in touch</h2>
          <p>
            Have a question or want to sell on Ekshop?{" "}
            <Link href="/register" className="text-amber underline underline-offset-2">Start selling</Link>{" "}
            or reach out to <span className="text-muted">support@ekshop.co.ke</span>.
          </p>
        </section>
      </div>
    </div>
  );
}
