import Link from "next/link";
import { SELLER_PLANS } from "@/lib/plans";

export default function ChoosePlanPage() {
  return (
    <div className="min-h-screen">
      <div className="max-w-4xl mx-auto px-6 py-16">
        <div className="text-center mb-12">
          <span className="text-2xl font-bold">
            EK<span className="text-amber">SHOP</span>
          </span>
          <h1 className="text-3xl sm:text-4xl font-bold mt-6 mb-3">Choose your seller plan</h1>
          <p className="text-muted">
            Pick the package that fits your shop. You&apos;ll enter your details and pay next.
          </p>
        </div>

        <div className="grid sm:grid-cols-2 gap-6">
          {SELLER_PLANS.map((plan) => (
            <div
              key={plan.code}
              className={`card p-8 flex flex-col ${plan.highlight ? "ring-2 ring-amber" : ""}`}
            >
              {plan.highlight && (
                <span className="self-start text-xs font-semibold uppercase tracking-wide text-amber mb-3">
                  Most popular
                </span>
              )}
              <h2 className="text-xl font-bold mb-1">{plan.name}</h2>
              <p className="text-muted text-sm mb-4">{plan.tagline}</p>
              <p className="mb-6">
                <span className="text-3xl font-bold">KES {plan.price.toLocaleString()}</span>
                <span className="text-muted text-sm"> /month</span>
              </p>
              <ul className="space-y-2 mb-8 flex-1">
                {plan.features.map((feature) => (
                  <li key={feature} className="flex items-start gap-2 text-sm">
                    <span className="text-amber mt-0.5">✓</span>
                    <span>{feature}</span>
                  </li>
                ))}
              </ul>
              <Link
                href={`/register?role=seller&plan=${plan.code}`}
                className="btn-accent text-center"
              >
                Get started
              </Link>
            </div>
          ))}
        </div>

        <p className="text-center text-sm text-muted mt-10">
          Already have an account?{" "}
          <Link href="/login" className="text-amber underline underline-offset-2">Sign in</Link>
        </p>
      </div>
    </div>
  );
}
