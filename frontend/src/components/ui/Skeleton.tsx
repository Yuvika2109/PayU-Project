import { cn } from '@/lib/utils';

interface SkeletonProps {
  className?: string;
}

export function Skeleton({ className }: SkeletonProps) {
  return (
    <div
      className={cn('shimmer rounded-md', className)}
      style={{ minHeight: '16px' }}
    />
  );
}

export function RuleCardSkeleton() {
  return (
    <div className="card p-5 space-y-3 animate-fade-in">
      <div className="flex items-start gap-3">
        <Skeleton className="w-5 h-5 rounded flex-shrink-0 mt-0.5" />
        <div className="flex-1 space-y-2">
          <div className="flex items-center gap-2">
            <Skeleton className="h-5 w-16 rounded-full" />
            <Skeleton className="h-5 w-24" />
          </div>
          <Skeleton className="h-4 w-3/4" />
          <Skeleton className="h-4 w-1/2" />
        </div>
      </div>
      <div className="flex gap-2 pl-8">
        <Skeleton className="h-5 w-16 rounded" />
        <Skeleton className="h-5 w-20 rounded" />
        <Skeleton className="h-5 w-14 rounded" />
      </div>
    </div>
  );
}

export function MetricSkeleton() {
  return (
    <div className="metric-card space-y-2 animate-fade-in">
      <Skeleton className="h-3 w-24" />
      <Skeleton className="h-8 w-20" />
      <Skeleton className="h-3 w-32" />
    </div>
  );
}
