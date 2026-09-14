"use client";

import { useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Star, Loader2 } from "lucide-react";
import Link from "next/link";
import { toast } from "sonner";
import { Review } from "@/types/interface";
import { useAuthStore } from "@/store/authStore";

function Stars({ value, size = 14 }: { value: number; size?: number }) {
  return (
    <div className="flex items-center text-amber">
      {Array.from({ length: 5 }).map((_, i) => (
        <Star key={i} size={size} className={i < value ? "fill-current" : "fill-none"} />
      ))}
    </div>
  );
}

export default function ProductReviews({ productId }: { productId: string }) {
  const { user, isAuthenticated } = useAuthStore();
  const queryClient = useQueryClient();
  const [rating, setRating] = useState(5);
  const [hover, setHover] = useState(0);
  const [body, setBody] = useState("");
  const [submitting, setSubmitting] = useState(false);

  const { data: reviews = [], isPending: loading } = useQuery<Review[]>({
    queryKey: ["reviews", productId],
    queryFn: () =>
      fetch(`/api/products/${productId}/reviews`)
        .then((r) => r.json())
        .then((data) => (Array.isArray(data) ? data : [])),
  });

  async function submitReview(e: React.FormEvent) {
    e.preventDefault();
    if (!rating) return;
    setSubmitting(true);
    try {
      const res = await fetch(`/api/products/${productId}/reviews`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ rating, body: body.trim() || null }),
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) {
        toast.error(data.detail ?? "Could not submit review");
        return;
      }
      toast.success("Thanks for your review!");
      setBody("");
      await queryClient.invalidateQueries({ queryKey: ["reviews", productId] });
    } catch {
      toast.error("Something went wrong. Please try again.");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <section className="card p-6 md:p-8">
      <div className="flex items-center justify-between mb-6">
        <h2 className="text-xl font-bold">Ratings & Reviews</h2>
        <span className="text-sm text-muted">
          {reviews.length} {reviews.length === 1 ? "review" : "reviews"}
        </span>
      </div>

      {/* Review form — logged-in buyers only */}
      {isAuthenticated && user ? (
        <form onSubmit={submitReview} className="border border-border rounded-lg p-4 mb-6 bg-surface/50">
          <p className="text-sm font-semibold mb-2">Rate this product</p>
          <div className="flex items-center gap-1 mb-3" onMouseLeave={() => setHover(0)}>
            {Array.from({ length: 5 }).map((_, i) => (
              <button
                key={i}
                type="button"
                aria-label={`${i + 1} star${i ? "s" : ""}`}
                onMouseEnter={() => setHover(i + 1)}
                onClick={() => setRating(i + 1)}
                className="p-0.5"
              >
                <Star
                  size={22}
                  className={`transition-colors ${
                    i < (hover || rating) ? "fill-current text-amber" : "fill-none text-muted"
                  }`}
                />
              </button>
            ))}
          </div>
          <textarea
            value={body}
            onChange={(e) => setBody(e.target.value)}
            placeholder="What did you like (or not)?"
            rows={3}
            className="input-field resize-none mb-3"
          />
          <button
            type="submit"
            disabled={submitting}
            className="btn-accent text-sm disabled:opacity-50"
          >
            {submitting ? <Loader2 size={15} className="animate-spin" /> : null}
            {submitting ? "Submitting…" : "Submit review"}
          </button>
        </form>
      ) : (
        <div className="border border-dashed border-border rounded-lg p-4 mb-6 text-center">
          <p className="text-sm text-muted mb-2">
            <Link href="/login" className="text-amber underline underline-offset-2">
              Sign in
            </Link>{" "}
            to rate this product.
          </p>
        </div>
      )}

      {/* Review list */}
      {loading ? (
        <div className="space-y-3">
          {Array.from({ length: 3 }).map((_, i) => (
            <div key={i} className="h-16 bg-ink/5 rounded animate-pulse" />
          ))}
        </div>
      ) : reviews.length === 0 ? (
        <p className="text-sm text-muted text-center py-8">
          No reviews yet&mdash;be the first to share your thoughts.
        </p>
      ) : (
        <div className="divide-y divide-border">
          {reviews.map((review) => (
            <div key={review.id} className="py-4">
              <div className="flex items-center justify-between mb-1.5">
                <div className="flex items-center gap-2">
                  <Stars value={review.rating} />
                  <span className="text-xs text-muted">
                    {new Date(review.created_at).toLocaleDateString("en-KE", {
                      year: "numeric",
                      month: "short",
                      day: "numeric",
                    })}
                  </span>
                </div>
                <span className="text-xs text-muted font-medium">Verified Buyer</span>
              </div>
              {review.body && <p className="text-sm leading-relaxed">{review.body}</p>}
            </div>
          ))}
        </div>
      )}
    </section>
  );
}