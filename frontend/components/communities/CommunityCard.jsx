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
    <article className="group flex h-full flex-col overflow-hidden rounded-2xl border border-white/10 bg-white/[0.045] shadow-[0_18px_45px_rgba(0,0,0,0.22)] backdrop-blur-xl transition-all hover:border-accent/25 hover:bg-white/[0.065]">
      <Link
        href={`/dashboard/communities/${id}`}
        className="block focus:outline-none focus-visible:ring-2 focus-visible:ring-accent/70"
        aria-label={`View ${name}`}
      >
        <div className="relative h-28 overflow-hidden bg-slate-900">
          {community?.image_url ? (
            <div
              className="h-full w-full bg-cover bg-center opacity-85"
              style={{ backgroundImage: `url(${community.image_url})` }}
              aria-hidden="true"
            />
          ) : (
            <div className="flex h-full w-full items-center justify-center bg-[radial-gradient(circle_at_30%_0%,rgba(255,143,50,0.20),transparent_48%),linear-gradient(135deg,rgba(15,23,42,0.95),rgba(2,6,23,0.95))]">
              <div className="flex h-14 w-14 items-center justify-center rounded-2xl border border-accent/30 bg-accent/15 text-sm font-bold text-accent">
                {getInitials(name)}
              </div>
            </div>
          )}
        </div>
      </Link>

      <div className="flex flex-1 flex-col gap-4 p-5">
        <div className="space-y-2">
          <div className="flex items-start justify-between gap-3">
            <Link
              href={`/dashboard/communities/${id}`}
              className="line-clamp-2 text-base font-bold text-white transition-colors hover:text-accent focus:outline-none focus-visible:ring-2 focus-visible:ring-accent/70"
            >
              {name}
            </Link>
            <span className="shrink-0 rounded-full border border-accent/25 bg-accent/10 px-2.5 py-1 text-[11px] font-semibold text-accent">
              {category}
            </span>
          </div>
          <p className="line-clamp-3 min-h-[3.75rem] text-sm leading-relaxed text-slate-400">
            {community?.description || 'Community description will appear here once provided.'}
          </p>
        </div>

        <div className="space-y-2 text-xs text-slate-400">
          <div className="flex items-center gap-2">
            <Users className="h-4 w-4 text-slate-500" aria-hidden="true" />
            {formatMembers(community?.member_count)}
          </div>
          {tags.length > 0 && (
            <div className="flex items-center gap-2">
              <Tag className="h-4 w-4 text-slate-500" aria-hidden="true" />
              <div className="flex min-w-0 flex-wrap gap-1.5">
                {tags.map((tag) => (
                  <span key={tag} className="rounded-full bg-white/[0.06] px-2 py-0.5 text-[11px] text-slate-300">
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
              className="flex w-full items-center justify-center gap-2 rounded-full border border-emerald-500/25 bg-emerald-500/10 px-4 py-2.5 text-sm font-semibold text-emerald-200 transition-colors hover:bg-emerald-500/15 disabled:cursor-not-allowed disabled:opacity-60 focus:outline-none focus-visible:ring-2 focus-visible:ring-emerald-400/70"
            >
              {busy ? <Loader2 className="h-4 w-4 animate-spin" /> : <Check className="h-4 w-4" />}
              Joined
            </button>
          ) : (
            <button
              type="button"
              onClick={() => onJoin?.(community)}
              disabled={busy || disabled}
              className="flex w-full items-center justify-center gap-2 rounded-full bg-accent px-4 py-2.5 text-sm font-semibold text-black shadow-[0_8px_30px_rgba(255,143,50,0.28)] transition-colors hover:bg-accentSoft disabled:cursor-not-allowed disabled:opacity-60 focus:outline-none focus-visible:ring-2 focus-visible:ring-accent/70"
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
    <div data-testid="community-card-skeleton" className="overflow-hidden rounded-2xl border border-white/10 bg-white/[0.045]">
      <div className="h-28 animate-pulse bg-white/[0.06]" />
      <div className="space-y-4 p-5">
        <div className="h-4 w-2/3 animate-pulse rounded bg-white/[0.08]" />
        <div className="space-y-2">
          <div className="h-3 w-full animate-pulse rounded bg-white/[0.06]" />
          <div className="h-3 w-4/5 animate-pulse rounded bg-white/[0.06]" />
        </div>
        <div className="h-9 w-full animate-pulse rounded-full bg-white/[0.08]" />
      </div>
    </div>
  );
}
