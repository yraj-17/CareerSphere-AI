'use client';

import React, { useCallback, useEffect, useState } from 'react';
import { AlertCircle, Bookmark, FileStack, Plus, RefreshCw, Search, X } from 'lucide-react';
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

function EmptyState({ saved, query, filtersActive, onClear, onShare }) {
  const hasFilters = Boolean(query || filtersActive);
  const title = saved ? 'No saved resources yet' : hasFilters ? 'No matching resources' : 'No resources found';
  const description = saved
    ? 'Save articles, courses, docs, and tools to build your learning library.'
    : hasFilters
    ? 'Try adjusting your search or filters to find a useful resource.'
    : 'Share the first useful resource with the CareerSphere community.';

  return (
    <div data-testid="resources-empty" className="flex flex-col items-center justify-center rounded-2xl border border-dashed border-slate-300 bg-white px-6 py-12 text-center">
      <div className="mb-4 flex h-12 w-12 items-center justify-center rounded-xl border border-brand-100 bg-brand-50">
        {saved ? <Bookmark className="h-6 w-6 text-brand-500" /> : <FileStack className="h-6 w-6 text-brand-500" />}
      </div>
      <h2 className="text-lg font-semibold text-slate-900">{title}</h2>
      <p className="mt-2 max-w-md text-sm leading-relaxed text-slate-500">{description}</p>
      <div className="mt-5 flex flex-wrap justify-center gap-3">
        {hasFilters && (
          <button type="button" onClick={onClear} className="btn-outline">
            Clear filters
          </button>
        )}
        {!saved && !hasFilters && (
          <button type="button" onClick={onShare} className="btn-primary">
            <Plus className="h-4 w-4" aria-hidden="true" />
            Share Resource
          </button>
        )}
      </div>
    </div>
  );
}

