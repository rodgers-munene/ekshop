import type { Metadata } from "next";
import Link from "next/link";

export const metadata: Metadata = {
  title: "Privacy Policy",
  description: "How Ekshop collects, uses, and protects your data under the Kenya Data Protection Act, 2019.",
};

export default function PrivacyPage() {
  return (
    <div className="w-full max-w-3xl mx-auto px-4 md:px-6 py-10">
      <h1 className="text-2xl font-bold mb-2">Privacy Policy</h1>
      <p className="text-xs text-muted mb-8">Last updated: 24 September 2026</p>

      <div className="space-y-6 text-sm leading-relaxed text-ink">
        <p>
          Ekshop (&quot;we&quot;, &quot;us&quot;, or &quot;our&quot;) operates the Ekshop e-commerce platform, linking
          independent sellers with buyers. We are committed to protecting your personal data and privacy in full
          compliance with the Kenya Data Protection Act, 2019 and its Regulations. This Privacy Policy explains how we
          collect, use, disclose, retain, and safeguard your personal information when you use our website, mobile
          application, and related services (together, the &quot;Platform&quot;). Please read it carefully to
          understand our practices regarding your personal data.
        </p>

        <section>
          <h2 className="font-semibold text-base mb-2">1. Information we collect</h2>
          <p>We collect the following types of information from and about users of our Platform:</p>
          <ul className="list-disc pl-5 space-y-1 mt-2">
            <li>
              <strong>1.1 Account information:</strong> personal details provided when creating an account, including
              your full name, verified email address, phone number, county of residence, and a securely hashed password.
            </li>
            <li>
              <strong>1.2 Order and transaction information:</strong> details needed to run your orders, including
              delivery addresses, order history, items purchased, pricing, and records of customer service
              communications or messages exchanged with Sellers on the Platform.
            </li>
            <li>
              <strong>1.3 Payment information:</strong> payments are handled by secure third-party gateways. Checkout
              payments are processed directly by Safaricom M-Pesa, and Seller subscription billing is managed by
              Paystack. Ekshop does not store, intercept, or log your M-Pesa PIN, card numbers, CVV codes, or bank
              account credentials.
            </li>
            <li>
              <strong>1.4 Usage, technical, and analytics data:</strong> automated logs of how you use the Platform,
              including pages viewed, products clicked, searches made, time spent on items, device identifiers, and
              similar activity used to improve recommendations.
            </li>
          </ul>
        </section>

        <section>
          <h2 className="font-semibold text-base mb-2">2. Legal basis and how we use your information</h2>
          <p>
            We process personal data only where the Kenya Data Protection Act, 2019 allows it. We use it for:
          </p>
          <ul className="list-disc pl-5 space-y-1 mt-2">
            <li>
              <strong>Fulfilling orders:</strong> processing checkout, confirming payments, passing accurate delivery
              details to delivery partners, and sending order updates.
            </li>
            <li>
              <strong>Account security and identity verification:</strong> authenticating sign-ins, blocking
              unauthorized access attempts, and protecting accounts from takeover or fraud.
            </li>
            <li>
              <strong>Platform communication:</strong> sending essential order updates, security advisories, and system
              alerts. If you opt in to marketing, we also send promotional offers.
            </li>
            <li>
              <strong>Personalization:</strong> analyzing Platform activity to tailor product rankings, local results,
              and search suggestions.
            </li>
            <li>
              <strong>Fraud prevention and compliance:</strong> detecting and stopping unauthorized activity, payment
              fraud, bots, and serious violations of our{" "}
              <Link href="/terms" className="text-amber underline underline-offset-2">Terms of Service</Link>.
            </li>
          </ul>
        </section>

        <section>
          <h2 className="font-semibold text-base mb-2">3. Information sharing and disclosure</h2>
          <p>
            Ekshop follows the principle of data minimization. We do not sell, lease, rent, or trade your personal
            information to third parties. We share data only with:
          </p>
          <ul className="list-disc pl-5 space-y-1 mt-2">
            <li>
              <strong>Independent Sellers:</strong> your name, delivery phone number, and delivery location, so the
              Seller can fulfil your order.
            </li>
            <li>
              <strong>Payment processors:</strong> the transaction details Safaricom M-Pesa and Paystack need to
              authorize payments, without Ekshop holding your credentials.
            </li>
            <li>
              <strong>Logistics and delivery partners:</strong> delivery locations, maps, and names, so couriers can
              deliver accurately.
            </li>
            <li>
              <strong>Infrastructure and operational providers:</strong> trusted third parties that help us run the
              Platform, including Google (for transactional email and maps) and encrypted cloud hosting providers.
            </li>
          </ul>
        </section>

        <section>
          <h2 className="font-semibold text-base mb-2">4. Cookies and tracking technologies</h2>
          <p>
            Ekshop uses cookies to make the Platform work well. Essential cookies keep you signed in as you move between
            pages and remember the items in your cart. Performance and analytics cookies help us measure how the
            interface performs and improve response times. You can reject or restrict non-essential cookies in your
            browser settings, though some features may not work as well.
          </p>
        </section>

        <section>
          <h2 className="font-semibold text-base mb-2">5. Data retention</h2>
          <p>
            We keep personal data only as long as needed for the purposes in this Privacy Policy. Account details are
            held securely while your account is active. Records of closed or inactive accounts, transaction ledgers,
            and formal communications are kept for the longer periods required by legal, accounting, tax, and
            regulatory obligations in Kenya.
          </p>
        </section>

        <section>
          <h2 className="font-semibold text-base mb-2">6. Your rights under the Kenya Data Protection Act, 2019</h2>
          <p>
            Under Section 26 of the Kenya Data Protection Act, 2019, you have the rights below. You can exercise them
            from your{" "}
            <Link href="/account" className="text-amber underline underline-offset-2">account settings</Link> or by
            sending a request to our data protection team:
          </p>
          <ul className="list-disc pl-5 space-y-1 mt-2">
            <li>
              <strong>Right to be informed:</strong> to know clearly why and how your personal data is used.
            </li>
            <li>
              <strong>Right of access:</strong> to request a complete breakdown or digital export of the data linked to
              your profile.
            </li>
            <li>
              <strong>Right to rectification:</strong> to have outdated, false, or misleading data corrected promptly.
            </li>
            <li>
              <strong>Right to erasure (deletion):</strong> to request deletion of your data where there are no
              overriding legal grounds to keep it.
            </li>
            <li>
              <strong>Right to object and restrict:</strong> to decline direct marketing, object to automated
              profiling, or pause processing while a dispute is resolved.
            </li>
          </ul>
        </section>

        <section>
          <h2 className="font-semibold text-base mb-2">7. Data security</h2>
          <p>
            Ekshop applies technical and organizational measures to reduce risks to your data. Passwords are protected
            with cryptographic hashing, data in transit is encrypted with SSL/TLS, and access within our cloud
            infrastructure follows least-privilege standards. No platform can promise absolute security, so we
            encourage you to use a strong password and keep your login details confidential.
          </p>
        </section>

        <section>
          <h2 className="font-semibold text-base mb-2">8. International data transfers</h2>
          <p>
            Because the Platform uses global cloud servers, your information may sometimes be processed or stored
            outside Kenya. Ekshop ensures that such processing complies with Section 41 of the Data Protection Act,
            2019. We only transfer data to jurisdictions with comparable data protection laws, or under standard
            contractual clauses that commit to equivalent protection for your personal data.
          </p>
        </section>

        <section>
          <h2 className="font-semibold text-base mb-2">9. Changes to this policy</h2>
          <p>
            We may update this Privacy Policy to reflect new technical capabilities or changes in compliance
            requirements. Material changes will be announced on the Platform or sent to your registered email address
            before they take effect. The date at the top of this page shows when the current version took effect.
          </p>
        </section>

        <section>
          <h2 className="font-semibold text-base mb-2">10. Contact and grievances</h2>
          <p>
            If you have questions, want to exercise a data right, or wish to raise a concern about how we handle your
            information, contact our privacy desk:
          </p>
          <p className="mt-2">
            Ekshop Data Privacy Desk
            <br />
            Email: <span className="text-muted">supportteam@ekshop.store</span>
            <br />
            Nairobi, Kenya
          </p>
          <p className="mt-2">
            If your inquiry is not handled to your satisfaction, you may escalate your complaint to the Office of the
            Data Protection Commissioner (ODPC) of Kenya.
          </p>
        </section>
      </div>
    </div>
  );
}
