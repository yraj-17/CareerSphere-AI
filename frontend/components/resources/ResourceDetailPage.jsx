'use client';

import React, { useCallback, useEffect, useState } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { AlertCircle, ArrowLeft, Bookmark, BookmarkCheck, ExternalLink, Loader2, Pencil, Share2, Trash2 } from 'lucide-react';
import ProfileAvatar from '@/components/common/ProfileAvatar';
import {
  deleteResource,
  extractErrorMessage,
  getResource,
  saveResource,
  unsaveResource,
  updateResource,
} from '@/services/api';
import ResourceFormModal from '@/components/resources/ResourceFormModal';
import ShareResourceModal from '@/components/resources/ShareResourceModal';
import { categoryLabel, resourceTypeLabel } from '@/components/resources/resourceConstants';

function formatDate(value) {
  if (!value) return 'Recently';
  try {
    return new Intl.DateTimeFormat(undefined, { dateStyle: 'medium' }).format(new Date(value));
  } catch {
    return 'Recently';
  }
}

export default function ResourceDetailPage({ resourceId }) {
  const router = useRouter();
  const [resource, setResource] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const [editOpen, setEditOpen] = useState(false);
  const [shareOpen, setShareOpen] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    setError('');
    try {
      setResource(await getResource(resourceId));
    } catch (err) {
      setError(extractErrorMessage(err) || 'Unable to load resource.');
    } finally {
      setLoading(false);
    }
  }, [resourceId]);

  useEffect(() => {
    load();
  }, [load]);

  const handleSaveToggle = async () => {
    if (!resource) return;
    setBusy(true);
    try {
      if (resource.is_saved) {
        await unsaveResource(resource.id);
        setResource((prev) => ({ ...prev, is_saved: false, save_count: Math.max(0, (prev.save_count || 0) - 1) }));
      } else {
        await saveResource(resource.id);
        setResource((prev) => ({ ...prev, is_saved: true, save_count: (prev.save_count || 0) + 1 }));
      }
    } catch (err) {
      setError(extractErrorMessage(err) || 'Unable to update saved state.');
    } finally {
      setBusy(false);
    }
  };

  const handleEdit = async (payload) => {
    await updateResource(resource.id, payload);
    setEditOpen(false);
    await load();
  };

  const handleDelete = async () => {
    if (!resource || !window.confirm(`Delete "${resource.title}"? This cannot be undone.`)) return;
    setBusy(true);
    try {
      await deleteResource(resource.id);
      router.push('/dashboard/resources');
    } catch (err) {
      setError(extractErrorMessage(err) || 'Unable to delete resource.');
      setBusy(false);
    }
  };

  if (loading) {
    return (
      <div className="flex min-h-[55vh] items-center justify-center">
        <Loader2 className="h-8 w-8 animate-spin text-accent" />
      </div>
    );
  }

  if (error && !resource) {
    return (
      <div className="mx-auto max-w-3xl rounded-3xl border border-rose-500/20 bg-rose-500/10 px-6 py-16 text-center">
        <AlertCircle className="mx-auto mb-4 h-10 w-10 text-rose-300" />
        <h1 className="text-xl font-bold text-white">Resource unavailable</h1>
        <p className="mt-2 text-sm text-rose-100/85">{error}</p>
        <Link href="/dashboard/resources" className="mt-6 inline-flex rounded-full bg-accent px-5 py-2.5 text-sm font-semibold text-black">
          Back to Resources
        </Link>
      </div>
    );
  }

  const authorName = resource.author
    ? `${resource.author.first_name || ''} ${resource.author.last_name || ''}`.trim() || resource.author.username
    : 'CareerSphere member';

  return (
    <div className="mx-auto w-full max-w-5xl space-y-6">
      <ResourceFormModal open={editOpen} mode="edit" resource={resource} onClose={() => setEditOpen(false)} onSubmit={handleEdit} />
      <ShareResourceModal open={shareOpen} resource={resource} onClose={() => setShareOpen(false)} onShared={() => setShareOpen(false)} />

      <Link href="/dashboard/resources" className="inline-flex items-center gap-2 text-sm font-semibold text-slate-300 hover:text-accent">
        <ArrowLeft className="h-4 w-4" />
        Back to Resources
      </Link>

      {error && (
        <div className="flex items-start gap-3 rounded-2xl border border-rose-500/25 bg-rose-500/10 px-4 py-3 text-sm text-rose-200" role="alert">
          <AlertCircle className="mt-0.5 h-4 w-4 shrink-0" />
          {error}
        </div>
      )}

      <article className="overflow-hidden rounded-[2.5rem] border border-white/10 bg-white/[0.04] shadow-glow backdrop-blur-2xl">
        <div className="relative p-7 sm:p-10">
          <div className="pointer-events-none absolute inset-0 bg-[radial-gradient(circle_at_25%_0%,rgba(255,143,50,0.14),transparent_50%)]" />
          <div className="relative z-10">
            <div className="mb-5 flex flex-wrap gap-2">
              <span className="rounded-full border border-accent/25 bg-accent/10 px-3 py-1 text-xs font-bold uppercase tracking-[0.16em] text-accent">
                {resourceTypeLabel(resource.resource_type)}
              </span>
              <span className="rounded-full border border-white/10 bg-white/[0.05] px-3 py-1 text-xs text-slate-300">
                {categoryLabel(resource.category)}
              </span>
              <span className="rounded-full border border-white/10 bg-white/[0.05] px-3 py-1 text-xs text-slate-400">
                {resource.source_domain}
              </span>
            </div>

            <h1 className="max-w-4xl text-3xl font-extrabold tracking-tight text-white sm:text-4xl">{resource.title}</h1>
            <p className="mt-5 max-w-3xl text-base leading-relaxed text-slate-300">
              {resource.description || 'No description provided for this resource yet.'}
            </p>

            <div className="mt-6 flex flex-wrap gap-2">
              {(resource.tags || []).map((tag) => (
                <span key={tag.toLowerCase()} className="rounded-full border border-white/10 bg-white/[0.04] px-3 py-1 text-xs text-slate-300">
                  #{tag}
                </span>
              ))}
            </div>

            <div className="mt-8 flex flex-col gap-4 border-t border-white/10 pt-6 sm:flex-row sm:items-center sm:justify-between">
              <div className="flex items-center gap-3">
                <ProfileAvatar
                  src={resource.author?.profile_photo_url}
                  name={authorName}
                  username={resource.author?.username}
                  alt={authorName}
                  fallback={(authorName?.[0] || 'R').toUpperCase()}
                  className="h-12 w-12"
                />
                <div>
                  <p className="font-semibold text-white">{authorName}</p>
                  <p className="text-xs text-slate-500">Shared {formatDate(resource.created_at)}</p>
                </div>
              </div>

              <div className="flex flex-wrap gap-2">
                <button
                  type="button"
                  disabled={busy}
                  onClick={handleSaveToggle}
                  className="inline-flex items-center justify-center gap-2 rounded-full border border-white/10 px-4 py-2.5 text-sm font-semibold text-slate-200 hover:border-accent/30 hover:text-accent disabled:opacity-60"
                >
                  {resource.is_saved ? <BookmarkCheck className="h-4 w-4" /> : <Bookmark className="h-4 w-4" />}
                  {resource.is_saved ? 'Saved' : 'Save'}
                </button>
                <a
                  href={resource.url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="inline-flex items-center justify-center gap-2 rounded-full bg-accent px-5 py-2.5 text-sm font-semibold text-black hover:bg-accentSoft"
                >
                  <ExternalLink className="h-4 w-4" />
                  Open Resource
                </a>
                <button
                  type="button"
                  onClick={() => setShareOpen(true)}
                  className="inline-flex items-center justify-center gap-2 rounded-full border border-white/10 px-4 py-2.5 text-sm font-semibold text-slate-200 hover:border-accent/30 hover:text-accent"
                >
                  <Share2 className="h-4 w-4" />
                  Share
                </button>
                {resource.is_owner && (
                  <>
                    <button
                      type="button"
                      onClick={() => setEditOpen(true)}
                      className="inline-flex items-center justify-center gap-2 rounded-full border border-white/10 px-4 py-2.5 text-sm font-semibold text-slate-200 hover:text-accent"
                    >
                      <Pencil className="h-4 w-4" />
                      Edit
                    </button>
                    <button
                      type="button"
                      disabled={busy}
                      onClick={handleDelete}
                      className="inline-flex items-center justify-center gap-2 rounded-full border border-rose-500/20 px-4 py-2.5 text-sm font-semibold text-rose-200 hover:bg-rose-500/10 disabled:opacity-60"
                    >
                      <Trash2 className="h-4 w-4" />
                      Delete
                    </button>
                  </>
                )}
              </div>
            </div>
          </div>
        </div>
      </article>
    </div>
  );
}
