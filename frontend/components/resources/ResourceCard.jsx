'use client';

import React from 'react';
import Link from 'next/link';
import {
  BookMarked,
  BookOpen,
  Bookmark,
  BookmarkCheck,
  Code2,
  ExternalLink,
  FileText,
  Github,
  GraduationCap,
  FileStack,
  Pencil,
  PlaySquare,
  Share2,
  Trash2,
  Wrench,
} from 'lucide-react';
import ProfileAvatar from '@/components/common/ProfileAvatar';
import { categoryLabel, resourceTypeLabel } from '@/components/resources/resourceConstants';

const TYPE_ICONS = {
  ARTICLE: FileText,
  COURSE: GraduationCap,
  VIDEO: PlaySquare,
  DOCUMENTATION: BookOpen,
  GITHUB_REPOSITORY: Github,
  TOOL: Wrench,
  BOOK: BookMarked,
  TUTORIAL: Code2,
  OTHER: FileStack,
};

function formatDate(value) {
  if (!value) return 'Recently';
  try {
    return new Intl.DateTimeFormat(undefined, { month: 'short', day: 'numeric', year: 'numeric' }).format(new Date(value));
  } catch {
    return 'Recently';
  }
}

function thumbnailUrl(resource) {
  return resource.thumbnail_url || resource.image_url || resource.cover_image_url || '';
}

export function ResourceCardSkeleton() {
  return (
    <div className="min-h-[340px] animate-pulse rounded-2xl border border-slate-200 bg-white p-4 shadow-sm">
      <div className="h-28 rounded-xl bg-slate-100" />
      <div className="mt-4 h-5 w-3/4 rounded bg-slate-100" />
      <div className="mt-3 h-4 w-full rounded bg-slate-100" />
      <div className="mt-2 h-4 w-5/6 rounded bg-slate-100" />
      <div className="mt-6 h-px bg-slate-100" />
      <div className="mt-4 flex gap-2">
        <div className="h-9 flex-1 rounded-lg bg-slate-100" />
        <div className="h-9 flex-1 rounded-lg bg-slate-100" />
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
  const ThumbnailIcon = TYPE_ICONS[resource.resource_type] || FileStack;
  const imageUrl = thumbnailUrl(resource);

  return (
    <article className="group flex h-full min-w-0 flex-col overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-[0_4px_16px_rgba(16,47,107,0.06)] transition-all hover:-translate-y-0.5 hover:border-brand-200 hover:shadow-[0_10px_24px_rgba(16,47,107,0.1)]">
      <div className="relative mx-4 mt-4 flex h-28 items-center justify-center overflow-hidden rounded-xl border border-slate-200 bg-slate-50">
        {imageUrl ? (
          // eslint-disable-next-line @next/next/no-img-element
          <img src={imageUrl} alt="" className="h-full w-full object-cover" loading="lazy" />
        ) : (
          <ThumbnailIcon className="h-10 w-10 text-brand-300" aria-hidden="true" />
        )}
        <span className="absolute left-2.5 top-2.5 rounded-md bg-white/95 px-2 py-1 text-[10px] font-bold uppercase tracking-[0.12em] text-brand-600 shadow-sm">
          {resourceTypeLabel(resource.resource_type)}
        </span>
        <button
          type="button"
          onClick={() => (resource.is_saved ? onUnsave?.(resource) : onSave?.(resource))}
          disabled={busy}
          aria-label={saveLabel}
          className={`absolute right-2.5 top-2.5 rounded-lg border bg-white/95 p-2 shadow-sm transition-colors disabled:opacity-60 ${
            resource.is_saved
              ? 'border-brand-200 text-brand-600'
              : 'border-slate-200 text-slate-500 hover:border-brand-200 hover:text-brand-600'
          }`}
        >
          {resource.is_saved ? <BookmarkCheck className="h-4 w-4" /> : <Bookmark className="h-4 w-4" />}
        </button>
      </div>

      <div className="flex min-w-0 flex-1 flex-col p-4">
        <p className="text-xs font-medium text-slate-500">{categoryLabel(resource.category)}</p>
        <Link href={`/dashboard/resources/${resource.id}`} className="group/title mt-1.5">
          <h2 className="line-clamp-2 text-base font-semibold leading-snug text-slate-900 group-hover/title:text-brand-600">
            {resource.title}
          </h2>
        </Link>
        <p className="mt-2 line-clamp-3 min-h-[4.25rem] text-sm leading-relaxed text-slate-600">
          {resource.description || 'No description provided yet.'}
        </p>

        <div className="mt-3 flex min-h-7 flex-wrap gap-1.5">
          {(resource.tags || []).slice(0, 4).map((tag) => (
            <span key={tag.toLowerCase()} className="rounded-md bg-slate-100 px-2 py-1 text-[11px] font-medium text-slate-600">
              #{tag}
            </span>
          ))}
        </div>

        <div className="mt-auto flex items-center gap-2 border-t border-slate-100 pt-4">
          <ProfileAvatar
            src={resource.author?.profile_photo_url}
            name={authorName}
            username={resource.author?.username}
            alt={authorName}
            fallback={(authorName?.[0] || 'R').toUpperCase()}
            className="h-8 w-8"
          />
          <div className="min-w-0 flex-1">
            <p className="truncate text-xs font-semibold text-slate-800">{authorName}</p>
            <p className="text-[11px] text-slate-500">{formatDate(resource.created_at)}</p>
          </div>
          <span className="max-w-[8rem] truncate text-[11px] text-slate-400" title={resource.source_domain || resource.url}>
            {resource.source_domain || resource.url}
          </span>
        </div>

        <div className="mt-4 flex flex-wrap gap-2">
          <a
            href={resource.url}
            target="_blank"
            rel="noopener noreferrer"
            className="inline-flex min-w-0 flex-1 items-center justify-center gap-1.5 rounded-lg bg-brand-500 px-3 py-2 text-xs font-semibold text-white transition-colors hover:bg-brand-600"
          >
            <ExternalLink className="h-3.5 w-3.5" aria-hidden="true" />
            Open
          </a>
          <Link
            href={`/dashboard/resources/${resource.id}`}
            className="inline-flex min-w-0 flex-1 items-center justify-center rounded-lg border border-slate-200 px-3 py-2 text-xs font-semibold text-slate-700 transition-colors hover:border-brand-200 hover:bg-brand-50 hover:text-brand-600"
          >
            View
          </Link>
          <button
            type="button"
            onClick={() => onShare?.(resource)}
            className="inline-flex items-center justify-center rounded-lg border border-slate-200 px-3 py-2 text-xs font-semibold text-slate-700 transition-colors hover:border-brand-200 hover:bg-brand-50 hover:text-brand-600"
          >
            <Share2 className="mr-1.5 h-3.5 w-3.5" aria-hidden="true" />
            Share
          </button>
          {resource.is_owner && (
            <>
              <button
                type="button"
                onClick={() => onEdit?.(resource)}
                className="inline-flex items-center justify-center rounded-lg border border-slate-200 p-2 text-slate-500 transition-colors hover:border-brand-200 hover:bg-brand-50 hover:text-brand-600"
                aria-label="Edit resource"
              >
                <Pencil className="h-3.5 w-3.5" />
              </button>
              <button
                type="button"
                onClick={() => onDelete?.(resource)}
                className="inline-flex items-center justify-center rounded-lg border border-red-200 p-2 text-red-600 transition-colors hover:bg-red-50"
                aria-label="Delete resource"
              >
                <Trash2 className="h-3.5 w-3.5" />
              </button>
            </>
          )}
        </div>
      </div>
    </article>
  );
}
