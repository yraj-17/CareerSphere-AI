'use client';

import React from 'react';
import Link from 'next/link';
import { Check, Loader2, Tag, Users } from 'lucide-react';
import { CATEGORY_LABELS } from '@/components/communities/communityConstants';

function getInitials(name = 'Community') {
  return name
    .split(' ')
    .filter(Boolean)
    .slice(0, 2)
    .map((part) => part[0])
    .join('')
    .toUpperCase() || 'CS';
}

function formatMembers(count) {
  if (typeof count !== 'number') return 'Members unavailable';
  return `${count.toLocaleString()} ${count === 1 ? 'member' : 'members'}`;
}

export default function CommunityCard({
  community,
  onJoin,
  onLeave,
  busy = false,
  disabled = false,
}) {
  const id = community?.id ?? community?.community_id;
  const name = community?.name || 'Untitled community';
  const joined = !!(community?.joined || community?.is_joined || community?.membership_status === 'joined');
  const category = community?.category_label || CATEGORY_LABELS[community?.category] || community?.category || 'Other';
  const tags = Array.isArray(community?.tags) ? community.tags.slice(0, 3) : [];

  return (
    <article className="group flex h-full flex-col overflow-hidden rounded-xl border border-slate-200 bg-white shadow-sm transition-all hover:border-brand-200 hover:shadow-md">
      <Link
        href={`/dashboard/communities/${id}`}
        className="block focus:outline-none focus-visible:ring-2 focus-visible:ring-brand-500 focus-visible:ring-offset-2"
        aria-label={`View ${name}`}
      >
        <div className="relative aspect-[16/9] overflow-hidden bg-brand-50">
          {community?.image_url ? (
            <div
              className="h-full w-full bg-cover bg-center"
              style={{ backgroundImage: `url(${community.image_url})` }}
              aria-hidden="true"
            />
          ) : (
            <div className="flex h-full w-full items-center justify-center bg-brand-50">
              <div className="flex h-14 w-14 items-center justify-center rounded-xl border border-brand-200 bg-white text-sm font-bold text-brand-600 shadow-sm">
                {getInitials(name)}
              </div>
            </div>
          )}
        </div>
      </Link>

      <div className="flex flex-1 flex-col gap-4 p-4 sm:p-5">
        <div className="space-y-2">
          <div className="flex items-start justify-between gap-3">
            <Link
              href={`/dashboard/communities/${id}`}
              className="line-clamp-2 text-base font-semibold text-slate-900 transition-colors hover:text-brand-600 focus:outline-none focus-visible:ring-2 focus-visible:ring-brand-500 focus-visible:ring-offset-2"
            >
              {name}
            </Link>
            <span className="shrink-0 rounded-lg border border-brand-100 bg-brand-50 px-2.5 py-1 text-[11px] font-semibold text-brand-600">
              {category}
            </span>
          </div>
          <p className="line-clamp-3 min-h-[3.75rem] text-sm leading-relaxed text-slate-600">
            {community?.description || 'Community description will appear here once provided.'}
          </p>
        </div>

        <div className="space-y-2 text-xs text-slate-500">
          <div className="flex items-center gap-2">
            <Users className="h-4 w-4 text-slate-400" aria-hidden="true" />
            {formatMembers(community?.member_count)}
          </div>
          {tags.length > 0 && (
            <div className="flex items-center gap-2">
              <Tag className="h-4 w-4 text-slate-400" aria-hidden="true" />
              <div className="flex min-w-0 flex-wrap gap-1.5">
                {tags.map((tag) => (
                  <span key={tag} className="rounded-md bg-slate-100 px-2 py-0.5 text-[11px] text-slate-600">
                    {tag}
                  </span>
                ))}
              </div>
            </div>
          )}
        </div>

        <div className="mt-auto">
          {joined ? (
            <button
              type="button"
              onClick={() => onLeave?.(community)}
              disabled={busy || disabled}
              aria-busy={busy}
              className="flex w-full items-center justify-center gap-2 rounded-lg border border-emerald-200 bg-emerald-50 px-4 py-2.5 text-sm font-semibold text-emerald-700 transition-colors hover:bg-emerald-100 disabled:cursor-not-allowed disabled:opacity-60 focus:outline-none focus-visible:ring-2 focus-visible:ring-emerald-500 focus-visible:ring-offset-2"
            >
              {busy ? <Loader2 className="h-4 w-4 animate-spin" /> : <Check className="h-4 w-4" />}
              Joined
            </button>
          ) : (
            <button
              type="button"
              onClick={() => onJoin?.(community)}
              disabled={busy || disabled}
              aria-busy={busy}
              className="flex w-full items-center justify-center gap-2 rounded-lg bg-brand-500 px-4 py-2.5 text-sm font-semibold text-white shadow-sm transition-colors hover:bg-brand-600 disabled:cursor-not-allowed disabled:opacity-60 focus:outline-none focus-visible:ring-2 focus-visible:ring-brand-500 focus-visible:ring-offset-2"
            >
              {busy ? <Loader2 className="h-4 w-4 animate-spin" /> : null}
              Join Community
            </button>
          )}
        </div>
      </div>
    </article>
  );
}

export function CommunityCardSkeleton() {
  return (
    <div data-testid="community-card-skeleton" className="overflow-hidden rounded-xl border border-slate-200 bg-white shadow-sm">
      <div className="aspect-[16/9] animate-pulse bg-slate-100" />
      <div className="space-y-4 p-5">
        <div className="h-4 w-2/3 animate-pulse rounded bg-slate-100" />
        <div className="space-y-2">
          <div className="h-3 w-full animate-pulse rounded bg-slate-100" />
          <div className="h-3 w-4/5 animate-pulse rounded bg-slate-100" />
        </div>
        <div className="h-10 w-full animate-pulse rounded-lg bg-slate-100" />
      </div>
    </div>
  );
}
