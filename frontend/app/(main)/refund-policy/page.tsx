import type { Metadata } from "next";
import Link from "next/link";

export const metadata: Metadata = {
  title: "Refund Policy",
  description: "Ekshop's policy on cancellations, returns, and refunds.",
};

export default function RefundPolicyPage() {
  return (
    <div className="w-full max-w-3xl mx-auto px-4 md:px-6 py-10">
      <h1 className="text-2xl font-bold mb-2">Refund, Cancellation &amp; Return Policy</h1>
      <p className="text-xs text-muted mb-8">Last updated: 24 September 2026</p>

      <div className="space-y-6 text-sm leading-relaxed text-ink">
        <p>
          This Refund, Cancellation &amp; Return Policy governs all transactions executed on the Ekshop e-commerce
          platform (the &quot;Platform&quot;). Ekshop operates as a multi-vendor marketplace connecting independent
          buyers (&quot;Buyers&quot;) and merchants (&quot;Sellers&quot;). This policy outlines the standards,
          procedures, and timelines intended to facilitate a transparent, equitable, and secure exchange while ensuring
          compliance with local consumer protection standards.
        </p>

        <section>
          <h2 className="font-semibold text-base mb-2">1. Order cancellations and pre-shipment modifications</h2>
          <p>
            Buyers maintain the statutory right to cancel any order without penalty, provided that the order has not
            yet been formally confirmed or dispatched for shipping by the designated Seller. To exercise this right:
          </p>
          <ul className="list-disc pl-5 space-y-1 mt-2">
            <li>
              <strong>Self-Service Cancellation:</strong> Buyers may initiate a cancellation directly through their{" "}
              <Link href="/orders" className="text-amber underline underline-offset-2">Orders</Link> page on the
              Platform.
            </li>
            <li>
              <strong>Seller Processing Threshold:</strong> Once a Seller changes the order status to
              &quot;Confirmed&quot; or &quot;Shipped&quot;, self-service cancellation is disabled, and the transaction
              moves to the returns process below.
            </li>
            <li>
              <strong>Financial Reversal Timeline:</strong> Upon verified pre-shipment cancellation, any funds already
              captured will be fully reversed to the original channel of payment. Refunds to credit or debit cards or
              other payment networks will reflect within 5 to 10 business days, subject to standard interbank
              processing cycles.
            </li>
          </ul>
        </section>

        <section>
          <h2 className="font-semibold text-base mb-2">2. Return authorization</h2>
          <p>
            Unless listed under the exemptions below, physical merchandise purchased via the Platform is eligible for
            return within <strong>seven (7) calendar days</strong> from the verifiable time of delivery. Returns are
            limited to items meeting the following criteria:
          </p>
          <ul className="list-disc pl-5 space-y-1 mt-2">
            <li>The item arrived physically damaged or structurally compromised during transit.</li>
            <li>
              The product has operational defects or fails to function in accordance with the manufacturer
              specifications.
            </li>
            <li>
              The item delivered is materially different, mislabeled, or variant-mismatched relative to the product
              listing published by the Seller.
            </li>
          </ul>

          <h3 className="font-semibold mt-4 mb-1">How to start a return</h3>
          <p>
            To start a return, open the order and message the Seller with your return request. If the Seller fails to
            respond, acknowledge, or meaningfully engage with the request within forty-eight (48) business hours,
            escalate the matter to Ekshop Support at <span className="text-muted">supportteam@ekshop.store</span> for
            platform-level intervention.
          </p>

          <h3 className="font-semibold mt-4 mb-1">Non-returnable items</h3>
          <p>
            For public health, sanitation, and safety reasons, the following product categories are excluded from return
            eligibility and will not be accepted under any circumstances:
          </p>
          <ul className="list-disc pl-5 space-y-1 mt-2">
            <li>
              <strong>Perishable Goods:</strong> Fresh foodstuffs, beverages, agricultural products, or items with rapid
              expiration.
            </li>
            <li>
              <strong>Personal Care &amp; Hygiene Products:</strong> Opened cosmetics, skincare, personal grooming
              devices, and intimate apparel that have been unsealed after delivery.
            </li>
            <li>
              <strong>Final Sale Items:</strong> Clearance stock, custom-tailored goods, or items clearly designated as
              &quot;Final Sale&quot; at the moment of purchase.
            </li>
            <li>
              <strong>Post-Delivery Misuse:</strong> Products showing wear, physical alteration, internal damage, or
              environmental exposure resulting from mishandling after delivery.
            </li>
          </ul>
        </section>

        <section>
          <h2 className="font-semibold text-base mb-2">3. How refunds are paid</h2>
          <p>
            Once a return is formally authorized by the Seller, or cleared by an Ekshop dispute ruling, the refund is
            issued. Where the refund goes depends on how you paid:
          </p>
          <div className="overflow-x-auto mt-3">
            <table className="w-full text-left border border-border">
              <thead className="bg-surface">
                <tr>
                  <th className="px-3 py-2 font-semibold">Payment method</th>
                  <th className="px-3 py-2 font-semibold">Refunded to</th>
                  <th className="px-3 py-2 font-semibold">Processing time</th>
                </tr>
              </thead>
              <tbody>
                <tr className="border-t border-border">
                  <td className="px-3 py-2">Safaricom M-Pesa</td>
                  <td className="px-3 py-2">The original M-Pesa mobile number</td>
                  <td className="px-3 py-2">Within minutes to 4 hours from approval</td>
                </tr>
                <tr className="border-t border-border">
                  <td className="px-3 py-2">Paystack (card or subscription)</td>
                  <td className="px-3 py-2">The original issuing bank account</td>
                  <td className="px-3 py-2">5 to 10 business days</td>
                </tr>
              </tbody>
            </table>
          </div>
          <p className="mt-3">
            M-Pesa refunds usually reflect almost instantly once authorized, without the delays of bank transfers.
            Ekshop does not offer cash-in-hand refunds or refunds to any other third-party destination, in line with
            anti-money laundering (AML) requirements.
          </p>
        </section>

        <section>
          <h2 className="font-semibold text-base mb-2">4. Logistics failures and non-delivery</h2>
          <p>
            If an order fails to arrive at the delivery address and tracking shows no transit activity for an
            unreasonably long period, the Buyer should alert Ekshop Support. Ekshop will investigate with the delivery
            partner and the Seller. If the shipment is verified as permanently lost, misrouted, or unfulfilled, a refund
            of 100% of the purchase value, including delivery fees, will be processed immediately.
          </p>
        </section>

        <section>
          <h2 className="font-semibold text-base mb-2">5. Dispute resolution and platform mediation</h2>
          <p>
            Where the Buyer and the Seller cannot agree on a return or refund, either party may ask Ekshop to
            intervene. Send an escalation containing the order reference number, photographic or written evidence of
            the problem, and your messages with the other party. Ekshop will review the case and issue a binding
            resolution within seventy-two (72) business hours.
          </p>
        </section>

        <section>
          <h2 className="font-semibold text-base mb-2">6. Contact</h2>
          <p>
            For claims, return authorizations, ongoing disputes, or questions about this policy, contact our support
            desk at <span className="text-muted">supportteam@ekshop.store</span>, or use &quot;Contact Support&quot; on
            the <Link href="/messages" className="text-amber underline underline-offset-2">Messages</Link> page while
            signed in. Please include your order number.
          </p>
        </section>
      </div>
    </div>
  );
}
