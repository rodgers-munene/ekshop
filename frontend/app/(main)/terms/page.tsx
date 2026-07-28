import type { Metadata } from "next";
import Link from "next/link";

export const metadata: Metadata = {
  title: "Terms of Service",
  description: "The terms governing use of Ekshop's marketplace.",
};

export default function TermsPage() {
  return (
    <div className="w-full max-w-3xl mx-auto px-4 md:px-6 py-10">
      <h1 className="text-2xl font-bold mb-2">Terms of Service</h1>
      <p className="text-xs text-muted mb-8">Last updated: {new Date().toLocaleDateString("en-KE", { day: "numeric", month: "long", year: "numeric" })}</p>

      <div className="space-y-6 text-sm leading-relaxed text-ink">
        <section>
          <h2 className="font-semibold text-base mb-2">1. Who we are</h2>
          <p>
            Ekshop (&quot;Ekshop&quot;, &quot;we&quot;, &quot;us&quot;) operates an online marketplace that connects independent
            sellers (&quot;Sellers&quot;) with buyers (&quot;Buyers&quot;) across Kenya. By creating an account or using the
            platform, you agree to these Terms of Service.
          </p>
        </section>

        <section>
          <h2 className="font-semibold text-base mb-2">2. The marketplace model</h2>
          <p>
            Ekshop is a marketplace, not a retailer. Products listed on the platform are owned, priced, and fulfilled by
            individual Sellers. Ekshop is not a party to the contract of sale between a Buyer and a Seller, though we
            facilitate checkout, payment processing, and dispute support as described below.
          </p>
        </section>

        <section>
          <h2 className="font-semibold text-base mb-2">3. Accounts</h2>
          <p>
            You must provide accurate registration information and keep your login credentials secure. You are
            responsible for all activity under your account. Accounts found to be fraudulent, abusive, or in violation
            of these Terms may be suspended or terminated without notice.
          </p>
        </section>

        <section>
          <h2 className="font-semibold text-base mb-2">4. Selling on Ekshop</h2>
          <p>
            Sellers must accurately describe their products, honour listed prices and stock levels, and fulfil orders
            within the timeframes shown at checkout. Sellers are responsible for the legality, quality, and safety of
            the products they list. Ekshop reserves the right to verify, suspend, or remove any Seller or listing that
            violates these Terms or applicable Kenyan law.
          </p>
        </section>

        <section>
          <h2 className="font-semibold text-base mb-2">5. Orders and payments</h2>
          <p>
            Payments are processed securely through Paystack. By placing an order you authorise Ekshop and its payment
            processor to charge the payment method you provide. Order confirmation does not guarantee availability.
            Sellers may cancel an order if a listed item is unexpectedly out of stock, in which case any payment taken
            will be refunded in full.
          </p>
        </section>

        <section>
          <h2 className="font-semibold text-base mb-2">6. Delivery</h2>
          <p>
            Estimated delivery times shown at checkout are indicative and not guaranteed. Ekshop coordinates delivery
            either directly or through its delivery partners; risk of loss passes to the Buyer upon confirmed delivery
            to the address provided at checkout.
          </p>
        </section>

        <section>
          <h2 className="font-semibold text-base mb-2">7. Returns and refunds</h2>
          <p>
            Returns, exchanges, and refunds are handled in accordance with our{" "}
            <Link href="/refund-policy" className="text-amber underline underline-offset-2">Refund Policy</Link>.
          </p>
        </section>

        <section>
          <h2 className="font-semibold text-base mb-2">8. Prohibited conduct</h2>
          <p>
            You may not use Ekshop to list counterfeit, stolen, or illegal goods; to misrepresent your identity; to
            manipulate reviews or ratings; to circumvent platform fees; or to engage in any activity that violates
            Kenyan law or infringes the rights of others.
          </p>
        </section>

        <section>
          <h2 className="font-semibold text-base mb-2">9. Limitation of liability</h2>
          <p>
            To the maximum extent permitted by law, Ekshop is not liable for indirect, incidental, or consequential
            damages arising from your use of the platform, transactions with Sellers, or delivery delays. Our
            aggregate liability for any claim is limited to the amount you paid for the order giving rise to the
            claim.
          </p>
        </section>

        <section>
          <h2 className="font-semibold text-base mb-2">10. Changes to these Terms</h2>
          <p>
            We may update these Terms from time to time. Continued use of Ekshop after changes take effect constitutes
            acceptance of the revised Terms.
          </p>
        </section>

        <section>
          <h2 className="font-semibold text-base mb-2">11. Governing law</h2>
          <p>These Terms are governed by the laws of the Republic of Kenya.</p>
        </section>

        <section>
          <h2 className="font-semibold text-base mb-2">12. Contact</h2>
          <p>Questions about these Terms can be sent to <span className="text-muted">support@ekshop.co.ke</span>.</p>
        </section>
      </div>
    </div>
  );
}
