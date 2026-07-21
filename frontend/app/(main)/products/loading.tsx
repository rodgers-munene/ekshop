export default function ProductsLoading() {
  return (
    <div className="w-full px-4 md:px-6 py-4">
      {/* Header skeleton */}
      <div className="card px-4 md:px-6 py-5 mb-4">
        <div className="h-7 w-48 bg-ink/10 rounded animate-pulse" />
      </div>

      <div className="flex gap-4">
        {/* Sidebar skeleton */}
        <aside className="hidden md:block w-56 shrink-0 card p-4">
          <div className="h-3 w-24 bg-ink/10 rounded animate-pulse mb-4" />
          <div className="space-y-3">
            {Array.from({ length: 8 }).map((_, i) => (
              <div key={i} className="h-4 bg-ink/10 rounded animate-pulse" style={{ width: `${60 + (i % 3) * 15}%` }} />
            ))}
          </div>
        </aside>

        {/* Grid skeleton */}
        <div className="flex-1">
          <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-4">
            {Array.from({ length: 16 }).map((_, i) => (
              <div key={i} className="card overflow-hidden">
                <div className="aspect-square bg-ink/10 animate-pulse" />
                <div className="p-3 space-y-2">
                  <div className="h-3 w-2/3 bg-ink/10 rounded animate-pulse" />
                  <div className="h-4 bg-ink/10 rounded animate-pulse" />
                  <div className="h-4 w-1/2 bg-ink/10 rounded animate-pulse" />
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
