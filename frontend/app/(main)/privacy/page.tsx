import type { Metadata } from "next";
import Link from "next/link";

export const metadata: Metadata = {
  title: "Privacy Policy",
  description: "How Ekshop collects, uses, and protects your data.",
};

export default function PrivacyPage() {
  return (
    <div className="w-full max-w-3xl mx-auto px-4 md:px-6 py-10">
      <h1 className="text-2xl font-bold mb-2">Privacy Policy</h1>
      <p className="text-xs text-muted mb-8">Last updated: {new Date().toLocaleDateString("en-KE", { day: "numeric", month: "long", year: "numeric" })}</p>

      <div className="space-y-6 text-sm leading-relaxed text-ink">
        <section>
          <h2 className="font-semibold text-base mb-2">1. Information we collect</h2>
          <ul className="list-disc pl-5 space-y-1">
            <li><strong>Account information:</strong> name, email, phone number, county, and password.</li>
            <li><strong>Order information:</strong> delivery addresses, order history, and communications with Sellers.</li>
            <li><strong>Payment information:</strong> processed directly by Paystack. Ekshop does not store your card details.</li>
            <li><strong>Usage data:</strong> pages viewed, products clicked, searches made, and similar activity, used to
              personalise recommendations and improve the platform.</li>
          </ul>
        </section>

        <section>
          <h2 className="font-semibold text-base mb-2">2. How we use your information</h2>
          <p>We use your information to:</p>
          <ul className="list-disc pl-5 space-y-1">
            <li>Process orders, payments, and deliveries</li>
            <li>Verify your identity and secure your account</li>
            <li>Communicate order updates, security alerts, and (if opted in) promotional offers</li>
            <li>Personalise product recommendations and search results</li>
            <li>Detect and prevent fraud, abuse, and platform violations</li>
          </ul>
        </section>

        <section>
          <h2 className="font-semibold text-base mb-2">3. Who we share it with</h2>
          <p>
            We share the minimum necessary information with: Sellers (to fulfil your orders), Paystack (to process
            payments), delivery partners (to deliver your orders), and service providers who help us operate the
            platform (such as email and cloud hosting providers). We do not sell your personal information to third
            parties.
          </p>
        </section>

        <section>
          <h2 className="font-semibold text-base mb-2">4. Cookies</h2>
          <p>
            Ekshop uses essential cookies to keep you signed in and to remember your cart. We may use additional
            cookies to understand platform usage and improve performance.
          </p>
        </section>

        <section>
          <h2 className="font-semibold text-base mb-2">5. Data retention</h2>
          <p>
            We retain your account and order information for as long as your account is active and as needed to
            comply with legal, tax, and accounting obligations.
          </p>
        </section>

        <section>
          <h2 className="font-semibold text-base mb-2">6. Your rights</h2>
          <p>
            You can access, update, or delete your account information from your{" "}
            <Link href="/account" className="text-amber underline underline-offset-2">account settings</Link>, or by
            contacting us. Under Kenya&apos;s Data Protection Act, 2019, you have the right to access, correct, and
            request deletion of your personal data, and to object to certain processing.
          </p>
        </section>

        <section>
          <h2 className="font-semibold text-base mb-2">7. Security</h2>
          <p>
            We use industry-standard measures, including password hashing, encrypted connections, and access
            controls, to protect your data. No system is completely secure, and we encourage you to use a strong,
            unique password.
          </p>
        </section>

        <section>
          <h2 className="font-semibold text-base mb-2">8. Changes to this policy</h2>
          <p>We may update this policy from time to time. Material changes will be communicated via the platform or email.</p>
        </section>

        <section>
          <h2 className="font-semibold text-base mb-2">9. Contact</h2>
          <p>For privacy questions or data requests, contact <span className="text-muted">privacy@ekshop.co.ke</span>.</p>
        </section>
      </div>
    </div>
  );
}
