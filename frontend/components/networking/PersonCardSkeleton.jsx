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
      className="flex flex-col rounded-[1.75rem] border border-white/10 bg-white/[0.04] backdrop-blur-xl shadow-glow overflow-hidden"
    >
      <div className="p-5 flex flex-col gap-4">
        {/* Avatar + name row */}
        <div className="flex items-start gap-4">
          {/* Avatar */}
          <div className="h-16 w-16 rounded-2xl bg-white/5 animate-pulse flex-shrink-0" />
          {/* Name lines */}
          <div className="flex-1 space-y-2 pt-1">
            <div className="h-4 w-32 rounded-lg bg-white/5 animate-pulse" />
            <div className="h-3 w-20 rounded-lg bg-white/5 animate-pulse" />
            <div className="h-3 w-44 rounded-lg bg-white/5 animate-pulse" />
            <div className="h-3 w-36 rounded-lg bg-white/5 animate-pulse" />
          </div>
        </div>

        {/* Location */}
        <div className="h-3 w-28 rounded-lg bg-white/5 animate-pulse" />

        {/* Buttons row */}
        <div className="flex items-center gap-2 pt-1 border-t border-white/8">
          <div className="flex-1 h-8 rounded-full bg-white/5 animate-pulse" />
          <div className="h-8 w-24 rounded-full bg-white/5 animate-pulse" />
        </div>
      </div>
    </div>
  );
}
