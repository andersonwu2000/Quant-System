interface SkeletonProps {
  className?: string;
}

export function Skeleton({ className = "" }: SkeletonProps) {
  return (
    <div className={`animate-pulse bg-slate-200 dark:bg-surface-light/50 rounded ${className}`} />
  );
}

export function MetricCardSkeleton() {
  return (
    <div className="bg-slate-50 dark:bg-surface rounded-xl p-5 space-y-2 border border-slate-200 dark:border-transparent shadow-sm dark:shadow-none">
      <Skeleton className="h-4 w-20" />
      <Skeleton className="h-6 w-32" />
    </div>
  );
}

export function PageSkeleton() {
  return (
    <div className="space-y-4 animate-pulse">
      <Skeleton className="h-7 w-52" />
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        {Array.from({ length: 4 }).map((_, i) => (
          <MetricCardSkeleton key={i} />
        ))}
      </div>
      <Skeleton className="h-64 rounded-xl" />
      <Skeleton className="h-40 rounded-xl" />
    </div>
  );
}

export function TableSkeleton({ rows = 5, cols = 4 }: { rows?: number; cols?: number }) {
  return (
    <div className="bg-slate-50 dark:bg-surface rounded-xl p-5 space-y-3 border border-slate-200 dark:border-transparent shadow-sm dark:shadow-none">
      <div className="flex gap-4 border-b border-slate-200 dark:border-surface-light pb-3">
        {Array.from({ length: cols }).map((_, i) => (
          <Skeleton key={i} className="h-4 flex-1" />
        ))}
      </div>
      {Array.from({ length: rows }).map((_, i) => (
        <div key={i} className="flex gap-4">
          {Array.from({ length: cols }).map((_, j) => (
            <Skeleton key={j} className="h-4 flex-1" />
          ))}
        </div>
      ))}
    </div>
  );
}
