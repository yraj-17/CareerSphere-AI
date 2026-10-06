'use client';

import React, { useCallback, useEffect, useState } from 'react';
import { AlertCircle, Bookmark, LibraryBig, Plus, RefreshCw, Search, X } from 'lucide-react';
import {
  createResource,
  deleteResource,
  extractErrorMessage,
  listResources,
  saveResource,
  unsaveResource,
  updateResource,
} from '@/services/api';
import ResourceCard, { ResourceCardSkeleton } from '@/components/resources/ResourceCard';
import ResourceFormModal from '@/components/resources/ResourceFormModal';
import ShareResourceModal from '@/components/resources/ShareResourceModal';
import { RESOURCE_CATEGORIES, RESOURCE_TYPES, normalizeResourceList } from '@/components/resources/resourceConstants';

const SKELETON_COUNT = 6;

function EmptyState({ saved, query }) {
  return (
    <div data-testid="resources-empty" className="flex flex-col items-center justify-center rounded-3xl border border-white/10 bg-white/[0.035] px-6 py-20 text-center">
      <div className="mb-4 flex h-16 w-16 items-center justify-center rounded-2xl border border-white/10 bg-white/[0.05]">
        {saved ? <Bookmark className="h-8 w-8 text-slate-500" /> : <LibraryBig className="h-8 w-8 text-slate-500" />}
      </div>
      <h2 className="text-lg font-bold text-white">{saved ? 'No saved resources yet.' : 'No resources found.'}</h2>
      <p className="mt-2 max-w-sm text-sm leading-relaxed text-slate-400">
        {saved
          ? 'Save articles, courses, docs, and tools to build your learning library.'
          : query
          ? 'Try a different search or filter.'
          : 'Share the first useful resource with the CareerSphere community.'}
      </p>
    </div>
  );
}

function ErrorState({ message, onRetry }) {
  return (
    <div data-testid="resources-error" className="flex flex-col items-center justify-center rounded-3xl border border-rose-500/20 bg-rose-500/10 px-6 py-16 text-center">
      <AlertCircle className="mb-4 h-10 w-10 text-rose-300" />
      <h2 className="text-lg font-bold text-white">Resources failed to load</h2>
      <p className="mt-2 max-w-md text-sm leading-relaxed text-rose-100/85">{message}</p>
      <button
        type="button"
        onClick={onRetry}
        className="mt-5 inline-flex items-center gap-2 rounded-full bg-accent px-5 py-2.5 text-sm font-semibold text-black hover:bg-accentSoft"
      >
        <RefreshCw className="h-4 w-4" />
        Try Again
      </button>
    </div>
  );
}

