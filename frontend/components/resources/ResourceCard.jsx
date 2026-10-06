'use client';

import React from 'react';
import Link from 'next/link';
import { Bookmark, BookmarkCheck, ExternalLink, Pencil, Share2, Trash2 } from 'lucide-react';
import ProfileAvatar from '@/components/common/ProfileAvatar';
import { categoryLabel, resourceTypeLabel } from '@/components/resources/resourceConstants';

function formatDate(value) {
  if (!value) return 'Recently';
  try {
    return new Intl.DateTimeFormat(undefined, { month: 'short', day: 'numeric', year: 'numeric' }).format(new Date(value));
  } catch {
    return 'Recently';
  }
}

export function ResourceCardSkeleton() {
  return (
    <div className="min-h-[260px] animate-pulse rounded-3xl border border-white/10 bg-white/[0.035] p-5">
      <div className="mb-4 h-6 w-28 rounded-full bg-white/10" />
      <div className="h-6 w-3/4 rounded bg-white/10" />
      <div className="mt-3 h-4 w-full rounded bg-white/10" />
      <div className="mt-2 h-4 w-5/6 rounded bg-white/10" />
      <div className="mt-6 flex gap-2">
        <div className="h-7 w-16 rounded-full bg-white/10" />
        <div className="h-7 w-20 rounded-full bg-white/10" />
      </div>
    </div>
  );
}

export default function ResourceCard({
  resource,
  busy = false,
  onSave,
  onUnsave,
  onShare,
  onEdit,
  onDelete,
}) {
  const authorName = resource.author
    ? `${resource.author.first_name || ''} ${resource.author.last_name || ''}`.trim() || resource.author.username
    : 'CareerSphere member';
  const saveLabel = resource.is_saved ? 'Unsave resource' : 'Save resource';

  return (
    <article className="flex h-full flex-col rounded-3xl border border-white/10 bg-white/[0.04] p-5 shadow-[0_16px_50px_rgba(0,0,0,0.25)] transition-transform hover:-translate-y-0.5 hover:border-accent/25">
      <div className="mb-4 flex items-start justify-between gap-3">
        <div>
          <span className="inline-flex rounded-full border border-accent/25 bg-accent/10 px-3 py-1 text-xs font-bold uppercase tracking-[0.16em] text-accent">
            {resourceTypeLabel(resource.resource_type)}
          </span>
          <p className="mt-2 text-xs text-slate-500">{categoryLabel(resource.category)}</p>
        </div>
        <button
          type="button"
          onClick={() => (resource.is_saved ? onUnsave?.(resource) : onSave?.(resource))}
          disabled={busy}
          aria-label={saveLabel}
          className={`rounded-full border p-2 transition-colors disabled:opacity-60 ${
            resource.is_saved
              ? 'border-accent/30 bg-accent/15 text-accent'
              : 'border-white/10 text-slate-300 hover:border-accent/30 hover:text-accent'
          }`}
        >
          {resource.is_saved ? <BookmarkCheck className="h-4 w-4" /> : <Bookmark className="h-4 w-4" />}
        </button>
      </div>

      <Link href={`/dashboard/resources/${resource.id}`} className="group">
        <h2 className="line-clamp-2 text-lg font-bold leading-snug text-white group-hover:text-accent">
          {resource.title}
        </h2>
      </Link>
      <p className="mt-3 line-clamp-3 min-h-[4.5rem] text-sm leading-relaxed text-slate-400">
        {resource.description || 'No description provided yet.'}
      </p>

      <div className="mt-4 flex flex-wrap gap-2">
        {(resource.tags || []).slice(0, 4).map((tag) => (
          <span key={tag.toLowerCase()} className="rounded-full border border-white/10 bg-white/[0.04] px-2.5 py-1 text-xs text-slate-300">
            #{tag}
          </span>
        ))}
      </div>

      <div className="mt-5 flex items-center gap-3 border-t border-white/10 pt-4">
        <ProfileAvatar
          src={resource.author?.profile_photo_url}
          name={authorName}
          username={resource.author?.username}
          alt={authorName}
          fallback={(authorName?.[0] || 'R').toUpperCase()}
          className="h-9 w-9"
        />
        <div className="min-w-0 flex-1">
          <p className="truncate text-sm font-semibold text-white">{authorName}</p>
          <p className="text-xs text-slate-500">{formatDate(resource.created_at)}</p>
        </div>
      </div>

      <div className="mt-5 flex flex-wrap gap-2">
        <a
          href={resource.url}
          target="_blank"
          rel="noopener noreferrer"
          className="inline-flex flex-1 items-center justify-center gap-2 rounded-full bg-accent px-4 py-2 text-sm font-semibold text-black hover:bg-accentSoft"
        >
          <ExternalLink className="h-4 w-4" />
          Open
        </a>
        <button
          type="button"
          onClick={() => onShare?.(resource)}
          className="inline-flex flex-1 items-center justify-center gap-2 rounded-full border border-white/10 px-4 py-2 text-sm font-semibold text-slate-200 hover:border-accent/30 hover:text-accent"
        >
          <Share2 className="h-4 w-4" />
          Share
        </button>
        <Link
          href={`/dashboard/resources/${resource.id}`}
          className="inline-flex flex-1 items-center justify-center rounded-full border border-white/10 px-4 py-2 text-sm font-semibold text-slate-200 hover:border-accent/30 hover:text-accent"
        >
          View
        </Link>
        {resource.is_owner && (
          <>
            <button
              type="button"
              onClick={() => onEdit?.(resource)}
              className="inline-flex items-center justify-center rounded-full border border-white/10 p-2 text-slate-300 hover:text-accent"
              aria-label="Edit resource"
            >
              <Pencil className="h-4 w-4" />
            </button>
            <button
              type="button"
              onClick={() => onDelete?.(resource)}
              className="inline-flex items-center justify-center rounded-full border border-rose-500/20 p-2 text-rose-200 hover:bg-rose-500/10"
              aria-label="Delete resource"
            >
              <Trash2 className="h-4 w-4" />
            </button>
          </>
        )}
      </div>

      <p className="mt-3 truncate text-xs text-slate-500">{resource.source_domain || resource.url}</p>
    </article>
  );
}
