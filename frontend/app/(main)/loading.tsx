export default function HomeLoading() {
  return (
    <div className="w-full">
      {/* Hero skeleton */}
      <section className="bg-navy min-h-[280px] flex items-center px-6 md:px-12">
        <div className="space-y-4 max-w-md">
          <div className="h-3 w-32 bg-white/10 rounded animate-pulse" />
          <div className="h-10 w-3/4 bg-white/10 rounded animate-pulse" />
          <div className="h-10 w-2/3 bg-white/10 rounded animate-pulse" />
          <div className="h-4 w-48 bg-white/10 rounded animate-pulse" />
          <div className="h-10 w-32 bg-white/10 rounded animate-pulse" />
        </div>
      </section>

      {/* Quick-link card row skeleton */}
      <div className="px-4 md:px-6 -mt-10 relative z-10">
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
          {Array.from({ length: 4 }).map((_, i) => (
            <div key={i} className="card p-4 space-y-2">
              <div className="h-4 w-2/3 bg-ink/10 rounded animate-pulse" />
              <div className="grid grid-cols-2 gap-1.5">
                {Array.from({ length: 4 }).map((_, j) => (
                  <div key={j} className="aspect-square bg-ink/10 rounded animate-pulse" />
                ))}
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Rail skeleton */}
      <section className="px-4 md:px-6 py-4">
        <div className="card p-5">
          <div className="h-6 w-40 bg-ink/10 rounded animate-pulse mb-5" />
          <div className="grid grid-cols-3 sm:grid-cols-4 lg:grid-cols-5 xl:grid-cols-6 gap-3">
            {Array.from({ length: 12 }).map((_, i) => (
              <div key={i} className="rounded-lg overflow-hidden border border-border">
                <div className="aspect-square bg-ink/10 animate-pulse" />
                <div className="p-2 space-y-1.5">
                  <div className="h-3 bg-ink/10 rounded animate-pulse" />
                  <div className="h-3 w-2/3 bg-ink/10 rounded animate-pulse" />
                </div>
              </div>
            ))}
          </div>
        </div>
      </section>
    </div>
  );
}
