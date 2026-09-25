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
      <p className="text-xs text-muted mb-8">Last updated: 22 September 2026</p>

      <div className="space-y-6 text-sm leading-relaxed text-ink">
        <p>
          Welcome to Ekshop. Please read these Terms of Service carefully before creating an account or using our
          platform. By accessing or using any part of the platform, you agree to be bound by these Terms. If you do not
          agree to all the terms and conditions, then you may not access the platform or use any services.
        </p>

        <section>
          <h2 className="font-semibold text-base mb-2">1. Who we are</h2>
          <p>
            Ekshop (&quot;Ekshop&quot;, &quot;we&quot;, &quot;us&quot;, &quot;our&quot;) operates an e-commerce marketplace
            platform, including website application layers, mobile interfaces, and associated services, connecting
            independent sellers with buyers across the Republic of Kenya. These Terms of Service legally bind any person
            or entity accessing the platform (&quot;User&quot;, &quot;you&quot;, &quot;your&quot;).
          </p>
        </section>

        <section>
          <h2 className="font-semibold text-base mb-2">2. Definitions and interpretations</h2>
          <p>In these Terms of Service, the following capitalized terms shall have the meanings ascribed to them below:</p>
          <ul className="list-disc pl-5 space-y-1 mt-2">
            <li>
              <strong>Platform:</strong> The Ekshop website, mobile application, checkout systems, dashboard portals, and
              all associated infrastructure operated by Ekshop.
            </li>
            <li>
              <strong>Seller:</strong> Any verified individual, merchant, business entity, or authorized third-party
              retailer listing, offering, advertising, or selling products to Buyers via the Platform.
            </li>
            <li>
              <strong>Buyer:</strong> Any end-consumer or registered retail customer browsing, placing orders, or
              purchasing goods via the Platform.
            </li>
            <li>
              <strong>Rider / Delivery Partner:</strong> Independent third-party logistics providers, courier services,
              or individual operators contracted or coordinated to transport and deliver products from Sellers to Buyers.
            </li>
            <li>
              <strong>Services:</strong> The core marketplace connection mechanisms, payment processing interfaces,
              logistics facilitation tools, order fulfillment updates, and dispute support resolution tools provided by
              Ekshop.
            </li>
          </ul>
        </section>

        <section>
          <h2 className="font-semibold text-base mb-2">3. The marketplace model</h2>
          <p>
            Ekshop is a multi-vendor marketplace engine and does not act as a retailer, producer, distributor, or
            inventory owner of items listed on the Platform. All products uploaded are owned, described, and priced
            solely by individual independent Sellers. Consequently, Ekshop is not a direct party to the contract of sale
            executed between a Buyer and a Seller. While Ekshop coordinates checkout, secure payment infrastructure,
            order dispatch tracking, and baseline customer dispute mediation, it maintains no authority over product
            defects, stock accurate availability, or fulfillment absolute timelines beyond explicit platform policy
            terms.
          </p>
        </section>

        <section>
          <h2 className="font-semibold text-base mb-2">4. Accounts and registration</h2>
          <p>
            <strong>4.1. Account Creation:</strong> To unlock transactions or product listings, users must establish an
            official account. You guarantee that all inputs provided during registration are authentic, up-to-date, and
            completely accurate. You are strictly responsible for preserving the tight confidentiality of your account
            credentials, passwords, and access tokens.
          </p>
          <p className="mt-2">
            <strong>4.2. Responsibility &amp; Abuse:</strong> You accept direct legal accountability for any and all
            transactions, data entries, or active behaviors initiated under your account. Fraudulent registration,
            duplicate deceptive accounts, profile spoofing, or violations of systemic safety barriers will lead to the
            immediate, non-negotiable suspension or definitive termination of your account without prior notice.
          </p>
        </section>

        <section>
          <h2 className="font-semibold text-base mb-2">5. Seller obligations and prohibited conduct</h2>
          <p>
            <strong>5.1. Accuracy of Listings:</strong> Sellers must present realistic, true, and high-fidelity
            specifications, images, conditions, and categorization details for all listed inventory. Listed prices must
            remain fixed and honored at the exact checkout timestamp. Artificial inflation or manipulative price
            shifting post-order is strictly forbidden.
          </p>
          <p className="mt-2">
            <strong>5.2. Prohibited Goods:</strong> Users are prohibited from listing, trading, or facilitating the
            delivery of counterfeit merchandise, stolen items, unregulated medicinal pharmaceuticals, weapons, dangerous
            chemical composites, or any goods banned under the laws of Kenya. Circumvention of platform fees, review
            manipulation, and direct solicitation of off-platform transactional payments from Ekshop acquired leads are
            strictly prohibited and subject to legal remedies.
          </p>
        </section>

        <section>
          <h2 className="font-semibold text-base mb-2">6. Marketplace fees, commissions, and payout structures</h2>
          <p>
            <strong>6.1. Platform Commissions:</strong> Ekshop charges a structural service marketplace fee or
            commission on successful completed vendor sales, as documented within separate active vendor schedules or
            onboard frameworks. By listing on Ekshop, the Seller explicitly authorizes Ekshop to deduct its standard
            marketplace commissions and payment merchant processing premiums prior to calculating and releasing final
            net merchant balances.
          </p>
          <p className="mt-2">
            <strong>6.2. Tax &amp; eTIMS Compliance:</strong> Sellers possess complete and absolute liability for
            executing, evaluating, registering, and remitting all appropriate taxes, tariffs, and excise fees arising
            from their marketplace activities, including Value Added Tax (VAT). Sellers must adhere tightly to all
            directives issued by the Kenya Revenue Authority (KRA), including full deployment and execution of
            Electronic Tax Invoice Management System (eTIMS) invoices where mandatory by statutory frameworks.
          </p>
        </section>

        <section>
          <h2 className="font-semibold text-base mb-2">7. Orders and Safaricom M-Pesa payments</h2>
          <p>
            <strong>7.1. Authorization:</strong> Payment services on Ekshop are primarily processed securely via
            Safaricom M-Pesa. By submitting an electronic checkout order on the Platform, you formally authorize Ekshop
            and its integrated payment gateway processors to execute an immediate push-STK or equivalent transaction
            sequence charging your submitted mobile wallet.
          </p>
          <p className="mt-2">
            <strong>7.2. Out of Stock &amp; Cancellations:</strong> Order creation logs and confirmation receipt signals
            do not provide an ironclad guarantee of immediate stock availability. If a Seller discovers an unexpected
            stock rupture post-order execution, the Seller must cancel the item line immediately. Ekshop will process an
            equitable, full refund of all captured funds directly back to the originating Safaricom M-Pesa mobile
            number or user credit balance.
          </p>
        </section>

        <section>
          <h2 className="font-semibold text-base mb-2">8. Delivery ecosystem and risk transfer</h2>
          <p>
            <strong>8.1. Indicative Timelines:</strong> Estimated fulfillment and transit metrics visible during the
            checkout portal are purely indicative predictions and do not carry precise legal deadlines or chronological
            guarantees.
          </p>
          <p className="mt-2">
            <strong>8.2. Logistics &amp; Risk:</strong> Ekshop arranges dispatch coordinates utilizing third-party
            independent Riders and delivery agencies. The legal risk of physical item loss, damage, or degradation
            passes dynamically from the Seller to the Rider upon collection, and successfully transfers entirely to the
            Buyer only upon formal, recorded signature or physical handoff at the destination address provided during
            checkout.
          </p>
          <p className="mt-2">
            <strong>8.3. Failed Delivery Protocol:</strong> If a Buyer remains entirely unreachable, rejects delivery
            without lawful cause, or fails to appear at the designated drop zone during multiple delivery attempts, the
            item will return to the origin hub. Ekshop and its logistics partners reserve the right to bill the
            defaulting party for extra transit costs or withhold original courier delivery fees from subsequent refund
            sequences.
          </p>
        </section>

        <section>
          <h2 className="font-semibold text-base mb-2">9. Returns, refunds, and disagreements</h2>
          <p>
            All requests for item returns, exchange tickets, broken product declarations, or financial refunds must
            strictly adhere to the operational rules embedded inside our official, separate{" "}
            <Link href="/refund-policy" className="text-amber underline underline-offset-2">Refund Policy</Link>{" "}
            framework. Claims must be filed within our standard window via Ekshop customer support channels to preserve
            eligibility for secure escrow hold interventions.
          </p>
        </section>

        <section>
          <h2 className="font-semibold text-base mb-2">10. Data protection and privacy compliance</h2>
          <p>
            Ekshop takes user data privacy seriously. All practices regarding data gathering, profile collection, storage
            architectures, tracking cookies, and marketing opt-ins are managed under strict compliance with the Kenyan
            Data Protection Act, 2019, as described in our{" "}
            <Link href="/privacy" className="text-amber underline underline-offset-2">Privacy Policy</Link>. By
            interacting with the Platform, you acknowledge that your contact details, physical delivery address, and
            tracking data will be securely processed and shared exclusively with relevant parties (such as logistics
            Riders and processing Sellers) solely to the extent required to execute and fulfill your orders.
          </p>
        </section>

        <section>
          <h2 className="font-semibold text-base mb-2">11. Dispute resolution and governing law</h2>
          <p>
            <strong>11.1. Governing Law:</strong> These Terms of Service, platform structures, and transactional
            procedures are governed by and construed strictly under the laws of the Republic of Kenya.
          </p>
          <p className="mt-2">
            <strong>11.2. Amicable Settlement:</strong> In the event of any legal debate, claims, or systemic
            disagreement arising between a User and Ekshop, the parties must first submit their grievances to Ekshop
            Customer Support for a mandatory 30-day amicable mediation window.
          </p>
          <p className="mt-2">
            <strong>11.3. Arbitration:</strong> If an amicable settlement is not reached within 30 days, the dispute
            shall be resolved through private, final, and legally binding Arbitration conducted in Nairobi, Kenya. The
            proceedings shall be administered in accordance with the provisions of the Arbitration Act (Cap 49 of the
            Laws of Kenya) by a sole arbitrator mutually agreed upon, or failing agreement, appointed by the Chairman of
            the Chartered Institute of Arbitrators (Kenya Branch).
          </p>
        </section>

        <section>
          <h2 className="font-semibold text-base mb-2">12. Limitation of liability and indemnification</h2>
          <p>
            <strong>12.1. Liability Cap:</strong> To the highest threshold permitted by applicable law, Ekshop, its
            directors, employees, or subsidiaries shall not be held liable for any indirect, unintended, accidental,
            punitive, or consequential damages, or loss of profits arising out of platform functionality, down-times,
            or bad merchant interactions.
          </p>
          <p className="mt-2">
            <strong>12.2. Indemnification:</strong> Users explicitly promise to indemnify, legally defend, and hold
            harmless Ekshop, its brand layers, and officers against any third-party lawsuits, damages, monetary loss, or
            regulatory penalties caused by your breach of these Terms, selling of defective goods, or active violation
            of intellectual property laws.
          </p>
        </section>

        <section>
          <h2 className="font-semibold text-base mb-2">13. Contact</h2>
          <p>
            For any clarifications, compliance reports, legal notices, or account assistance regarding these marketplace
            terms, please send formal digital correspondence to our official helpdesk at{" "}
            <span className="text-muted">supportteam@ekshop.store</span>.
          </p>
        </section>
      </div>
    </div>
  );
}
