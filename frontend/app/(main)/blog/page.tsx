import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Ekshop Blog",
  description: "News and stories from Ekshop.",
};

export default function BlogPage() {
  return (
    <div className="w-full max-w-3xl mx-auto px-4 md:px-6 py-16 text-center">
      <h1 className="text-2xl font-bold mb-2">Ekshop Blog</h1>
      <p className="text-sm text-muted">
        We&apos;re working on our first posts. Check back soon for news, seller stories, and shopping guides.
      </p>
    </div>
  );
}