export default function ResourcesPage() {
  const [activeView, setActiveView] = useState('all');
  const [query, setQuery] = useState('');
  const [resourceType, setResourceType] = useState('all');
  const [category, setCategory] = useState('all');
  const [resources, setResources] = useState([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [busyIds, setBusyIds] = useState({});
  const [formOpen, setFormOpen] = useState(false);
  const [editTarget, setEditTarget] = useState(null);
  const [shareTarget, setShareTarget] = useState(null);

  const fetchResources = useCallback(async () => {
    setLoading(true);
    setError('');
    try {
      const payload = await listResources({
        q: query,
        resourceType,
        category,
        saved: activeView === 'saved',
        sort: 'newest',
        limit: 30,
        offset: 0,
      });
      setResources(normalizeResourceList(payload));
      setTotal(payload?.total ?? 0);
    } catch (err) {
      setError(extractErrorMessage(err) || 'Unable to load resources.');
    } finally {
      setLoading(false);
    }
  }, [activeView, category, query, resourceType]);

  useEffect(() => {
    fetchResources();
  }, [fetchResources]);

  const setBusy = (id, value) => {
    setBusyIds((prev) => {
      const next = { ...prev };
      if (value) next[id] = true;
      else delete next[id];
      return next;
    });
  };

  const patchResource = (id, patch) => {
    setResources((prev) => prev.map((resource) => (resource.id === id ? { ...resource, ...patch } : resource)));
  };

  const handleSave = async (resource) => {
    setBusy(resource.id, true);
    try {
      await saveResource(resource.id);
      patchResource(resource.id, { is_saved: true, save_count: (resource.save_count || 0) + 1 });
    } catch (err) {
      setError(extractErrorMessage(err) || 'Unable to save resource.');
    } finally {
      setBusy(resource.id, false);
    }
  };

  const handleUnsave = async (resource) => {
    setBusy(resource.id, true);
    try {
      await unsaveResource(resource.id);
      if (activeView === 'saved') {
        setResources((prev) => prev.filter((item) => item.id !== resource.id));
        setTotal((prev) => Math.max(0, prev - 1));
      } else {
        patchResource(resource.id, { is_saved: false, save_count: Math.max(0, (resource.save_count || 0) - 1) });
      }
    } catch (err) {
      setError(extractErrorMessage(err) || 'Unable to unsave resource.');
    } finally {
      setBusy(resource.id, false);
    }
  };

  const handleCreate = async (payload) => {
    await createResource(payload);
    await fetchResources();
  };

  const handleEdit = async (payload) => {
    if (!editTarget) return;
    await updateResource(editTarget.id, payload);
    await fetchResources();
    setEditTarget(null);
  };

  const handleDelete = async (resource) => {
    if (!window.confirm(`Delete "${resource.title}"? This cannot be undone.`)) return;
    setBusy(resource.id, true);
    try {
      await deleteResource(resource.id);
      setResources((prev) => prev.filter((item) => item.id !== resource.id));
      setTotal((prev) => Math.max(0, prev - 1));
    } catch (err) {
      setError(extractErrorMessage(err) || 'Unable to delete resource.');
    } finally {
      setBusy(resource.id, false);
    }
  };

  return (
    <div className="space-y-8 animate-fade-in">
      <ResourceFormModal open={formOpen} mode="create" onClose={() => setFormOpen(false)} onSubmit={handleCreate} />
      <ResourceFormModal
        open={!!editTarget}
        mode="edit"
        resource={editTarget}
        onClose={() => setEditTarget(null)}
        onSubmit={handleEdit}
      />
      <ShareResourceModal
        open={!!shareTarget}
        resource={shareTarget}
        onClose={() => setShareTarget(null)}
        onShared={() => setShareTarget(null)}
      />

      <section className="relative overflow-hidden rounded-[2.5rem] border border-white/10 bg-white/[0.04] p-7 shadow-glow backdrop-blur-2xl sm:p-10">
        <div className="pointer-events-none absolute inset-0 bg-[radial-gradient(circle_at_24%_0%,rgba(255,143,50,0.14),transparent_50%),radial-gradient(circle_at_85%_30%,rgba(64,217,255,0.09),transparent_40%)]" />
        <div className="relative z-10 flex flex-col gap-5 sm:flex-row sm:items-start sm:justify-between">
          <div>
            <div className="mb-3 flex items-center gap-2.5">
              <div className="flex h-9 w-9 items-center justify-center rounded-xl border border-accent/30 bg-accent/15">
                <LibraryBig className="h-4 w-4 text-accent" />
              </div>
              <h1 className="text-2xl font-extrabold tracking-tight text-white sm:text-3xl">Resources</h1>
            </div>
            <p className="max-w-2xl text-sm leading-relaxed text-slate-400">
              Discover and share articles, courses, docs, repos, tools, books, and tutorials that help professionals grow.
            </p>
          </div>
          <button
            type="button"
            onClick={() => setFormOpen(true)}
            className="inline-flex shrink-0 items-center justify-center gap-2 rounded-full bg-accent px-5 py-2.5 text-sm font-semibold text-black shadow-[0_8px_30px_rgba(255,143,50,0.28)] hover:bg-accentSoft"
          >
            <Plus className="h-4 w-4" />
            Share Resource
          </button>
        </div>
      </section>

      {error && (
        <div className="flex items-start gap-3 rounded-2xl border border-rose-500/25 bg-rose-500/10 px-4 py-3 text-sm text-rose-200" role="alert">
          <AlertCircle className="mt-0.5 h-4 w-4 shrink-0" />
          <span className="flex-1">{error}</span>
          <button type="button" onClick={() => setError('')} aria-label="Dismiss error" className="text-rose-200/75 hover:text-white">
            <X className="h-4 w-4" />
          </button>
        </div>
      )}

      <div className="space-y-5">
        <div className="flex flex-col gap-4 xl:flex-row xl:items-center xl:justify-between">
          <div className="flex w-full rounded-2xl border border-white/10 bg-white/[0.04] p-1 xl:w-auto" role="tablist" aria-label="Resources view">
            {[
              { id: 'all', label: 'All' },
              { id: 'saved', label: 'Saved' },
            ].map((item) => (
              <button
                key={item.id}
                type="button"
                role="tab"
                aria-selected={activeView === item.id}
                onClick={() => setActiveView(item.id)}
                className={`flex-1 rounded-xl px-4 py-2.5 text-sm font-semibold transition-colors xl:flex-none ${
                  activeView === item.id ? 'bg-accent text-black' : 'text-slate-300 hover:bg-white/[0.06] hover:text-white'
                }`}
              >
                {item.label}
              </button>
            ))}
          </div>

          <label className="relative block w-full xl:max-w-md">
            <span className="sr-only">Search resources</span>
            <Search className="pointer-events-none absolute left-4 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" />
            <input
              type="search"
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              placeholder="Search resources..."
              className="w-full rounded-2xl border border-white/10 bg-white/[0.04] py-3 pl-11 pr-11 text-sm text-white outline-none placeholder:text-slate-500 focus:border-accent/45"
            />
            {query && (
              <button
                type="button"
                onClick={() => setQuery('')}
                aria-label="Clear resource search"
                className="absolute right-3 top-1/2 -translate-y-1/2 rounded-lg p-1 text-slate-400 hover:text-white"
              >
                <X className="h-4 w-4" />
              </button>
            )}
          </label>
        </div>

        <div className="flex gap-2 overflow-x-auto pb-1" aria-label="Resource types">
          {RESOURCE_TYPES.map((item) => (
            <button
              key={item.id}
              type="button"
              onClick={() => setResourceType(item.id)}
              className={`shrink-0 rounded-full border px-4 py-2 text-sm font-medium transition-colors ${
                resourceType === item.id
                  ? 'border-accent/35 bg-accent/15 text-accent'
                  : 'border-white/10 bg-white/[0.04] text-slate-300 hover:bg-white/[0.07] hover:text-white'
              }`}
            >
              {item.label}
            </button>
          ))}
        </div>

        <div className="flex gap-2 overflow-x-auto pb-1" aria-label="Resource categories">
          {RESOURCE_CATEGORIES.map((item) => (
            <button
              key={item.id}
              type="button"
              onClick={() => setCategory(item.id)}
              className={`shrink-0 rounded-full border px-4 py-2 text-sm font-medium transition-colors ${
                category === item.id
                  ? 'border-sky-300/35 bg-sky-300/10 text-sky-200'
                  : 'border-white/10 bg-white/[0.04] text-slate-300 hover:bg-white/[0.07] hover:text-white'
              }`}
            >
              {item.label}
            </button>
          ))}
        </div>
      </div>

      <section className="space-y-4" aria-label="Resource library">
        <div className="flex items-center justify-between gap-3">
          <h2 className="text-xl font-bold text-white">{activeView === 'saved' ? 'Saved Resources' : 'Resource Library'}</h2>
          {!loading && total > 0 && (
            <span className="rounded-full border border-white/10 bg-white/[0.04] px-3 py-1 text-xs text-slate-400">
              {total.toLocaleString()} found
            </span>
          )}
        </div>

        {loading ? (
          <div className="grid grid-cols-1 gap-5 md:grid-cols-2 xl:grid-cols-3">
            {Array.from({ length: SKELETON_COUNT }).map((_, index) => (
              <ResourceCardSkeleton key={index} />
            ))}
          </div>
        ) : error && resources.length === 0 ? (
          <ErrorState message={error} onRetry={fetchResources} />
        ) : resources.length === 0 ? (
          <EmptyState saved={activeView === 'saved'} query={query} />
        ) : (
          <div className="grid grid-cols-1 gap-5 md:grid-cols-2 xl:grid-cols-3" data-testid="resources-grid">
            {resources.map((resource) => (
              <ResourceCard
                key={resource.id}
                resource={resource}
                busy={!!busyIds[resource.id]}
                onSave={handleSave}
                onUnsave={handleUnsave}
                onShare={setShareTarget}
                onEdit={setEditTarget}
                onDelete={handleDelete}
              />
            ))}
          </div>
        )}
      </section>
    </div>
  );
}
