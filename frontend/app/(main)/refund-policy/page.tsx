import type { Metadata } from "next";
import Link from "next/link";

export const metadata: Metadata = {
  title: "Refund Policy",
  description: "Ekshop's policy on returns, exchanges, and refunds.",
};

export default function RefundPolicyPage() {
  return (
    <div className="w-full max-w-3xl mx-auto px-4 md:px-6 py-10">
      <h1 className="text-2xl font-bold mb-2">Refund Policy</h1>
      <p className="text-xs text-muted mb-8">Last updated: {new Date().toLocaleDateString("en-KE", { day: "numeric", month: "long", year: "numeric" })}</p>

      <div className="space-y-6 text-sm leading-relaxed text-ink">
        <section>
          <h2 className="font-semibold text-base mb-2">1. Order cancellations</h2>
          <p>
            You can cancel an order from your{" "}
            <Link href="/orders" className="text-amber underline underline-offset-2">Orders</Link> page as long as the
            Seller has not yet confirmed or shipped it. Once cancelled, any payment already taken is refunded in full
            to your original payment method within 5–10 business days.
          </p>
        </section>

        <section>
          <h2 className="font-semibold text-base mb-2">2. Returns</h2>
          <p>
            Most items can be returned within <strong>7 days</strong> of delivery if they arrive damaged, defective,
            or materially different from their listing. To start a return, message the Seller directly from your
            order, or contact Ekshop support if the Seller is unresponsive.
          </p>
          <p className="mt-2">Some items are not eligible for return, including:</p>
          <ul className="list-disc pl-5 space-y-1 mt-1">
            <li>Perishable goods</li>
            <li>Personal care and hygiene items that have been opened</li>
            <li>Items marked &quot;final sale&quot; on their listing</li>
            <li>Products damaged through misuse after delivery</li>
          </ul>
        </section>

        <section>
          <h2 className="font-semibold text-base mb-2">3. How refunds work</h2>
          <p>
            Once a return is approved by the Seller (or by Ekshop in a disputed case), the refund is issued to the
            payment method used at checkout. Paystack refunds typically reflect within 5–10 business days, depending
            on your bank.
          </p>
        </section>

        <section>
          <h2 className="font-semibold text-base mb-2">4. Failed or undelivered orders</h2>
          <p>
            If an order fails to arrive and tracking shows no delivery activity for an extended period, contact
            support, and we will work with the Seller or delivery agent to resolve it, and issue a full refund if the
            order cannot be located or fulfilled.
          </p>
        </section>

        <section>
          <h2 className="font-semibold text-base mb-2">5. Disputes</h2>
          <p>
            If you and a Seller cannot resolve a return or refund directly, Ekshop can step in to mediate. Reach out
            with your order number and details of the issue, and we&apos;ll review the case.
          </p>
        </section>

        <section>
          <h2 className="font-semibold text-base mb-2">6. Contact</h2>
          <p>
            For help with a return or refund, contact <span className="text-muted">support@ekshop.co.ke</span> with
            your order number.
          </p>
        </section>
      </div>
    </div>
  );
}
