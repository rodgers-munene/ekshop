import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Careers at Ekshop",
  description: "Open roles at Ekshop.",
};

export default function CareersPage() {
  return (
    <div className="w-full max-w-3xl mx-auto px-4 md:px-6 py-10">
      <h1 className="text-2xl font-bold mb-2">Careers</h1>
      <p className="text-xs text-muted mb-8">Join the team building Ekshop</p>

      <div className="space-y-4 text-sm leading-relaxed text-ink">
        <p>
          We&apos;re not hiring for any open roles right now, but we&apos;re growing fast and that could change soon.
          Check back here for updates.
        </p>
        <p>
          In the meantime, if you think you&apos;d be a great fit for Ekshop, feel free to reach out at{" "}
          <span className="text-muted">careers@ekshop.co.ke</span>.
        </p>
      </div>
    </div>
  );
}
