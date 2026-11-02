'use client';

/**
 * PersonCardSkeleton — loading placeholder that matches PersonCard dimensions.
 * Uses the same animate-pulse pattern from CareerMatchingPage.
 */

export default function PersonCardSkeleton() {
  return (
    <div
      aria-hidden="true"
      data-testid="person-card-skeleton"
      className="flex flex-col overflow-hidden rounded-[var(--radius-card)] border border-[var(--border)] bg-[var(--surface)] shadow-[var(--shadow-card)]"
    >
      <div className="p-5 flex flex-col gap-4">
        {/* Avatar + name row */}
        <div className="flex items-start gap-4">
          {/* Avatar */}
          <div className="h-16 w-16 flex-shrink-0 animate-pulse rounded-2xl bg-[var(--surface-subtle)]" />
          {/* Name lines */}
          <div className="flex-1 space-y-2 pt-1">
            <div className="h-4 w-32 animate-pulse rounded-lg bg-[var(--surface-subtle)]" />
            <div className="h-3 w-20 animate-pulse rounded-lg bg-[var(--surface-subtle)]" />
            <div className="h-3 w-44 animate-pulse rounded-lg bg-[var(--surface-subtle)]" />
            <div className="h-3 w-36 animate-pulse rounded-lg bg-[var(--surface-subtle)]" />
          </div>
        </div>

        {/* Location */}
        <div className="h-3 w-28 animate-pulse rounded-lg bg-[var(--surface-subtle)]" />

        {/* Buttons row */}
        <div className="flex items-center gap-2 border-t border-[var(--border)] pt-4">
          <div className="h-8 flex-1 animate-pulse rounded-lg bg-[var(--surface-subtle)]" />
          <div className="h-8 w-24 animate-pulse rounded-lg bg-[var(--surface-subtle)]" />
        </div>
      </div>
    </div>
  );
}