function ErrorState({ message, onRetry }) {
  return (
    <div data-testid="resources-error" className="flex flex-col items-center justify-center rounded-2xl border border-red-200 bg-red-50 px-6 py-12 text-center">
      <AlertCircle className="mb-4 h-8 w-8 text-red-600" />
      <h2 className="text-lg font-semibold text-slate-900">Resources failed to load</h2>
      <p className="mt-2 max-w-md text-sm leading-relaxed text-red-700">{message}</p>
      <button
        type="button"
        onClick={onRetry}
        className="btn-primary mt-5"
      >
        <RefreshCw className="h-4 w-4" aria-hidden="true" />
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

  useEffect(() => {
    document.documentElement.classList.add('scrollbar-hidden');
    return () => document.documentElement.classList.remove('scrollbar-hidden');
  }, []);

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

  const clearFilters = () => {
    setQuery('');
    setResourceType('all');
    setCategory('all');
    setActiveView('all');
  };

  const filtersActive = resourceType !== 'all' || category !== 'all';

  return (
    <div className="space-y-6 animate-fade-in">
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

      <section className="flex flex-col gap-4 border-b border-slate-200 pb-5 sm:flex-row sm:items-center sm:justify-between">
        <div className="flex min-w-0 items-start gap-3">
          <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl border border-brand-100 bg-brand-50">
            <FileStack className="h-5 w-5 text-brand-500" aria-hidden="true" />
          </div>
          <div className="min-w-0">
            <p className="text-xs font-semibold uppercase tracking-[0.18em] text-brand-500">Knowledge hub</p>
            <h1 className="page-title mt-1">Resources</h1>
            <p className="page-description mt-1.5">
              Discover and share practical resources for learning and career growth.
            </p>
          </div>
        </div>
        <button type="button" onClick={() => setFormOpen(true)} className="btn-primary shrink-0">
          <Plus className="h-4 w-4" aria-hidden="true" />
          Share Resource
        </button>
      </section>

      {error && (
        <div className="flex items-start gap-3 rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700" role="alert">
          <AlertCircle className="mt-0.5 h-4 w-4 shrink-0" aria-hidden="true" />
          <span className="flex-1">{error}</span>
          <button type="button" onClick={() => setError('')} aria-label="Dismiss error" className="text-red-600/75 hover:text-red-800">
            <X className="h-4 w-4" />
          </button>
        </div>
      )}

      <div className="surface-card space-y-4 p-4 sm:p-5">
        <div className="flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
          <div className="flex w-full rounded-lg bg-slate-100 p-1 lg:w-auto" role="tablist" aria-label="Resources view">
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
                className={`flex-1 rounded-md px-5 py-2 text-sm font-semibold transition-colors lg:flex-none ${
                  activeView === item.id ? 'bg-white text-brand-600 shadow-sm' : 'text-slate-600 hover:text-slate-900'
                }`}
              >
                {item.label}
              </button>
            ))}
          </div>

          <label className="relative block w-full lg:max-w-md lg:flex-1">
            <span className="sr-only">Search resources</span>
            <Search className="pointer-events-none absolute left-3.5 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" aria-hidden="true" />
            <input
              type="search"
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              placeholder="Search resources..."
              className="input-base py-2.5 pl-10 pr-10"
            />
            {query && (
              <button
                type="button"
                onClick={() => setQuery('')}
                aria-label="Clear resource search"
                className="absolute right-3 top-1/2 -translate-y-1/2 rounded-lg p-1 text-slate-400 hover:text-slate-700"
              >
                <X className="h-4 w-4" />
              </button>
            )}
          </label>
        </div>

        <div className="space-y-3 border-t border-slate-200 pt-4">
          <div className="flex flex-col gap-2 sm:flex-row sm:items-start">
            <span className="w-16 shrink-0 pt-1 text-xs font-semibold uppercase tracking-wide text-slate-500">Type</span>
            <div className="flex flex-wrap gap-2" aria-label="Resource types">
              {RESOURCE_TYPES.map((item) => (
                <button
                  key={item.id}
                  type="button"
                  onClick={() => setResourceType(item.id)}
                  className={`min-h-8 rounded-lg border px-3 py-1.5 text-xs font-medium transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-brand-200 sm:text-sm ${
                    resourceType === item.id
                      ? 'border-brand-200 bg-brand-50 text-brand-600'
                      : 'border-slate-200 bg-white text-slate-600 hover:border-slate-300 hover:bg-slate-50 hover:text-slate-900'
                  }`}
                >
                  {item.label}
                </button>
              ))}
            </div>
          </div>

          <div className="flex flex-col gap-2 sm:flex-row sm:items-start">
            <span className="w-16 shrink-0 pt-1 text-xs font-semibold uppercase tracking-wide text-slate-500">Category</span>
            <div className="flex flex-wrap gap-2" aria-label="Resource categories">
              {RESOURCE_CATEGORIES.map((item) => (
                <button
                  key={item.id}
                  type="button"
                  onClick={() => setCategory(item.id)}
                  className={`min-h-8 rounded-lg border px-3 py-1.5 text-xs font-medium transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-brand-200 sm:text-sm ${
                    category === item.id
                      ? 'border-brand-200 bg-brand-50 text-brand-600'
                      : 'border-slate-200 bg-white text-slate-600 hover:border-slate-300 hover:bg-slate-50 hover:text-slate-900'
                  }`}
                >
                  {item.label}
                </button>
              ))}
            </div>
          </div>
        </div>
      </div>

      <section className="space-y-4" aria-label="Resource library">
        <div className="flex items-center justify-between gap-3">
          <div>
            <h2 className="text-lg font-semibold text-slate-900">{activeView === 'saved' ? 'Saved Resources' : 'Resource Library'}</h2>
            <p className="mt-0.5 text-sm text-slate-500">{activeView === 'saved' ? 'Your bookmarked learning resources.' : 'Useful resources shared by the CareerSphere community.'}</p>
          </div>
          {!loading && total > 0 && (
            <span className="shrink-0 rounded-full bg-slate-100 px-3 py-1 text-xs font-medium text-slate-600">
              {total.toLocaleString()} found
            </span>
          )}
        </div>

        {loading ? (
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-3">
            {Array.from({ length: SKELETON_COUNT }).map((_, index) => (
              <ResourceCardSkeleton key={index} />
            ))}
          </div>
        ) : error && resources.length === 0 ? (
          <ErrorState message={error} onRetry={fetchResources} />
        ) : resources.length === 0 ? (
          <EmptyState
            saved={activeView === 'saved'}
            query={query}
            filtersActive={filtersActive}
            onClear={clearFilters}
            onShare={() => setFormOpen(true)}
          />
        ) : (
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-3" data-testid="resources-grid">
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
